"""P16/A unit — the Scheduler owns timing: register, tick (due-detection + dispatch), and lifecycle.

The Scheduler dispatches each due occurrence exactly once, never re-dispatches (idempotent), and honors the
schedule lifecycle (pause / resume / cancel / complete) — all as a projection of the durable log.
"""

from __future__ import annotations

from nexus_human_interaction import build_human_interaction
from nexus_infra import build_infrastructure
from nexus_operations import build_operations
from nexus_scheduler import AutonomyMode, ScheduleStatus, ScheduleTrigger, build_scheduler
from nexus_workflows.spine import spine_reference_request

T0 = "2026-07-21T00:00:00+00:00"
T2 = "2026-07-21T02:00:00+00:00"


def _scheduler(now: str = T0):
    infra = build_infrastructure()
    hi = build_human_interaction(infra)
    ops = build_operations(hi.spine.coordinator, hi.approval, infra)
    return build_scheduler(hi.spine, hi.approval, ops, now=lambda: now).scheduler


def _register(scheduler, identity="job", *, trigger=None, autonomy=AutonomyMode.GOVERNED):
    return scheduler.schedule_goal(
        identity=identity,
        request=spine_reference_request(run=identity),
        trigger=trigger or ScheduleTrigger.one_time(T0),
        autonomy=autonomy,
    )


def test_register_then_tick_dispatches_the_goal() -> None:
    scheduler = _scheduler()
    _register(scheduler)
    outcomes = scheduler.tick(T0)
    assert len(outcomes) == 1 and outcomes[0].executed
    assert outcomes[0].pipeline_status == "completed"
    assert scheduler.schedule("job").status is ScheduleStatus.COMPLETED


def test_tick_never_double_dispatches() -> None:
    scheduler = _scheduler()
    _register(scheduler)
    assert len(scheduler.tick(T0)) == 1
    assert scheduler.tick(T0) == ()  # the occurrence already fired — idempotent


def test_pause_then_resume() -> None:
    scheduler = _scheduler()
    _register(scheduler)
    scheduler.pause("job")
    assert scheduler.tick(T0) == () and scheduler.schedule("job").status is ScheduleStatus.PAUSED
    scheduler.resume("job")
    assert len(scheduler.tick(T0)) == 1  # the missed occurrence fires on resume
    assert scheduler.schedule("job").status is ScheduleStatus.COMPLETED


def test_cancel_stops_a_schedule() -> None:
    scheduler = _scheduler()
    _register(scheduler)
    scheduler.cancel("job")
    assert scheduler.tick(T0) == ()
    assert scheduler.schedule("job").status is ScheduleStatus.CANCELLED


def test_recurring_dispatches_every_due_occurrence() -> None:
    scheduler = _scheduler()
    _register(scheduler, "rec", trigger=ScheduleTrigger.interval(3600, anchor=T0))
    outcomes = scheduler.tick(T2)
    assert [o.occurrence for o in outcomes] == [0, 1, 2]
    assert all(o.executed for o in outcomes)
    assert scheduler.schedule("rec").status is ScheduleStatus.ACTIVE  # still recurring


def test_read_surface_and_health() -> None:
    scheduler = _scheduler()
    _register(scheduler, "once")
    _register(scheduler, "rec", trigger=ScheduleTrigger.interval(3600, anchor=T0))
    scheduler.tick(T0)  # 'once' completes at occurrence 0; 'rec' fires occurrence 0
    health = scheduler.health(T2)
    assert health.completed == 1 and health.active == 1
    assert health.dispatched_total == 2 and health.denied_total == 0
    assert scheduler.upcoming(T2) and scheduler.upcoming(T2)[0].identity == "rec"
    assert {s.identity for s in scheduler.schedules()} == {"once", "rec"}
