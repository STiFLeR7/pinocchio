# Benchmark: Scheduler `tick()` Throughput

## Purpose

Measure how `Scheduler.tick()` — the one call that makes time pass for every registered schedule
(`docs/v2/OPERATOR_GUIDE.md`: "`tick(now)` is the only thing that makes time pass") — scales as the number
of registered schedules grows. This is the one benchmark in this evidence base that a real defect was
found and fixed against, not a passive measurement.

## Methodology

`scripts/p17_scale.py`, single-machine, single-run per data point. Each row registers *N* schedules (a mix
of one-time, recurring, and delayed triggers, matching P17's original scale-test design) against a fresh
`Scheduler`, then times one `tick(now)` call. P17 established the methodology and the 10/100/500 data
points; RC1 re-ran the identical script, unmodified, against the fixed code, and added the 1000/2000 points
P17 had only projected or not measured.

**Environment:** not separately recorded beyond "single-machine, single-run" in both source reports —
neither report states CPU/OS/Python build specifics for this script. Treat absolute millisecond values as
order-of-magnitude, not calibrated hardware numbers; the shape (linear vs. quadratic) is the load-bearing
result, not the exact timings.

## Measured Result

| Registered schedules | P17 (before fix) | RC1 (after fix) | Improvement |
|---|---|---|---|
| 10 | 0.5 ms | 0.09 ms | ~6x |
| 100 | 43.1 ms | 0.66 ms | ~65x |
| 500 | 1136.6 ms | 3.29 ms | ~345x |
| 1000 | ~9.6 s (P17 documented this projection; not directly re-measured at this count in P17's own script run) | 6.8 ms | >1000x |
| 2000 | not measured in P17 | 14.4 ms | — |

**Growth shape** (the actual finding, not just the absolute numbers):

- **Before (P17):** consistent with O(n²) — 10→100 schedules (10x growth) cost ~80x more time; 100→500
  (5x growth) cost ~26x more time. Both are super-linear, matching a quadratic model.
- **After (RC1):** consistent with linear scaling — 500→1000 (2x growth) cost ~2x more time; 1000→2000 (2x
  growth) cost ~2.1x more time. Both track their input growth almost exactly.

## Source Report

`docs/v2/RC1_PRODUCTIZATION_REPORT.md` §3 (root cause and fix), §6.1 (the table above, reproduced exactly).
The "before" column is P17's own number, cited by RC1 for direct comparison — not independently re-derived
by this benchmark documentation phase.

## Interpretation

The root cause (`docs/v2/RC1_PRODUCTIZATION_REPORT.md` §3.1) was a real algorithmic defect, not a tuning
opportunity: `tick()`'s outer loop already reconstructed every schedule in one O(events) pass, but then
called `_maybe_complete()` per schedule, which **re-fetched and re-reconstructed the entire schedule
history again** just to find the one schedule it already had — an extra O(events) pass per schedule, or
O(n·events) total, which becomes O(n²) once event count scales with schedule count. The fix removed the
redundant re-fetch entirely (`_maybe_complete` now receives the schedule it needs directly from the outer
loop) — an O(1)-per-schedule change with **no behavioral change**: same dispatch order, same completion
semantics, same replay/restart guarantees, confirmed by all 28 pre-existing scheduler tests passing
unchanged before any new test was added.

This matters operationally, not just as a speed number: an O(n²) `tick()` is a governance risk, not merely
an inconvenience — a Scheduler that takes 9.6 seconds to process 1000 schedules is a Scheduler that can miss
its own tick interval under real autonomous load, which is a correctness-adjacent failure mode (delayed or
skipped dispatch), not just a slow one.

## Limitations

- **Single-run, single-machine.** No statistical distribution (mean/p50/p99) was collected — each row is
  one timed call.
- **2,000 schedules is the largest measured scale.** No claim is made about behavior at 10,000, 100,000, or
  any higher count — see the top-level [`README.md`](README.md#what-nexus-has-not-benchmarked)'s "million-job
  scheduling" entry.
- **The schedule mix (one-time/recurring/delayed) is P17's original synthetic mix**, not a measured
  production workload — no real deployment's schedule distribution has ever been sampled.
- **This is `tick()` cost alone**, not end-to-end dispatch-through-Knowledge latency for the goals a tick
  fires — see [`persistence-and-replay.md`](persistence-and-replay.md) for per-pipeline-run costs.
