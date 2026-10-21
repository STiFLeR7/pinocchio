"""The Autonomous Execution Coordinator (P16/B) — Policy-mediated dispatch of a due Goal.

Autonomy is *always* mediated by Policy (INV-28). Given a due Goal, this coordinator asks the Policy engine
(the sole evaluator) whether the autonomous execution is permitted, then dispatches accordingly:

- **Manual** — records a request a human must run; never executes autonomously.
- **Governed** — runs the Goal through the Constitutional Pipeline; approval gates pause for a human
  decision (surfaced through the Approval Exchange, which stays the owner of approvals).
- **Fully Automatic** — runs the Goal and, *only when Policy permits*, auto-approves its gates through the
  Approval Exchange (recording the Policy-delegated authorization exactly as a human one).

A policy **deny** withholds execution (fail-closed, INV-30). The coordinator never evaluates policy itself
(it submits a ``DecisionRequest`` and reads the returned verdict — it constructs no verdict of its own),
never plans, executes, validates, or recovers, and drives execution only through the Constitutional
Pipeline (the single execution coordinator — no competing coordinator).
"""

from __future__ import annotations

from dataclasses import replace

from nexus_approval import ApprovalExchange
from nexus_policy import AUTONOMOUS_EXECUTION_ACTION_CLASS, DecisionRequest, PolicyEngine
from nexus_scheduler.model import AutonomyMode, DispatchOutcome
from nexus_workflows.spine import ConstitutionalPipeline, SpineRequest

_AUTONOMY_ACTOR = "policy-autonomy"


class AutonomousExecutionCoordinator:
    """Dispatches a due Goal under Policy governance (records the decision provenance; runs via the pipeline)."""

    def __init__(
        self,
        pipeline: ConstitutionalPipeline,
        approval: ApprovalExchange,
        policy_engine: PolicyEngine,
    ) -> None:
        self._pipeline = pipeline
        self._approval = approval
        self._policy = policy_engine

    def dispatch(
        self,
        request: SpineRequest,
        *,
        autonomy: AutonomyMode,
        occurrence: int,
        occurrence_at: str,
        correlation: str,
        schedule_id: str,
    ) -> DispatchOutcome:
        """Consult Policy, then dispatch the Goal per the autonomy mode (records full provenance)."""
        verdict = self._policy.simulate(
            DecisionRequest(
                action_class=AUTONOMOUS_EXECUTION_ACTION_CLASS,
                correlation_identifier=correlation,
                attributes={"mode": autonomy.value, "schedule": schedule_id},
                governed=True,
            )
        )
        outcome = DispatchOutcome(
            schedule_id=schedule_id,
            occurrence=occurrence,
            occurrence_at=occurrence_at,
            autonomy=autonomy,
            executed=False,
            policy_allowed=verdict.allowed,
            policy_decision=verdict.decision.value,
            reasoning=tuple(verdict.reasoning_trace),
        )

        if autonomy is AutonomyMode.MANUAL:
            return replace(outcome, note="queued for manual execution")
        if not verdict.allowed:
            return replace(outcome, note="withheld by policy (fail-closed)")

        run = self._pipeline.run(request)
        status = run.status.value
        auto_granted: tuple[str, ...] = ()
        waiting = run.execution_state.waiting_nodes if run.execution_state is not None else ()
        if waiting:
            # Surface the gates for a human (Governed) — idempotent even when we then auto-approve.
            self._approval.publish(request.pipeline_session_id, waiting)
            if autonomy is AutonomyMode.FULLY_AUTOMATIC:
                for node in waiting:
                    decision = self._approval.approve(
                        request,
                        node,
                        decided_by=_AUTONOMY_ACTOR,
                        reason="auto-approved by policy (fully automatic)",
                    )
                    status = decision.pipeline_status or status
                auto_granted = tuple(waiting)

        return replace(
            outcome,
            executed=True,
            pipeline_status=status,
            session_id=request.pipeline_session_id,
            auto_granted=auto_granted,
            note="auto-approved" if auto_granted else "governed run",
        )
