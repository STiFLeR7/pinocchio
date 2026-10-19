"""P16 — the Constitutional Scheduler & governed autonomy, end to end.

Proves the whole scheduling surface over the one shared log: one-time / recurring / delayed dispatch, a
restart that never double-dispatches, exact replay reconstruction, Policy-controlled auto-approval,
approval-required (governed) execution surfaced for a human, and scheduled platform operations — all
without changing any ownership (the pipeline runs the Goal, Policy governs, the Approval Exchange approves).
"""

from __future__ import annotations

from dataclasses import replace

from nexus_human_interaction import build_human_interaction, reference_operator_request
from nexus_infra import build_durable_infrastructure, build_infrastructure
from nexus_operations import build_operations
from nexus_scheduler import AutonomyMode, ScheduleStatus, ScheduleTrigger, build_scheduler
from nexus_scheduler.registry import reconstruct_schedule
from nexus_workflows.spine import spine_reference_request

T0 = "2026-07-21T00:00:00+00:00"
T1 = "2026-07-21T01:00:00+00:00"
T2 = "2026-07-21T02:00:00+00:00"


def _platform(infra, now: str = T0):
    hi = build_human_interaction(infra)
    ops = build_operations(hi.spine.coordinator, hi.approval, infra)
    scheduler = build_scheduler(hi.spine, hi.approval, ops, now=lambda: now).scheduler
    return hi, ops, scheduler


def _goal(scheduler, identity, trigger, *, autonomy=AutonomyMode.FULLY_AUTOMATIC, gated=()):
    return scheduler.schedule_goal(
        identity=identity,
        request=spine_reference_request(run=identity, gated=gated),
        trigger=trigger,
        autonomy=autonomy,
    )


def test_one_time_recurring_and_delayed_execution() -> None:
    _, _, scheduler = _platform(build_infrastructure())
    _goal(scheduler, "one", ScheduleTrigger.one_time(T0))
    _goal(scheduler, "rec", ScheduleTrigger.interval(3600, anchor=T0))
    _goal(scheduler, "dly", ScheduleTrigger.delayed(3600))  # anchor = registration T0 → fires at T1

    fired_at_t0 = {(o.schedule_id, o.occurrence) for o in scheduler.tick(T0)}
    assert ("one", 0) in fired_at_t0 and ("rec", 0) in fired_at_t0
    assert ("dly", 0) not in fired_at_t0  # delay not elapsed

    fired_at_t2 = {(o.schedule_id, o.occurrence) for o in scheduler.tick(T2)}
    assert {("rec", 1), ("rec", 2), ("dly", 0)} <= fired_at_t2
    assert scheduler.schedule("one").status is ScheduleStatus.COMPLETED


def test_restart_never_double_dispatches(tmp_path) -> None:
    db = str(tmp_path / "sched.db")
    _, _, first = _platform(build_durable_infrastructure(db))
    _goal(first, "job", ScheduleTrigger.one_time(T0))
    first.tick(T0)

    # A fresh scheduler over the reopened file re-detects the occurrence as already fired — no re-dispatch.
    hi2, _, second = _platform(build_durable_infrastructure(db))
    assert second.tick(T0) == ()
    completed = [
        e
        for e in hi2.spine.coordinator.history()
        if e.type == "pipeline.completed" and e.payload.get("session") == "pipe-job-0"
    ]
    assert len(completed) == 1  # the Goal executed exactly once across the restart


def test_recurring_schedule_occurrences_each_run_their_own_goal() -> None:
    """RC2: every occurrence of a recurring schedule shares one ``correlation_identifier`` by design
    (``Scheduler._dispatch``: ``correlation_identifier=schedule.correlation_identifier or f"cor-{schedule.identity}"``)
    — restart/seed reconstruction must not mistake that shared correlation for "the same goal run" and
    let occurrence 1 silently reuse occurrence 0's already-completed Intent/Plan/ExecutionState.
    """
    infra = build_infrastructure()
    _, _, scheduler = _platform(infra)
    _goal(scheduler, "rec", ScheduleTrigger.interval(3600, anchor=T0, max_occurrences=3))

    scheduler.tick(T0)
    scheduler.tick(T2)

    goals = {e.payload["goal"] for e in infra.event_store.read_all() if e.type == "intent.resolved"}
    plans = {
        e.identifier
        for e in infra.event_store.read_all()
        if e.type == "planning.execution_plan_assembled"
    }
    # Three distinct occurrences → three distinct goals and three distinct plans, not one reused thrice.
    assert goals == {"goal-rec-0", "goal-rec-1", "goal-rec-2"}
    assert len(plans) == 3


def test_replay_reconstructs_scheduling_history(tmp_path) -> None:
    db = str(tmp_path / "replay.db")
    _, _, scheduler = _platform(build_durable_infrastructure(db))
    _goal(scheduler, "rec", ScheduleTrigger.interval(3600, anchor=T0, max_occurrences=3))
    scheduler.tick(T2)

    reopened = build_durable_infrastructure(db)
    schedule = reconstruct_schedule(tuple(reopened.event_store.read_all()), "rec")
    assert schedule is not None
    assert schedule.dispatched == (0, 1, 2)  # identical occurrence history
    assert schedule.status is ScheduleStatus.COMPLETED  # capped recurring completed


def test_policy_controlled_auto_approval() -> None:
    hi, _, scheduler = _platform(build_infrastructure())
    _goal(
        scheduler,
        "auto",
        ScheduleTrigger.one_time(T0),
        autonomy=AutonomyMode.FULLY_AUTOMATIC,
        gated=("review",),
    )
    outcome = scheduler.tick(T0)[0]
    assert outcome.executed and outcome.pipeline_status == "completed"
    assert outcome.auto_granted == ("node-review",)
    assert hi.spine.coordinator.session("pipe-auto-0").status.value == "completed"


def test_approval_required_execution_is_surfaced_then_completed() -> None:
    hi, ops, scheduler = _platform(build_infrastructure())
    _goal(
        scheduler,
        "job",
        ScheduleTrigger.one_time(T0),
        autonomy=AutonomyMode.GOVERNED,
        gated=("review",),
    )
    outcome = scheduler.tick(T0)[0]
    assert outcome.executed and outcome.pipeline_status == "paused"
    assert ops.service.approval_queue().depth == 1  # queued for a human, not auto-approved

    # A human approves through the Approval Exchange — the paused run resumes to completion.
    request = replace(
        spine_reference_request(run="job", gated=("review",)),
        identity="job-0",
        correlation_identifier="cor-job",
    )
    decision = hi.approval.approve(request, "node-review", decided_by="alice", reason="ok")
    assert decision.pipeline_status == "completed"
    assert ops.service.approval_queue().depth == 0


def test_scheduled_operation_execution(tmp_path) -> None:
    db = str(tmp_path / "ops.db")
    hi, ops, scheduler = _platform(build_durable_infrastructure(db))
    hi.facade.submit(reference_operator_request(run="seed"))  # a run for the snapshot to observe
    scheduler.schedule_operation(
        identity="nightly-health", operation="health_snapshot", trigger=ScheduleTrigger.one_time(T0)
    )
    outcome = scheduler.tick(T0)[0]
    assert outcome.operation == "health_snapshot" and "health=healthy" in outcome.note
    # Operations owns the durable snapshot fact; the Scheduler only recorded that it ran.
    assert ops.health.snapshots()
    assert scheduler.schedule("nightly-health").status is ScheduleStatus.COMPLETED
