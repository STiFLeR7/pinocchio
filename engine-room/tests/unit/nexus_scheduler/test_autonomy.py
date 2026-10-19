"""P16/B unit — autonomous execution is entirely Policy-governed.

Every mode is mediated by the Policy engine (the sole evaluator): Manual queues without running, Governed
runs and pauses gates for a human, Fully Automatic auto-approves gates (only when Policy permits), and a
Policy deny withholds execution (fail-closed). The autonomy coordinator records provenance but evaluates
no policy itself.
"""

from __future__ import annotations

from nexus_core.contracts.enums import PolicyCategory, PolicyDecision
from nexus_core.contracts.status import PolicyStatus
from nexus_core.domain.policy import Policy
from nexus_human_interaction import build_human_interaction
from nexus_infra import build_infrastructure
from nexus_operations import build_operations
from nexus_scheduler import AutonomyMode, ScheduleTrigger, build_scheduler
from nexus_workflows.spine import spine_reference_request

T0 = "2026-07-21T00:00:00+00:00"


def _platform():
    infra = build_infrastructure()
    hi = build_human_interaction(infra)
    ops = build_operations(hi.spine.coordinator, hi.approval, infra)
    scheduler = build_scheduler(hi.spine, hi.approval, ops, now=lambda: T0).scheduler
    return hi, scheduler


def _deny_autonomy(policy) -> None:
    policy.registry.register(
        Policy(
            identity="policy.autonomy.deny-test",
            version="1",
            purpose="deny autonomous execution (test override)",
            conditions={"attr": "action_class", "op": "eq", "value": "autonomous_execution"},
            decision=PolicyDecision.DENY,
            priority=100,
            owner="governance",
            status=PolicyStatus.ENABLED,
            category=PolicyCategory.GOVERNANCE,
            governed_action_class="autonomous_execution",
        )
    )


def _register(scheduler, autonomy, *, gated=()):
    return scheduler.schedule_goal(
        identity="job",
        request=spine_reference_request(run="job", gated=gated),
        trigger=ScheduleTrigger.one_time(T0),
        autonomy=autonomy,
    )


def test_manual_queues_without_running() -> None:
    _, scheduler = _platform()
    _register(scheduler, AutonomyMode.MANUAL)
    outcome = scheduler.tick(T0)[0]
    assert not outcome.executed and "manual" in outcome.note


def test_governed_runs_and_pauses_at_a_gate_for_a_human() -> None:
    hi, scheduler = _platform()
    _register(scheduler, AutonomyMode.GOVERNED, gated=("review",))
    outcome = scheduler.tick(T0)[0]
    assert outcome.executed and outcome.pipeline_status == "paused"
    assert outcome.auto_granted == ()
    # the gate was surfaced for a human decision (Approval Exchange owns it) — not auto-approved.
    assert [r.node for r in hi.approval.pending("pipe-job-0")] == ["node-review"]


def test_fully_automatic_auto_approves_when_policy_permits() -> None:
    hi, scheduler = _platform()
    _register(scheduler, AutonomyMode.FULLY_AUTOMATIC, gated=("review",))
    outcome = scheduler.tick(T0)[0]
    assert outcome.executed and outcome.pipeline_status == "completed"
    assert outcome.auto_granted == ("node-review",)
    approved = [e for e in hi.spine.coordinator.history() if e.type == "approval.approved"]
    assert approved and all(e.payload.get("decided_by") == "policy-autonomy" for e in approved)


def test_policy_deny_withholds_execution() -> None:
    hi, scheduler = _platform()
    _deny_autonomy(hi.spine.policy)
    _register(scheduler, AutonomyMode.GOVERNED)
    outcome = scheduler.tick(T0)[0]
    assert not outcome.executed and not outcome.policy_allowed
    assert outcome.policy_decision == "deny"
    # nothing ran: no pipeline session was created for this occurrence.
    assert hi.spine.coordinator.session("pipe-job-0").status.value == "running"
