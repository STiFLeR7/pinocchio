"""Milestone 4 — the end-to-end Runtime vertical slice (deterministic).

Drives the full post-Harness pipeline for one runtime, exactly once:

    Execution Package (projected as a RuntimeIntake, the sanctioned integration boundary)
        → Runtime Manager (prepare → Ready)
        → Execution Engine (perform)
        → Claude Runtime Adapter (StubClaudeInvoker — deterministic)
        → Execution Result (Destroyed)

It captures *every* emitted event, *every* state transition, *every* artifact, and the run
metrics — the Milestone-4 capture requirement — and proves the two headline guarantees: the
whole-lifecycle state is a projection of the ``runtime.*`` log (ADR-001), and two
independent runs emit byte-identical event streams (the determinism requirement). A separate
failure scenario proves a Claude error maps onto the doc-11 model and still reaches
Destroyed. An opt-in smoke test drives the *real* ``claude`` CLI when
``NEXUS_CLAUDE_SMOKE=1`` and a ``claude`` binary are present.

Two structural guardrails enforce the architecture's validation checklist directly: the RM
core (``nexus_runtime``) and the generic Execution Engine (``nexus_execution``) contain
**zero** Claude-specific source.
"""

from __future__ import annotations

import os
import pathlib

import pytest

from nexus_execution import build_execution
from nexus_execution.signals import TerminalOutcome
from nexus_infra import InMemoryObservability, build_infrastructure
from nexus_runtime import FixedTimestampSource, build_runtime
from nexus_runtime.lifecycle import project_state
from nexus_runtime.vocabulary import RuntimeLifecycleState
from nexus_runtime_claude import ClaudeCliInvoker, ClaudeRuntimeAdapter, StubClaudeInvoker
from tests.unit.nexus_runtime.helpers import intake, preparation_request

_LIFECYCLE_DRIVING = (
    "runtime.session_created",
    "runtime.candidates_resolved",
    "runtime.allocated",
    "runtime.prepared",
    "runtime.ready",
    "runtime.started",
    "runtime.completed",
    "runtime.destroyed",
)


def _run_slice(*, fail: bool = False):  # type: ignore[no-untyped-def]
    """Prepare + execute the full slice; return (infra, session, result)."""
    infra = build_infrastructure(observability=InMemoryObservability())
    ts = FixedTimestampSource()
    runtime = build_runtime(infra, timestamps=ts)
    adapter = ClaudeRuntimeAdapter(invoker=StubClaudeInvoker(fail=fail))

    # Integration boundary: register the runtime, then project the Execution Package into a
    # RuntimeIntake (requests.py's documented pattern) and prepare it to Ready.
    runtime.manager.register_runtime(adapter.descriptor())
    itk = intake(candidates=("claude-code",), required=("code_generation",))
    prepared = runtime.manager.prepare(preparation_request(itk))
    session = prepared.sessions[0]
    assert session.lifecycle_state is RuntimeLifecycleState.READY

    execution = build_execution(infra, timestamps=ts)
    result = execution.engine.execute(session, adapter, itk.work_package)
    return infra, session, result


def _session_event_types(infra, session_identity: str) -> tuple[str, ...]:  # type: ignore[no-untyped-def]
    return tuple(
        e.type
        for e in infra.event_store.read_all()
        if e.identifier.startswith(f"evt-{session_identity}-")
    )


# --------------------------------------------------------------------------- #
# Happy-path end-to-end                                                         #
# --------------------------------------------------------------------------- #


def test_e2e_completes_and_is_destroyed() -> None:
    _infra, _session, result = _run_slice()
    assert result.outcome is TerminalOutcome.COMPLETED
    assert result.final_state is RuntimeLifecycleState.DESTROYED
    assert result.succeeded is True


def test_e2e_captures_full_lifecycle_event_stream() -> None:
    infra, session, _result = _run_slice()
    types = _session_event_types(infra, session.identity)
    # every lifecycle-driving event appears, in canonical order
    driving = tuple(t for t in types if t in _LIFECYCLE_DRIVING)
    assert driving == _LIFECYCLE_DRIVING


