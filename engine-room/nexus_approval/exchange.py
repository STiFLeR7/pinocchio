"""The Constitutional Approval Exchange (P15) — sole owner of approval *coordination*.

:class:`ApprovalExchange` completes the governance loop around approval-gated execution. Execution
Actuation already pauses at an approval boundary (a gated node left WAITING); the exchange publishes the
approval request, awaits the operator's decision, records it as immutable audit (durable ``approval.*``
facts, INV-29), and — on approval — resumes execution by re-driving the **Constitutional Pipeline** with
the now-granted gate. It owns exactly the lifecycle ``Requested → Pending → Approved | Denied | Expired``.

It is deliberately *not* a coordinator of anything else: it never evaluates policy (Policy owns that,
INV-28 — the taxonomy that required the gate is the ExecutionStrategy's, authored by Planning/EI), never
executes work (Actuation owns traversal, INV-23 — the exchange hands resumption to the pipeline, which
drives Actuation), never plans, reasons, validates, or recovers. Its only sanctioned collaborator is the
Constitutional Pipeline (the single execution coordinator — no competing coordinator) and the shared
durable log; it imports no engine.
"""

from __future__ import annotations

from collections.abc import Callable

from nexus_approval import events as aevents
from nexus_approval.model import (
    ApprovalDecision,
    ApprovalExplanation,
    ApprovalLifecycle,
    ApprovalRequest,
    ApprovalSession,
)
from nexus_approval.observability import ApprovalObservability
from nexus_approval.session import reconstruct_approval_session
from nexus_core.contracts.base import Struct
from nexus_core.contracts.enums import ApprovalTaxonomy
from nexus_core.domain.event import Event
from nexus_infra import InfrastructureContext, content_hash
from nexus_workflows.spine import (
    ConstitutionalPipeline,
    SpineControl,
    SpineRequest,
    SpineRun,
    find_plan,
)


