"""Operations-Plane value models — read-only projections of the one shared log (observation only).

The Operations Plane *observes*; it never controls execution and produces no Supervision ``Observation``
domain object (INV-11 stays with Supervision). These are read-only formatted projections — session,
approval-queue, runtime, replay/restart inventories, diagnostics, and a health summary — each a pure
function of the durable log, plus the ``operations.snapshot`` it may record as instrumentation.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SessionSummary:
    """One pipeline session, operator-shaped: its status, stage progression, and pending approvals."""

    session_id: str
    status: str
    current_stage: str | None
    stages_completed: tuple[str, ...]
    pending_approvals: int
    is_paused: bool


@dataclass(frozen=True, slots=True)
class ExecutionStatusView:
    """The execution status of one session — whether traversal finished and any gates still waiting."""

    session_id: str
    pipeline_status: str
    actuation_complete: bool
    waiting_gates: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ApprovalQueueView:
    """The cross-session approval queue — every gate awaiting a decision plus the queue depth."""

    pending: tuple[tuple[str, str, str], ...]  # (session_id, node, taxonomy)

    @property
    def depth(self) -> int:
        """The number of gates awaiting an operator decision across all sessions."""
        return len(self.pending)


@dataclass(frozen=True, slots=True)
class RuntimeInventory:
    """The runtimes seen on the log and a coarse utilization count (node dispatches)."""

    runtimes: tuple[str, ...]
    utilization: int


@dataclass(frozen=True, slots=True)
class ReplayInventory:
    """The sessions replayable from the durable log and the total event count backing them."""

    sessions: tuple[str, ...]
    total_events: int


@dataclass(frozen=True, slots=True)
class RestartInventory:
    """The paused sessions a restart can resume and the pending-approval depth blocking them."""

    resumable: tuple[str, ...]
    pending_approvals: int


@dataclass(frozen=True, slots=True)
class Diagnostics:
    """Deterministic diagnostics over the log — event counts and a consistency verdict."""

    total_events: int
    by_producer: tuple[tuple[str, int], ...]
    by_type: tuple[tuple[str, int], ...]
    consistent: bool
    issues: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class HealthSummary:
    """The platform health summary — liveness plus the operational counters (instrumentation only)."""

    liveness: str  # "healthy" | "degraded"
    active_sessions: int
    pending_approvals: int
    completed_approvals: int
    queue_depth: int
    runtime_utilization: int
    policy_decisions: int
    pipeline_states: tuple[tuple[str, int], ...]  # (status, count)
    verdict: str

    @property
    def is_healthy(self) -> bool:
        """Whether the platform is in a healthy operational state."""
        return self.liveness == "healthy"


@dataclass(frozen=True, slots=True)
class OperationsSnapshot:
    """A recorded point-in-time health snapshot (persisted as an ``operations.snapshot`` fact)."""

    identity: str
    summary: HealthSummary
    recorded_at: str
