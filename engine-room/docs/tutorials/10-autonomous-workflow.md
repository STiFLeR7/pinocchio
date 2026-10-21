# Tutorial 10 — Building Your First Autonomous Workflow

## What you'll learn

How every mechanism from Tutorials 03–09 composes into one real, no-human-in-the-loop workflow — and why
"autonomous" in Nexus never means "ungoverned."

## Concept: autonomy means no waiting for a human, never no governance

`AutonomyMode` has three tiers — `MANUAL`, `GOVERNED`, `FULLY_AUTOMATIC` — and the tier only controls
whether a human is asked before dispatch. It never removes the Policy Engine from the loop:

```python
scheduler.schedule_goal(
    identity="daily-summary",
    request=spine_reference_request(run="autonomous"),
    trigger=ScheduleTrigger.immediate(),
    autonomy=AutonomyMode.FULLY_AUTOMATIC,
)
outcomes = scheduler.tick(NOW)
```

The `AutonomousExecutionCoordinator` still asks Policy whether the dispatch is allowed
(`outcome.policy_allowed`, `outcome.policy_decision`) before the pipeline ever runs — a `FULLY_AUTOMATIC`
schedule with a Policy `Deny` simply never dispatches, exactly as governance intends. This is the same
Policy Engine from Tutorial 09, the same Scheduler from Tutorial 05, applied together.

## What this composes

| Piece | From |
|---|---|
| Registering timed, autonomous dispatch | Tutorial 05 (Scheduling Work) |
| Fail-closed governance mediating every dispatch | Tutorial 09 (Policy Authoring) |
| Observing the result afterward, without re-running it | Tutorial 03 (Constitutional Pipeline / Operations) |
| Recording what was learned | Tutorial 04 (Memory) |
| What would happen if the runtime failed | Tutorial 07 (Recovery) |
| A human gate, if one were added | Tutorial 06 (Approval Exchange) |

## Run it

```bash
uv run python examples/10-autonomous-workflow/run.py
```

Read [`examples/10-autonomous-workflow/README.md`](../../examples/10-autonomous-workflow/README.md) — the
showcase example every prior tutorial has been building toward.

## What you should see

`executed: True` with no operator involved, `policy allowed: True (allow)` proving governance was still
consulted, and an Operations-plane lookup afterward (`pipe-daily-summary-0` — the Scheduler's own
occurrence-numbering pattern from Tutorial 05) showing all nine stages completed.

## Check your understanding

- If Policy had denied this dispatch, would the schedule disappear? (No — it stays registered and due, it
  simply doesn't execute; this is the same "denied is a normal, recorded outcome, not an error" pattern
  Tutorial 06 and Tutorial 07 both already showed you.)
- Does the pipeline behave any differently when invoked through the Scheduler versus directly (as in
  Tutorial 02)? (No — this is the point: the pipeline doesn't know or care whether it was invoked directly
  or through the Scheduler. Composability, not a special "autonomous mode" code path.)

## Go deeper

[`docs/architecture/README.md`](../architecture/README.md)'s Scheduler section;
[`docs/v2/P16_AUTONOMY_AND_SCHEDULED_OPERATIONS_REPORT.md`](../v2/P16_AUTONOMY_AND_SCHEDULED_OPERATIONS_REPORT.md).

## What's next

You've completed the tutorial series. From here:

- [`docs/development/CONTRIBUTING.md`](../development/CONTRIBUTING.md) — turn what you've learned into a
  pull request.
- [`docs/architecture/README.md`](../architecture/README.md) — the full design behind everything you just
  ran.
- [`docs/benchmarks/README.md`](../benchmarks/README.md) — what's actually been measured about the
  platform you now know how to use.
