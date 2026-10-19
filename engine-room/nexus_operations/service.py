"""The Operations service — read-only projections of the platform from the one shared log (P15).

:class:`OperationsService` observes; it never controls execution and never mutates an engine. Every method
is a deterministic projection of the durable log (via the pipeline's read-only inspection surface and the
Approval Exchange's read-only surface) — active sessions, pipeline/execution status, the approval queue,
runtime/replay/restart inventories, and event lookup. It invokes no ``run`` / ``approve`` / ``actuate``.
"""

from __future__ import annotations

from nexus_approval import ApprovalExchange
from nexus_core.domain.event import Event
from nexus_operations.model import (
    ApprovalQueueView,
    ExecutionStatusView,
    ReplayInventory,
    RestartInventory,
    RuntimeInventory,
    SessionSummary,
)
from nexus_workflows.spine import (
    PIPELINE_PRODUCER,
    ConstitutionalPipeline,
    PipelineSession,
    SpineStage,
    reconstruct_pipeline_session,
)

_PAUSED = "paused"


class OperationsService:
    """Deterministic read-only projections of the platform (observation only — no execution control)."""

    def __init__(self, pipeline: ConstitutionalPipeline, approval: ApprovalExchange) -> None:
        self._pipeline = pipeline
        self._approval = approval

    # -- session views ------------------------------------------------------- #

    def active_sessions(self) -> tuple[SessionSummary, ...]:
        """Every pipeline session on the log, with status, stage progression, and pending approvals."""
        events = self._pipeline.history()
        return tuple(self._summary(session_id, events) for session_id in session_ids(events))

    def session_lookup(self, session_id: str) -> SessionSummary | None:
        """One session's summary, or ``None`` if the session is not on the log."""
        events = self._pipeline.history()
        if session_id not in session_ids(events):
            return None
        return self._summary(session_id, events)

    def pipeline_lookup(self, session_id: str) -> PipelineSession:
        """The full pipeline-session projection (stage lineage), reconstructed from the log."""
        return self._pipeline.session(session_id)

    def execution_lookup(self, session_id: str) -> ExecutionStatusView:
        """The execution status of one session — traversal completion and any waiting approval gates."""
        session = self._pipeline.session(session_id)
        waiting = tuple(request.node for request in self._approval.pending(session_id))
        return ExecutionStatusView(
            session_id=session_id,
            pipeline_status=session.status.value,
            actuation_complete=session.completed(SpineStage.ACTUATION),
            waiting_gates=waiting,
        )

    # -- queues + inventories ------------------------------------------------ #

    def approval_queue(self) -> ApprovalQueueView:
        """The cross-session pending-approval queue (session, node, taxonomy), deterministically ordered."""
        events = self._pipeline.history()
        pending: list[tuple[str, str, str]] = []
        for session_id in session_ids(events):
            for request in self._approval.pending(session_id):
                pending.append((session_id, request.node, request.taxonomy))
        return ApprovalQueueView(pending=tuple(sorted(pending)))

    def runtime_inventory(self) -> RuntimeInventory:
        """The runtimes assigned across the log and a coarse utilization count (node dispatches)."""
        events = self._pipeline.history()
        runtimes: set[str] = set()
        utilization = 0
        for event in events:
            identifier = _runtime_identifier(event)
            if identifier is not None:
                runtimes.add(identifier)
                utilization += 1
        return RuntimeInventory(runtimes=tuple(sorted(runtimes)), utilization=utilization)

    def runtime_lookup(self, session_id: str) -> tuple[tuple[str, str], ...]:
        """The (node, runtime) assignments for one session, matched by correlation (sorted)."""
        events = self._pipeline.history()
        correlation = _correlation_of(events, session_id)
        assignments: set[tuple[str, str]] = set()
        for event in events:
            if event.correlation_identifier != correlation:
                continue
            identifier = _runtime_identifier(event)
            if identifier is not None:
                assignments.add((str(event.payload.get("node", "")), identifier))
        return tuple(sorted(assignments))

    def replay_inventory(self) -> ReplayInventory:
        """The sessions replayable from the durable log and the total event count backing them."""
        events = self._pipeline.history()
        return ReplayInventory(sessions=session_ids(events), total_events=len(events))

    def restart_inventory(self) -> RestartInventory:
        """The paused sessions a restart can resume, plus the pending-approval depth blocking them."""
        events = self._pipeline.history()
        resumable: list[str] = []
        pending = 0
        for session_id in session_ids(events):
            if reconstruct_pipeline_session(events, session_id).status.value == _PAUSED:
                resumable.append(session_id)
                pending += len(self._approval.pending(session_id))
        return RestartInventory(resumable=tuple(resumable), pending_approvals=pending)

    def event_lookup(
        self,
        *,
        producer: str | None = None,
        event_type: str | None = None,
        session: str | None = None,
    ) -> tuple[Event, ...]:
        """A filtered view of the durable log (by producer / type / session) — the audit trail."""
        prefix = f"evt-{session}-" if session is not None else None
        return tuple(
            event
            for event in self._pipeline.history()
            if (producer is None or event.producer == producer)
            and (event_type is None or event.type == event_type)
            and (
                session is None
                or str(event.payload.get("session", "")) == session
                or (prefix is not None and event.identifier.startswith(prefix))
            )
        )

    # -- internals ----------------------------------------------------------- #

    def _summary(self, session_id: str, events: tuple[Event, ...]) -> SessionSummary:
        session = reconstruct_pipeline_session(events, session_id)
        return SessionSummary(
            session_id=session_id,
            status=session.status.value,
            current_stage=session.current_stage,
            stages_completed=session.stages_completed,
            pending_approvals=len(self._approval.pending(session_id)),
            is_paused=session.status.value == _PAUSED,
        )


# -- shared pure projections (deterministic reads of the log) ------------------------- #


def session_ids(events: tuple[Event, ...]) -> tuple[str, ...]:
    """The distinct pipeline-session ids on the log, in first-seen order (deterministic)."""
    seen: list[str] = []
    for event in events:
        if event.producer != PIPELINE_PRODUCER:
            continue
        session = str(event.payload.get("session", ""))
        if session and session not in seen:
            seen.append(session)
    return tuple(seen)


def _runtime_identifier(event: Event) -> str | None:
    """The runtime reference identifier carried by a node-dispatch fact, if any (structural read)."""
    runtime = event.payload.get("runtime")
    if isinstance(runtime, dict):
        identifier = runtime.get("identifier")
        return str(identifier) if identifier is not None else None
    return None


def _correlation_of(events: tuple[Event, ...], session_id: str) -> str:
    for event in events:
        if str(event.payload.get("session", "")) == session_id and event.correlation_identifier:
            return event.correlation_identifier
    return f"cor-{session_id}"
