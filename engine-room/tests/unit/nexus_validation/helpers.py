"""Shared, deterministic builders for the Validation Engine test suite.

Provides an :class:`ExecutionResult` factory (so rule/evaluator/collector tests exercise
verdicts without running a real execution), a ``runtime.artifact_emitted`` event factory
(the independent Evidence-Candidate record the collector reads), and a full prepared →
executed slice for the engine/integration tests. Every builder is deterministic.
"""

from __future__ import annotations

from collections.abc import Sequence

from nexus_core.contracts.base import Reference, Struct
from nexus_core.domain.event import Event
from nexus_core.domain.work_package import WorkPackage
from nexus_execution.results import ExecutionResult
from nexus_execution.signals import TerminalOutcome
from nexus_runtime.events import RUNTIME_ARTIFACT_EMITTED
from nexus_runtime.vocabulary import RuntimeLifecycleState
from tests.unit.nexus_runtime.helpers import work_package

SESSION = "rts-pkg-val-01"
CORRELATION = "cor-val"


def _ref(target_type: str, identifier: str) -> Reference:
    return Reference(target_type=target_type, identifier=identifier)


def execution_result(
    *,
    session: str = SESSION,
    work_package_id: str = "wp-val",
    runtime: str | None = "claude-code",
    outcome: TerminalOutcome = TerminalOutcome.COMPLETED,
    final_state: RuntimeLifecycleState = RuntimeLifecycleState.DESTROYED,
    exit_status: int | None = 0,
    artifacts: Sequence[str] = ("wp-val-main.py",),
    stdout: str = "done\n",
    stderr: str = "",
    structured: Sequence[str] = (),
    cleanup_ok: bool = True,
    error_class: str | None = None,
    error_owner: str | None = None,
    metrics: Struct | None = None,
) -> ExecutionResult:
    """Build a deterministic :class:`ExecutionResult` fixture."""
    return ExecutionResult(
        session_ref=_ref("runtime_session", session),
        work_package_ref=_ref("work_package", work_package_id),
        runtime_ref=_ref("harness", runtime) if runtime else None,
        outcome=outcome,
        final_state=final_state,
        exit_status=exit_status,
        artifact_refs=tuple(_ref("artifact", a) for a in artifacts),
        event_ids=(),
        cleanup_ok=cleanup_ok,
        error_class=error_class,
        error_owner=error_owner,
        error_detail=None if error_class is None else "detail",
        stdout=stdout,
        stderr=stderr,
        structured=tuple(structured),
        metrics=metrics or {"output_chunks": 1, "artifact_count": len(artifacts), "event_count": 5},
    )


def artifact_event(
    artifact_id: str, *, session: str = SESSION, correlation: str = CORRELATION, seq: int = 0
) -> Event:
    """Build a ``runtime.artifact_emitted`` event scoped to a session (a Candidate)."""
    return Event(
        identifier=f"evt-{session}-artifact-{seq:04d}",
        type=RUNTIME_ARTIFACT_EMITTED,
        version="1",
        timestamp="1970-01-01T00:00:00+00:00",
        producer="runtime",
        correlation_identifier=correlation,
        execution_identifier=None,
        payload={"artifact": artifact_id, "kind": "file"},
        source="nexus_runtime",
    )


def artifact_events(
    artifact_ids: Sequence[str], *, session: str = SESSION, correlation: str = CORRELATION
) -> tuple[Event, ...]:
    """A tuple of artifact-emitted events (the independent artifact record)."""
    return tuple(
        artifact_event(aid, session=session, correlation=correlation, seq=i)
        for i, aid in enumerate(artifact_ids)
    )


def val_work_package(
    identifier: str = "wp-val", *, completion_criteria: Struct | None = None
) -> WorkPackage:
    """A Work Package with optional explicit completion criteria."""
    wp = work_package(identifier)
    if completion_criteria is not None:
        return wp.model_copy(update={"completion_criteria": completion_criteria})
    return wp
