"""Unit tests for the Execution Engine — the driver that performs what RM prepared.

Covers the full signal loop and every terminal branch: happy completion, cancellation
(cooperative + engine-enforced), timeout, adapter-reported failure, adapter crash, cleanup
failure, the not-Ready guard, artifact collection by reference, honest progress, and the
determinism guarantee (identical event ids/payloads across two runs under a fixed clock).
"""

from __future__ import annotations

import pytest

from nexus_core.contracts.base import Reference
from nexus_execution.adapter import ExecutionControl, TeardownReport
from nexus_execution.errors import ExecutionStartupError, TransportError
from nexus_execution.signals import (
    ArtifactSignal,
    OutputSignal,
    ProgressSignal,
    StreamChannel,
    TerminalOutcome,
    TerminalSignal,
)
from nexus_runtime import FixedTimestampSource
from nexus_runtime.lifecycle import project_state
from nexus_runtime.vocabulary import RuntimeLifecycleState
from tests.unit.nexus_execution.helpers import FakeAdapter, prepared_slice

# --------------------------------------------------------------------------- #
# Happy path                                                                    #
# --------------------------------------------------------------------------- #

_HAPPY_SIGNALS = (
    OutputSignal(StreamChannel.STDOUT, "hello\n"),
    ProgressSignal(phase="work", fraction=0.5, milestone="halfway"),
    ArtifactSignal(Reference(target_type="artifact", identifier="out.txt"), kind="file"),
    OutputSignal(StreamChannel.STDERR, "a warning\n"),
    TerminalSignal(TerminalOutcome.COMPLETED, exit_status=0),
)


def test_happy_path_reaches_completed_then_destroyed() -> None:
    env = prepared_slice()
    adapter = FakeAdapter(_HAPPY_SIGNALS)
    result = env.execution.engine.execute(env.session, adapter, env.work_package)
    assert result.outcome is TerminalOutcome.COMPLETED
    assert result.final_state is RuntimeLifecycleState.DESTROYED
    assert result.succeeded is True


def test_happy_path_emits_canonical_event_types_in_order() -> None:
    env = prepared_slice()
    env.execution.engine.execute(env.session, FakeAdapter(_HAPPY_SIGNALS), env.work_package)
    exec_types = [t for t in env.event_types() if t.startswith("runtime.") and t not in _PREP_TYPES]
    assert exec_types == [
        "runtime.started",
        "runtime.output",
        "runtime.progress",
        "runtime.artifact_emitted",
        "runtime.output",
        "runtime.artifact_emitted",  # synthesized captured-output artifact
        "runtime.completed",
        "runtime.destroyed",
    ]


def test_full_stream_projects_to_destroyed() -> None:
    env = prepared_slice()
    env.execution.engine.execute(env.session, FakeAdapter(_HAPPY_SIGNALS), env.work_package)
    assert project_state(env.event_types()) is RuntimeLifecycleState.DESTROYED


def test_captured_output_is_collected() -> None:
    env = prepared_slice()
    result = env.execution.engine.execute(
        env.session, FakeAdapter(_HAPPY_SIGNALS), env.work_package
    )
    assert result.stdout == "hello\n"
    assert result.stderr == "a warning\n"


def test_artifacts_collected_by_reference() -> None:
    env = prepared_slice()
    result = env.execution.engine.execute(
        env.session, FakeAdapter(_HAPPY_SIGNALS), env.work_package
    )
    identifiers = [r.identifier for r in result.artifact_refs]
    assert "out.txt" in identifiers
    assert f"{env.session.identity}-captured-output" in identifiers


def test_cleanup_runs_on_success() -> None:
    env = prepared_slice()
    adapter = FakeAdapter(_HAPPY_SIGNALS)
    env.execution.engine.execute(env.session, adapter, env.work_package)
    assert adapter.cleaned_up is True


_PREP_TYPES = frozenset(
    {
        "runtime.session_created",
        "runtime.candidates_resolved",
        "runtime.capabilities_matched",
        "runtime.allocated",
        "runtime.prepared",
        "runtime.ready",
        "runtime.registered",
    }
)


# --------------------------------------------------------------------------- #
# Guard: session must be Ready                                                   #
# --------------------------------------------------------------------------- #


def test_execute_rejects_non_ready_session() -> None:
    env = prepared_slice()
    running = env.session.transitioned_to(RuntimeLifecycleState.RUNNING)
    with pytest.raises(ExecutionStartupError):
        env.execution.engine.execute(running, FakeAdapter(_HAPPY_SIGNALS), env.work_package)


# --------------------------------------------------------------------------- #
# Failure branches                                                               #
# --------------------------------------------------------------------------- #