def test_e2e_state_is_a_projection_of_the_log() -> None:
    infra, session, result = _run_slice()
    types = _session_event_types(infra, session.identity)
    assert project_state(types) is RuntimeLifecycleState.DESTROYED
    assert project_state(types) is result.final_state


def test_e2e_captures_artifacts_by_reference() -> None:
    _infra, _session, result = _run_slice()
    identifiers = [r.identifier for r in result.artifact_refs]
    assert any("main.py" in i for i in identifiers)  # a produced file
    assert any("captured-output" in i for i in identifiers)  # the captured stream


def test_e2e_captures_metrics() -> None:
    _infra, _session, result = _run_slice()
    assert result.metrics["event_count"] == len(result.event_ids)
    assert result.metrics["output_chunks"] >= 1


def test_e2e_is_deterministic_across_runs() -> None:
    infra1, _s1, _r1 = _run_slice()
    infra2, _s2, _r2 = _run_slice()
    triples1 = [
        (e.identifier, e.type, e.payload, e.timestamp) for e in infra1.event_store.read_all()
    ]
    triples2 = [
        (e.identifier, e.type, e.payload, e.timestamp) for e in infra2.event_store.read_all()
    ]
    assert triples1 == triples2


# --------------------------------------------------------------------------- #
# Failure path end-to-end                                                       #
# --------------------------------------------------------------------------- #


def test_e2e_claude_error_maps_to_failed_then_destroyed() -> None:
    infra, session, result = _run_slice(fail=True)
    assert result.outcome is TerminalOutcome.FAILED
    assert result.error_class == "provider-failure"
    assert result.final_state is RuntimeLifecycleState.DESTROYED
    assert "runtime.failed" in _session_event_types(infra, session.identity)


# --------------------------------------------------------------------------- #
# Architectural guardrails (validation checklist, enforced in code)             #
# --------------------------------------------------------------------------- #

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _package_source(package: str) -> str:
    root = _REPO_ROOT / package
    return "\n".join(p.read_text(encoding="utf-8") for p in root.glob("*.py"))


def test_runtime_manager_core_contains_zero_claude_reference() -> None:
    # RM core is provider-blind: not a single mention of any provider (doc 03 §3).
    assert "claude" not in _package_source("nexus_runtime").lower()


def test_execution_engine_does_not_depend_on_the_claude_adapter() -> None:
    # The generic engine may *name* the example adapter in prose, but must never import it
    # or branch on a provider — the load-bearing invariant (doc 03 §3 litmus, doc 22 §5).
    source = _package_source("nexus_execution")
    assert "import nexus_runtime_claude" not in source
    assert "from nexus_runtime_claude" not in source


def test_claude_adapter_holds_all_provider_behavior() -> None:
    # The converse: the provider package is where "claude" lives (doc 03 §1).
    assert "claude" in _package_source("nexus_runtime_claude").lower()


# --------------------------------------------------------------------------- #
# Opt-in real-Claude smoke (skipped unless NEXUS_CLAUDE_SMOKE=1 + a binary)      #
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    os.environ.get("NEXUS_CLAUDE_SMOKE") != "1",
    reason="opt-in: set NEXUS_CLAUDE_SMOKE=1 with an authenticated `claude` CLI on PATH",
)
def test_e2e_real_claude_cli_smoke() -> None:  # pragma: no cover - opt-in, environment-gated
    binary = os.environ.get("NEXUS_CLAUDE_BIN", "claude")
    infra = build_infrastructure(observability=InMemoryObservability())
    runtime = build_runtime(infra)  # real (system) timestamps — this path is not deterministic
    adapter = ClaudeRuntimeAdapter(invoker=ClaudeCliInvoker(binary=binary))
    runtime.manager.register_runtime(adapter.descriptor())
    itk = intake(candidates=("claude-code",), required=("code_generation",))
    session = runtime.manager.prepare(preparation_request(itk)).sessions[0]

    execution = build_execution(infra)
    result = execution.engine.execute(session, adapter, itk.work_package)

    # Only the *shape* is asserted — the model's text is non-deterministic.
    assert result.final_state is RuntimeLifecycleState.DESTROYED
    assert result.outcome is TerminalOutcome.COMPLETED
    types = _session_event_types(infra, session.identity)
    assert "runtime.started" in types
    assert "runtime.destroyed" in types
