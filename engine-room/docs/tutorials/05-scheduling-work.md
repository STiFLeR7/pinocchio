# Tutorial 05 — Scheduling Work

## What you'll learn

How Nexus makes time pass on purpose, the difference between one-time and recurring dispatch, and what a
real process restart actually does to scheduled work.

## Concept: nothing fires on a wall clock

This is the single most important operational fact about the Scheduler: **`tick(now)` is the only thing
that makes time pass.** Nothing inside `nexus_scheduler` reads the real clock itself — an operator (or a
host process, like `nexus_scheduler/__main__.py`, the real production entrypoint) calls `tick()`
periodically and passes it the current time explicitly:

```python
scheduler.schedule_goal(
    identity="daily-summary",
    request=spine_reference_request(run="scheduled"),
    trigger=ScheduleTrigger.one_time(...),
    autonomy=AutonomyMode.GOVERNED,
)
outcomes = scheduler.tick(now)
```

This is why the Scheduler is deterministic and replayable in a way a real-wall-clock design couldn't be:
every dispatch decision is a pure function of the durable log plus the `now` value you passed in, never of
"what time is it right now" read from the OS.

## Concept: restart is a real reopen, not a simulation

Because the Scheduler's state lives entirely in the durable event log, a genuine process restart is just:
discard every in-memory object, reopen the same durable file, rebuild the platform, and keep ticking. The
example for this tutorial does exactly that — not a mock of a restart, the actual mechanism.

## Run it

```bash
uv run python examples/06-scheduler/run.py
```

Read [`examples/06-scheduler/README.md`](../../examples/06-scheduler/README.md). Its own notes describe a
real bug this documentation initiative found and fixed while building the example — an early draft
rebuilt the whole platform on every tick instead of only at the genuine restart step, which is exactly the
mistake this tutorial's "Concept" section above is warning you away from.

## What you should see

A one-time schedule firing exactly once, a recurring schedule firing multiple times across separate
`tick()` calls, and — after a genuine restart over the same durable file — the schedule state reconstructed
identically to before the restart.

## Check your understanding

- Why does `AutonomyMode.GOVERNED` (rather than `FULLY_AUTOMATIC`) still make sense for scheduled work?
  (Autonomy controls whether a human is asked before dispatch — it never controls whether Policy is
  consulted. Tutorial 09 covers this distinction directly.)
- What identity does the Scheduler give to the second occurrence of a recurring schedule? (`f"{schedule.
  identity}-{index}"` — derived by the Scheduler itself, never by the caller; see Tutorial 10 for why this
  matters when you look a dispatched session up in Operations.)

## Go deeper

[`docs/v2/P16_AUTONOMY_AND_SCHEDULED_OPERATIONS_REPORT.md`](../v2/P16_AUTONOMY_AND_SCHEDULED_OPERATIONS_REPORT.md);
[`docs/benchmarks/scheduler.md`](../benchmarks/scheduler.md) for how `tick()` performs at scale.

## Next

[Tutorial 06 — Approval Exchange](06-approval-exchange.md)
