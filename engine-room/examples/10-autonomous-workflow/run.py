"""10 - Autonomous Workflow: a Goal that runs itself, end to end, with no human in the loop.

This is the showcase example - everything the previous nine build up to, in one process:
a Goal is registered against the Scheduler with `AutonomyMode.FULLY_AUTOMATIC`, an immediate
trigger fires it on the very next tick, the Policy-mediated autonomy coordinator dispatches
it through the full Constitutional Pipeline without waiting for an operator, and the read-only
Operations plane reports on the result afterward - all over one durable log.

Goal -> Planning -> Actuation -> Validation -> Recovery -> Reflection -> Knowledge -> Operations

`FULLY_AUTOMATIC` does not mean "unchecked": Policy still mediates the dispatch (an operator's
policy can require approval for any action class), and every stage still writes an immutable,
replayable fact. Autonomy here means "no wait for a human," never "no governance."

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

NOW = "2026-01-01T00:00:00+00:00"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = str(Path(tmp) / "example.db")

        infra = build_durable_infrastructure(db_path)
        hi = build_human_interaction(infra)
        operations = build_operations(hi.spine.coordinator, hi.approval, infra)
        scheduler = build_scheduler(hi.spine, hi.approval, operations, now=lambda: NOW).scheduler

        print("Registering a Fully-Automatic goal, due immediately...")
        scheduler.schedule_goal(
            identity="daily-summary",
            request=spine_reference_request(run="autonomous"),
            trigger=ScheduleTrigger.immediate(),
            autonomy=AutonomyMode.FULLY_AUTOMATIC,
        )

        print("Ticking the scheduler once - this is the only thing that makes time pass...")
        outcomes = scheduler.tick(NOW)

        for outcome in outcomes:
            print()
            print(f"schedule:        {outcome.schedule_id}")
            print(f"autonomy:        {outcome.autonomy.value}")
            print(f"executed:        {outcome.executed}   (no operator was asked)")
            print(f"policy allowed:  {outcome.policy_allowed} ({outcome.policy_decision})")

        # The goal ran through the *same* pipeline every other example uses - nothing about
        # the Constitutional Pipeline itself changes when the trigger is a schedule instead
        # of a direct `.run()` call.
        session_id = "daily-summary-0"  # the scheduler's per-occurrence request identity
        summary = operations.service.session_lookup(f"pipe-{session_id}")
        print()
        print("-- Operations plane, after the fact --")
        print(f"session:           pipe-{session_id}")
        print(f"status:            {summary.status if summary else 'not found'}")
        if summary:
            print(f"stages completed:  {summary.stages_completed}")


if __name__ == "__main__":
    main()