def test_adapter_reported_failure_maps_to_failed() -> None:
    env = prepared_slice()
    signals = (
        OutputSignal(StreamChannel.STDOUT, "trying\n"),
        TerminalSignal(TerminalOutcome.FAILED, error_class="provider-failure", detail="boom"),
    )
    result = env.execution.engine.execute(env.session, FakeAdapter(signals), env.work_package)
    assert result.outcome is TerminalOutcome.FAILED
    assert result.final_state is RuntimeLifecycleState.DESTROYED
    assert result.error_class == "provider-failure"


def test_adapter_raising_execution_error_is_classified() -> None:
    env = prepared_slice()
    adapter = FakeAdapter(
        (OutputSignal(StreamChannel.STDOUT, "x\n"),),
        raise_at=0,
        raise_exc=TransportError("socket reset"),
    )
    result = env.execution.engine.execute(env.session, adapter, env.work_package)
    assert result.outcome is TerminalOutcome.FAILED
    assert result.error_class == "transport-failure"
    assert result.error_owner == "transport"


def test_adapter_generic_crash_becomes_provider_failure() -> None:
    env = prepared_slice()
    adapter = FakeAdapter(
        (OutputSignal(StreamChannel.STDOUT, "x\n"),),
        raise_at=0,
        raise_exc=RuntimeError("unexpected"),
    )
    result = env.execution.engine.execute(env.session, adapter, env.work_package)
    assert result.outcome is TerminalOutcome.FAILED
    assert result.error_class == "provider-failure"
    assert "unexpected" in (result.error_detail or "")


def test_failed_run_emits_runtime_failed_with_owner() -> None:
    env = prepared_slice()
    adapter = FakeAdapter(
        (OutputSignal(StreamChannel.STDOUT, "x\n"),), raise_at=0, raise_exc=TransportError("reset")
    )
    env.execution.engine.execute(env.session, adapter, env.work_package)
    failed = [
        e
        for e in env.events()
        if e.type == "runtime.failed" and e.identifier.startswith(f"evt-{env.session.identity}-")
    ]
    assert failed
    assert failed[0].payload["owner"] == "transport"
    assert failed[0].payload["error_class"] == "transport-failure"


# --------------------------------------------------------------------------- #
# Cancellation                                                                   #
# --------------------------------------------------------------------------- #


def test_engine_enforced_cancellation() -> None:
    env = prepared_slice()
    # Adapter cancels the control after its 1st signal but keeps yielding; engine must stop.
    signals = tuple(OutputSignal(StreamChannel.STDOUT, f"line {i}\n") for i in range(5))
    adapter = FakeAdapter(signals, cancel_after=1)
    result = env.execution.engine.execute(env.session, adapter, env.work_package)
    assert result.outcome is TerminalOutcome.CANCELLED
    assert result.final_state is RuntimeLifecycleState.DESTROYED


def test_cancelled_run_emits_runtime_cancelled() -> None:
    env = prepared_slice()
    signals = tuple(OutputSignal(StreamChannel.STDOUT, f"{i}\n") for i in range(3))
    env.execution.engine.execute(
        env.session, FakeAdapter(signals, cancel_after=1), env.work_package
    )
    types = env.event_types()
    assert "runtime.cancelled" in types
    assert "runtime.destroyed" in types


def test_stream_ends_after_cancel_is_cancelled() -> None:
    env = prepared_slice()
    control = ExecutionControl()
    control.cancel()
    # Pre-cancelled control, adapter yields one non-terminal then stream ends.
    result = env.execution.engine.execute(
        env.session,
        FakeAdapter((OutputSignal(StreamChannel.STDOUT, "x\n"),)),
        env.work_package,
        control=control,
    )
    assert result.outcome is TerminalOutcome.CANCELLED


# --------------------------------------------------------------------------- #
# Timeout                                                                        #
# --------------------------------------------------------------------------- #


def test_empty_stream_precancelled_is_cancelled() -> None:
    env = prepared_slice()
    control = ExecutionControl()
    control.cancel()
    # Empty stream + pre-cancelled control: the in-loop check never runs, so the
    # default-terminal path resolves to Cancelled (not Completed).
    result = env.execution.engine.execute(
        env.session, FakeAdapter(()), env.work_package, control=control
    )
    assert result.outcome is TerminalOutcome.CANCELLED


def test_timeout_fires_and_fails() -> None:
    env = prepared_slice()
    signals = tuple(OutputSignal(StreamChannel.STDOUT, f"{i}\n") for i in range(10))
    control = ExecutionControl(deadline_steps=3)
    result = env.execution.engine.execute(
        env.session, FakeAdapter(signals), env.work_package, control=control
    )
    assert result.outcome is TerminalOutcome.FAILED
    assert result.error_class == "timeout"