class ApprovalExchange:
    """Coordinates the approval-decision lifecycle over one shared durable log (records + resumes only)."""

    def __init__(
        self,
        pipeline: ConstitutionalPipeline,
        infrastructure: InfrastructureContext,
        *,
        now: Callable[[], str] | None = None,
        observability: ApprovalObservability | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._infra = infrastructure
        self._now = now or aevents.system_now
        self._obs = observability or ApprovalObservability(infrastructure.observability)

    # -- publish (derive requests from the Actuation approval boundary) ------- #

    def publish(
        self,
        session_id: str,
        waiting: tuple[str, ...],
        *,
        expires_at: str | None = None,
        human_required: tuple[str, ...] = (),
    ) -> tuple[ApprovalRequest, ...]:
        """Publish an approval request for each waiting gate not yet published; return the pending queue.

        ``waiting`` are the gate node ids Actuation left awaiting approval (from the paused run's
        ExecutionState). Publishing is idempotent — a gate already in the lifecycle is not re-published.
        """
        events = self._history()
        already = {
            request.node for request in reconstruct_approval_session(events, session_id).requests
        }
        taxonomy = self._taxonomy(events)
        correlation = self._correlation(events, session_id)
        for node in waiting:
            if node in already:
                continue
            self._emit(
                session_id,
                f"{node}-requested",
                aevents.APPROVAL_REQUESTED,
                correlation,
                {
                    "node": node,
                    "taxonomy": "human_review" if node in human_required else taxonomy,
                    "expires_at": expires_at,
                },
            )
            self._emit(
                session_id, f"{node}-pending", aevents.APPROVAL_PENDING, correlation, {"node": node}
            )
            self._obs.requested()
        return self.pending(session_id)

    # -- decide (record the operator's authorization as immutable audit) ------ #

    def approve(
        self,
        request: SpineRequest,
        node: str,
        *,
        decided_by: str = "operator",
        reason: str = "",
    ) -> ApprovalDecision:
        """Record an approval and resume: re-drive the pipeline with the now-granted gate (INV-23)."""
        decision, _ = self.approve_with_run(request, node, decided_by=decided_by, reason=reason)
        return decision

    def approve_with_run(
        self,
        request: SpineRequest,
        node: str,
        *,
        decided_by: str = "operator",
        reason: str = "",
    ) -> tuple[ApprovalDecision, SpineRun]:
        """Resume an approved run and return its outcome to the façade for response recording."""
        session_id = request.pipeline_session_id
        self._decide(session_id, node, aevents.APPROVAL_APPROVED, decided_by, reason)
        self._obs.approved()
        granted = self.session(session_id).granted_gates  # all approvals so far (this one included)
        run = self._pipeline.run(request, control=SpineControl(granted_gates=granted))
        decision = ApprovalDecision(
            session_id=session_id,
            node=node,
            state=ApprovalLifecycle.APPROVED,
            decided_by=decided_by,
            reason=reason,
            resumed=True,
            pipeline_status=run.status.value,
        )
        return decision, run

    def deny(
        self, session_id: str, node: str, *, decided_by: str = "operator", reason: str = ""
    ) -> ApprovalDecision:
        """Record a denial — the gated node is not authorized and execution does not resume for it."""
        self._decide(session_id, node, aevents.APPROVAL_DENIED, decided_by, reason)
        self._obs.denied()
        return ApprovalDecision(
            session_id=session_id,
            node=node,
            state=ApprovalLifecycle.DENIED,
            decided_by=decided_by,
            reason=reason,
            resumed=False,
        )

    def expire(
        self, session_id: str, node: str, *, decided_by: str = "system", reason: str = "expired"
    ) -> ApprovalDecision:
        """Record an expiry — a pending approval timed out; the gate stays un-authorized."""
        self._decide(session_id, node, aevents.APPROVAL_EXPIRED, decided_by, reason)
        self._obs.expired()
        return ApprovalDecision(
            session_id=session_id,
            node=node,
            state=ApprovalLifecycle.EXPIRED,
            decided_by=decided_by,
            reason=reason,
            resumed=False,
        )

    def sweep_expired(self, session_id: str, *, now: str) -> tuple[str, ...]:
        """Expire every pending approval whose deadline has passed (ISO-8601 is order-preserving)."""
        expired: list[str] = []
        for request in self.pending(session_id):
            if request.expires_at is not None and now >= request.expires_at:
                self.expire(session_id, request.node, reason="deadline")
                expired.append(request.node)
        return tuple(expired)

    # -- read-only projections (the log is truth) ---------------------------- #

    def session(self, session_id: str) -> ApprovalSession:
        """Reconstruct one session's full approval history from the durable ``approval.*`` log."""
        return reconstruct_approval_session(self._history(), session_id)

    def pending(self, session_id: str) -> tuple[ApprovalRequest, ...]:
        """The gates still awaiting an operator decision (the session's pending approval queue)."""
        return self.session(session_id).pending

    def history(self, session_id: str) -> tuple[ApprovalRequest, ...]:
        """The full decision history for the session — every gate and its recorded lifecycle state."""
        return self.session(session_id).requests

    def explanation(self, session_id: str, node: str) -> ApprovalExplanation:
        """Explain why a gate required approval and its current lifecycle state (read-only)."""
        request = self.session(session_id).request(node)
        if request is None:
            return ApprovalExplanation(
                session_id=session_id,
                node=node,
                taxonomy="",
                state=ApprovalLifecycle.REQUESTED,
                detail=f"no approval was requested for node '{node}'",
            )
        return ApprovalExplanation(
            session_id=session_id,
            node=node,
            taxonomy=request.taxonomy,
            state=request.state,
            detail=(
                f"node '{node}' requires '{request.taxonomy}' approval "
                f"(per the ExecutionStrategy); currently {request.state.value}"
            ),
            decided_by=request.decided_by,
            reason=request.reason,
        )

    # -- internals ----------------------------------------------------------- #

    def _decide(
        self, session_id: str, node: str, event_type: str, decided_by: str, reason: str
    ) -> None:
        correlation = self._correlation(self._history(), session_id)
        suffix = event_type.split(".")[-1]
        self._emit(
            session_id,
            f"{node}-{suffix}",
            event_type,
            correlation,
            {"node": node, "decided_by": decided_by, "reason": reason},
        )

    def _taxonomy(self, events: tuple[Event, ...]) -> str:
        plan = find_plan(events)
        if plan is None:
            return ApprovalTaxonomy.HUMAN_REVIEW.value
        return plan.execution_strategy.approval_policy.value

    def _correlation(self, events: tuple[Event, ...], session_id: str) -> str:
        for event in events:
            if str(event.payload.get("session", "")) == session_id and event.correlation_identifier:
                return event.correlation_identifier
        return f"cor-{session_id}"

    def _history(self) -> tuple[Event, ...]:
        return self._pipeline.history()

    def _emit(
        self, session_id: str, suffix: str, event_type: str, correlation: str, payload: Struct
    ) -> None:
        full: Struct = {"session": session_id, **payload}
        identifier = f"evt-{session_id}-{suffix}-{content_hash(full)[:16]}"
        self._infra.emit(
            aevents.build_event(identifier, event_type, correlation, full, self._now())
        )
