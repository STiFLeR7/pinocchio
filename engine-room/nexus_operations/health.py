"""The Health inspector — a deterministic platform health summary + durable snapshots (P15).

:class:`HealthInspector` composes the read-only Operations + Diagnostics projections into one
:class:`~nexus_operations.model.HealthSummary` (liveness plus the operational counters) and may record it
as a durable ``operations.snapshot`` fact. It observes only — it derives health from the log and controls
nothing (INV-11 Observations stay with Supervision; this is operator instrumentation).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping

from nexus_approval import ApprovalExchange
from nexus_infra import InfrastructureContext, content_hash
from nexus_operations import events as oevents
from nexus_operations.diagnostics import DiagnosticsService
from nexus_operations.model import HealthSummary, OperationsSnapshot
from nexus_operations.observability import OperationsObservability
from nexus_operations.service import OperationsService
from nexus_workflows.spine import ConstitutionalPipeline

_POLICY_PREFIX = "policy."


class HealthInspector:
    """Derives a deterministic health summary from the shared log and records durable snapshots."""

    def __init__(
        self,
        pipeline: ConstitutionalPipeline,
        approval: ApprovalExchange,
        service: OperationsService,
        diagnostics: DiagnosticsService,
        infrastructure: InfrastructureContext,
        *,
        now: Callable[[], str] | None = None,
        observability: OperationsObservability | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._approval = approval
        self._service = service
        self._diagnostics = diagnostics
        self._infra = infrastructure
        self._now = now or oevents.system_now
        self._obs = observability or OperationsObservability(infrastructure.observability)

    def summary(self) -> HealthSummary:
        """Derive the platform health summary from the log (deterministic; observation only)."""
        events = self._pipeline.history()
        sessions = self._service.active_sessions()
        completed = sum(
            1
            for session in sessions
            for request in self._approval.history(session.session_id)
            if request.is_decided
        )
        pipeline_states = tuple(sorted(Counter(s.status for s in sessions).items()))
        policy_decisions = sum(1 for event in events if event.type.startswith(_POLICY_PREFIX))
        queue_depth = self._service.approval_queue().depth
        diagnostics = self._diagnostics.diagnostics()
        liveness = "healthy" if diagnostics.consistent else "degraded"
        self._obs.inspected()
        return HealthSummary(
            liveness=liveness,
            active_sessions=len(sessions),
            pending_approvals=queue_depth,
            completed_approvals=completed,
            queue_depth=queue_depth,
            runtime_utilization=self._service.runtime_inventory().utilization,
            policy_decisions=policy_decisions,
            pipeline_states=pipeline_states,
            verdict=self._verdict(liveness, len(sessions), queue_depth, diagnostics.issues),
        )

    def record_snapshot(self) -> OperationsSnapshot:
        """Record the current health summary as a durable ``operations.snapshot`` fact."""
        summary = self.summary()
        payload = _dump_summary(summary)
        identifier = f"evt-operations-snapshot-{content_hash(payload)[:16]}"
        timestamp = self._now()
        self._infra.emit(
            oevents.build_event(
                identifier,
                oevents.OPERATIONS_SNAPSHOT,
                oevents.OPERATIONS_PRODUCER,
                payload,
                timestamp,
            )
        )
        self._obs.snapshot()
        return OperationsSnapshot(identity=identifier, summary=summary, recorded_at=timestamp)

    def snapshots(self) -> tuple[OperationsSnapshot, ...]:
        """Every recorded operations snapshot, reconstructed from the log (deterministic)."""
        return tuple(
            OperationsSnapshot(
                identity=event.identifier,
                summary=_load_summary(event.payload),
                recorded_at=event.timestamp,
            )
            for event in self._pipeline.history()
            if event.type == oevents.OPERATIONS_SNAPSHOT
        )

    @staticmethod
    def _verdict(liveness: str, sessions: int, queue_depth: int, issues: tuple[str, ...]) -> str:
        if issues:
            return f"degraded: {'; '.join(issues)}"
        return f"{liveness}: {sessions} session(s), {queue_depth} approval(s) pending"


def _dump_summary(summary: HealthSummary) -> dict[str, object]:
    return {
        "liveness": summary.liveness,
        "active_sessions": summary.active_sessions,
        "pending_approvals": summary.pending_approvals,
        "completed_approvals": summary.completed_approvals,
        "queue_depth": summary.queue_depth,
        "runtime_utilization": summary.runtime_utilization,
        "policy_decisions": summary.policy_decisions,
        "pipeline_states": [list(item) for item in summary.pipeline_states],
        "verdict": summary.verdict,
    }


def _load_summary(payload: Mapping[str, object]) -> HealthSummary:
    states = payload.get("pipeline_states", [])
    pipeline_states = (
        tuple((str(item[0]), _int(item[1])) for item in states if isinstance(item, (list, tuple)))
        if isinstance(states, (list, tuple))
        else ()
    )
    return HealthSummary(
        liveness=str(payload.get("liveness", "")),
        active_sessions=_int(payload.get("active_sessions")),
        pending_approvals=_int(payload.get("pending_approvals")),
        completed_approvals=_int(payload.get("completed_approvals")),
        queue_depth=_int(payload.get("queue_depth")),
        runtime_utilization=_int(payload.get("runtime_utilization")),
        policy_decisions=_int(payload.get("policy_decisions")),
        pipeline_states=pipeline_states,
        verdict=str(payload.get("verdict", "")),
    )


def _int(value: object) -> int:
    return value if isinstance(value, int) else 0