def test_timeout_emits_runtime_timed_out() -> None:
    env = prepared_slice()
    signals = tuple(OutputSignal(StreamChannel.STDOUT, f"{i}\n") for i in range(10))
    control = ExecutionControl(deadline_steps=2)
    env.execution.engine.execute(
        env.session, FakeAdapter(signals), env.work_package, control=control
    )
    assert "runtime.timed_out" in env.event_types()


# --------------------------------------------------------------------------- #
# Cleanup / teardown                                                            #
# --------------------------------------------------------------------------- #


def test_cleanup_failure_is_surfaced_but_still_destroyed() -> None:
    env = prepared_slice()
    adapter = FakeAdapter(_HAPPY_SIGNALS, cleanup=TeardownReport(ok=False, detail="orphan process"))
    result = env.execution.engine.execute(env.session, adapter, env.work_package)
    assert result.cleanup_ok is False
    assert result.final_state is RuntimeLifecycleState.DESTROYED


def test_cleanup_crash_is_caught_and_surfaced() -> None:
    env = prepared_slice()
    adapter = FakeAdapter(_HAPPY_SIGNALS, cleanup_raise=RuntimeError("kill failed"))
    result = env.execution.engine.execute(env.session, adapter, env.work_package)
    assert result.cleanup_ok is False
    assert result.final_state is RuntimeLifecycleState.DESTROYED


# --------------------------------------------------------------------------- #
# Stream without an explicit terminal                                           #
# --------------------------------------------------------------------------- #


def test_stream_without_terminal_completes() -> None:
    env = prepared_slice()
    result = env.execution.engine.execute(
        env.session, FakeAdapter((OutputSignal(StreamChannel.STDOUT, "x\n"),)), env.work_package
    )
    assert result.outcome is TerminalOutcome.COMPLETED


def test_no_output_produces_no_captured_artifact() -> None:
    env = prepared_slice()
    signals = (ProgressSignal(phase="p", fraction=None), TerminalSignal(TerminalOutcome.COMPLETED))
    result = env.execution.engine.execute(env.session, FakeAdapter(signals), env.work_package)
    assert result.artifact_refs == ()


def test_unknown_progress_is_recorded_honestly() -> None:
    env = prepared_slice()
    signals = (
        ProgressSignal(phase="p", fraction=None, milestone="m"),
        TerminalSignal(TerminalOutcome.COMPLETED),
    )
    env.execution.engine.execute(env.session, FakeAdapter(signals), env.work_package)
    progress = [e for e in env.events() if e.type == "runtime.progress"]
    assert progress[0].payload["fraction"] == "unknown"


def test_structured_output_is_captured() -> None:
    env = prepared_slice()
    signals = (
        OutputSignal(StreamChannel.STRUCTURED, '{"k":1}'),
        TerminalSignal(TerminalOutcome.COMPLETED),
    )
    result = env.execution.engine.execute(env.session, FakeAdapter(signals), env.work_package)
    assert result.structured == ('{"k":1}',)


# --------------------------------------------------------------------------- #
# Determinism                                                                    #
# --------------------------------------------------------------------------- #


def test_two_runs_emit_identical_event_ids_and_payloads() -> None:
    env1 = prepared_slice(timestamps=FixedTimestampSource())
    env2 = prepared_slice(timestamps=FixedTimestampSource())
    env1.execution.engine.execute(env1.session, FakeAdapter(_HAPPY_SIGNALS), env1.work_package)
    env2.execution.engine.execute(env2.session, FakeAdapter(_HAPPY_SIGNALS), env2.work_package)
    triples1 = [(e.identifier, e.type, e.payload) for e in env1.events()]
    triples2 = [(e.identifier, e.type, e.payload) for e in env2.events()]
    assert triples1 == triples2


def test_started_event_tolerates_missing_runtime_ref() -> None:
    env = prepared_slice()
    session = env.session.model_copy(update={"runtime_ref": None})
    env.execution.engine.execute(session, FakeAdapter(_HAPPY_SIGNALS), env.work_package)
    started = [e for e in env.events() if e.type == "runtime.started"]
    assert started[0].payload["runtime"] is None


def test_metrics_report_counts() -> None:
    env = prepared_slice()
    result = env.execution.engine.execute(
        env.session, FakeAdapter(_HAPPY_SIGNALS), env.work_package
    )
    assert result.metrics["output_chunks"] == 2
    assert result.metrics["event_count"] == len(result.event_ids)
