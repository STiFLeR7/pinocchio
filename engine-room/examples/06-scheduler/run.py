"""06 - Scheduler: one-time and recurring dispatch, then a real restart over the same log.

Nothing fires on a wall clock inside the platform - `tick(now)` is the only thing that makes
time pass, and `now` is always an injected value (never `datetime.now()` inside the platform
itself), so every tick in this example is fully deterministic and reproducible.

Demonstrates:
  - a one-time schedule (fires exactly once, at its `run_at`)
  - a recurring schedule (fires on each interval tick, up to `max_occurrences`)
  - a restart: a *fresh* process rebuilding everything from the same durable SQLite file
  - replay: the restarted process reconstructs identical schedule state, and never
    re-dispatches an occurrence the log already shows as delivered

See README.md in this directory for the full walkthrough.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from nexus_human_interaction import build_human_interaction
from nexus_infra import build_durable_infrastructure
from nexus_operations import build_operations
from nexus_scheduler import AutonomyMode, ScheduleTrigger, build_scheduler
from nexus_workflows.spine import spine_reference_request

T0 = "2026-01-01T00:00:00+00:00"
T1 = "2026-01-01T01:00:00+00:00"
T2 = "2026-01-01T02:00:00+00:00"


def _boot(db_path: str, now: str):
    """Wire the full platform over one durable file - the same shape `nexus_scheduler`'s
    real entrypoint uses, just with an injected fixed clock instead of the real one."""
    infra = build_durable_infrastructure(db_path)
    hi = build_human_interaction(infra)
    ops = build_operations(hi.spine.coordinator, hi.approval, infra)
    scheduler = build_scheduler(hi.spine, hi.approval, ops, now=lambda: now).scheduler
    return scheduler


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    # ignore_cleanup_errors: on Windows, SQLite keeps the file handle open until the
    # connection object is garbage-collected, which can race the temp-dir cleanup below.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = str(Path(tmp) / "example.db")

        # -- "Process 1": register both schedules, then tick twice ----------------------- #
        scheduler = _boot(db_path, now=T0)

        scheduler.schedule_goal(
            identity="onboarding-goal",
            request=spine_reference_request(run="one-time"),
            trigger=ScheduleTrigger.one_time(run_at=T0),
            autonomy=AutonomyMode.FULLY_AUTOMATIC,
        )
        scheduler.schedule_goal(
            identity="daily-report",
            request=spine_reference_request(run="recurring"),
            trigger=ScheduleTrigger.interval(interval_seconds=3600, max_occurrences=2),
            autonomy=AutonomyMode.FULLY_AUTOMATIC,
        )

        outcomes_t0 = scheduler.tick(T0)
        print(f"tick @ {T0}: dispatched {len(outcomes_t0)} occurrence(s)")
        for o in outcomes_t0:
            print(f"  - {o.schedule_id} occurrence #{o.occurrence}: executed={o.executed}")

        # Still "process 1" - the same scheduler object, the clock has simply advanced.
        # (A real process would get T1 from the real clock; nothing here rebuilds anything.)
        outcomes_t1 = scheduler.tick(T1)
        print(f"tick @ {T1}: dispatched {len(outcomes_t1)} occurrence(s)")
        for o in outcomes_t1:
            print(f"  - {o.schedule_id} occurrence #{o.occurrence}: executed={o.executed}")

        # -- "Process 2": a real restart. Fresh objects, same durable file. --------------- #
        restarted = _boot(db_path, now=T2)
        outcomes_t2 = restarted.tick(T2)
        print(f"tick @ {T2} (after restart): dispatched {len(outcomes_t2)} occurrence(s)")
        print("  (the one-time schedule already fired once; the recurring schedule already")
        print("   reached max_occurrences=2 - a restarted process correctly dispatches nothing")
        print("   new here, reconstructed entirely from the durable log, not from memory)")


if __name__ == "__main__":
    main()
