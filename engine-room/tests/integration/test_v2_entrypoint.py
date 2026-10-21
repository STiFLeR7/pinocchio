"""RC1 Workstream 2 — the v2 production entrypoint (``python -m nexus_scheduler``).

Proves ``nexus_scheduler.__main__``'s ``bootstrap``/``run_service`` actually boot a real durable
constitutional platform and drive a Goal through it — not just that the composition roots it calls are
individually correct (they already are, per every other integration suite), but that *this* wiring does
the same thing across a real durable file and a real service loop.
"""

from __future__ import annotations

from nexus_scheduler import AutonomyMode, ScheduleStatus, ScheduleTrigger
from nexus_scheduler.__main__ import PlatformContext, bootstrap, run_service
from nexus_scheduler.scheduler import Scheduler
from nexus_workflows.spine import spine_reference_request


def test_bootstrap_wires_a_real_durable_platform(tmp_path) -> None:
    db = str(tmp_path / "entry.db")
    platform = bootstrap(db)

    assert isinstance(platform, PlatformContext)
    assert isinstance(platform.scheduler, Scheduler)
    assert platform.scheduler.schedules() == ()
    assert (tmp_path / "entry.db").exists()


def test_run_service_dispatches_a_due_goal_through_the_real_pipeline(tmp_path) -> None:
    db = str(tmp_path / "entry.db")
    platform = bootstrap(db)
    platform.scheduler.schedule_goal(
        identity="goal-1",
        request=spine_reference_request(run="e2e"),
        trigger=ScheduleTrigger.immediate(),
        autonomy=AutonomyMode.FULLY_AUTOMATIC,
    )

    ticks = run_service(platform.scheduler, max_ticks=1, sleep=lambda _seconds: None)

    assert ticks == 1
    schedule = platform.scheduler.schedule("goal-1")
    assert schedule is not None
    assert schedule.status is ScheduleStatus.COMPLETED  # the one immediate occurrence fired and ran
    completed = [
        e
        for e in platform.infrastructure.event_store.read_all()
        if e.type == "pipeline.completed" and e.payload.get("session") == "pipe-goal-1-0"
    ]
    assert len(completed) == 1  # the Goal reached the Constitutional Pipeline and completed


def test_run_service_sleeps_between_ticks_but_not_after_the_last_one(tmp_path) -> None:
    platform = bootstrap(
        str(tmp_path / "idle.db")
    )  # no schedules registered — ticks are all no-ops
    sleeps: list[float] = []

    ticks = run_service(platform.scheduler, tick_interval=0.0, max_ticks=3, sleep=sleeps.append)

    assert ticks == 3
    assert (
        len(sleeps) == 2
    )  # sleeps between ticks 1->2 and 2->3, never a trailing sleep before exit


def test_bootstrap_over_a_reopened_file_reconstructs_the_identical_schedule(tmp_path) -> None:
    db = str(tmp_path / "restart.db")
    first = bootstrap(db)
    first.scheduler.schedule_goal(
        identity="goal-1",
        request=spine_reference_request(run="restart"),
        trigger=ScheduleTrigger.one_time("2099-01-01T00:00:00+00:00"),
        autonomy=AutonomyMode.MANUAL,
    )

    second = bootstrap(db)  # a fresh process reopening the same durable file

    assert second.scheduler.schedule("goal-1") == first.scheduler.schedule("goal-1")
