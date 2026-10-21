"""Approval-Exchange value models — the approval lifecycle, request projection, and decision outcome.

The Approval Exchange owns approval *coordination* only. Its durable facts are the ``approval.*`` events;
:class:`ApprovalRequest` is the per-gate projection of that stream and :class:`ApprovalSession` is the
per-pipeline-session projection (INV-13/14 — the log is truth), never a new frozen domain object (INV-07).
:class:`ApprovalLifecycle` is the deterministic state machine ``Requested → Pending → Approved | Denied |
Expired``; :class:`ApprovalDecision` / :class:`ApprovalExplanation` are read-only formatted outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from nexus_core.contracts.base import Reference, ValueObject


class ApprovalLifecycle(StrEnum):
    """The deterministic approval-gate lifecycle (every transition is a durable ``approval.*`` fact).

    ``Requested → Pending → Approved | Denied | Expired`` — Requested/Pending are published when the
    Actuation approval boundary is reached; the terminal state is the operator's recorded decision.
    """

    REQUESTED = "requested"
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


_TERMINAL = frozenset(
    {ApprovalLifecycle.APPROVED, ApprovalLifecycle.DENIED, ApprovalLifecycle.EXPIRED}
)


class ApprovalRequest(ValueObject):
    """The per-gate approval projection — its lifecycle state and the recorded decision, by reference.

    Rebuildable from the ``approval.*`` stream for one gated node: the taxonomy that required it (Policy's
    call, carried by the ExecutionStrategy), the current lifecycle state, and — once decided — who decided
    and why. It is a ``ValueObject`` projection (INV-07); the timestamps are read from the events.
    """

    node: str
    session_ref: Reference
    taxonomy: str
    state: ApprovalLifecycle
    requested_at: str = ""
    decided_at: str | None = None
    decided_by: str | None = None
    reason: str | None = None
    expires_at: str | None = None

    @property
    def is_pending(self) -> bool:
        """Whether this gate is still awaiting an operator decision."""
        return self.state is ApprovalLifecycle.PENDING or self.state is ApprovalLifecycle.REQUESTED

    @property
    def is_decided(self) -> bool:
        """Whether a terminal decision (approved / denied / expired) has been recorded."""
        return self.state in _TERMINAL


class ApprovalSession(ValueObject):
    """The immutable approval-session projection — a deterministic read of ``approval.*`` for one run.

    Records every gate of one pipeline session and its lifecycle state (INV-13/14), so a reopened durable
    log reconstructs the identical approval history and a restart resumes the pending waits exactly.
    """

    identity: str  # the pipeline-session identity (e.g. "pipe-op-arch-r1")
    requests: tuple[ApprovalRequest, ...]

    @property
    def pending(self) -> tuple[ApprovalRequest, ...]:
        """The gates still awaiting a decision (the pending approval queue for this session)."""
        return tuple(request for request in self.requests if request.is_pending)

    @property
    def granted_gates(self) -> tuple[str, ...]:
        """The node ids the operator approved — the gates a resumed run may drive (sorted)."""
        return tuple(sorted(r.node for r in self.requests if r.state is ApprovalLifecycle.APPROVED))

    @property
    def denied_gates(self) -> tuple[str, ...]:
        """The node ids the operator denied (sorted)."""
        return tuple(sorted(r.node for r in self.requests if r.state is ApprovalLifecycle.DENIED))

    def request(self, node: str) -> ApprovalRequest | None:
        """The approval request for one gated node, if the exchange has published it."""
        for request in self.requests:
            if request.node == node:
                return request
        return None


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    """The formatted outcome of an approve / deny / expire — the recorded state, operator-shaped.

    ``resumed`` is true when the decision re-drove the constitutional pipeline (an approval → resume);
    ``pipeline_status`` is the pipeline's status after that resume (``None`` for a record-only decision).
    """

    session_id: str
    node: str
    state: ApprovalLifecycle
    decided_by: str
    reason: str
    resumed: bool
    pipeline_status: str | None = None


@dataclass(frozen=True, slots=True)
class ApprovalExplanation:
    """The read-only explanation of one gate — why approval was required and its current state."""

    session_id: str
    node: str
    taxonomy: str
    state: ApprovalLifecycle
    detail: str
    decided_by: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ApprovalOutcome:
    """The formatted result of a submit-and-publish — the pipeline status plus any pending approvals."""

    session_id: str
    pipeline_status: str
    pending: tuple[ApprovalRequest, ...] = field(default_factory=tuple)

    @property
    def awaiting_approval(self) -> bool:
        """Whether the run paused with at least one gate awaiting an operator decision."""
        return bool(self.pending)
