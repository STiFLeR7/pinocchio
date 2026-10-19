# Benchmark: Persistence, Replay, Restart & Execution Latency

## Purpose

Measure the cost of Nexus v2's durability model itself — event throughput (in-memory vs. durable), replay
throughput, restart latency, pipeline startup cost, per-run execution latency, and memory footprint — so a
reader can judge whether the event-sourced, append-only-log design (ADR-001) is a durability tax nobody can
afford, or a manageable, measured cost. Every figure here was re-measured at RC1 against RC1's own fixes
(none of which touch these code paths) purely to confirm no regression, then again referenced unchanged
through Release Readiness and Release Execution.

## Methodology

`scripts/p17_benchmark.py`, single-machine, single-run per metric, built at P17 and re-run unmodified at
RC1. Same caveat as `scheduler.md`: order-of-magnitude and shape, not calibrated production SLAs;
run-to-run variance of ±10–15% is expected and already reflected in the "confirmed unchanged" verdicts
below (a ~3% or ~6% delta between P17 and RC1 on an unrelated code path is noise, not drift).

**Environment:** not separately recorded beyond "single-machine, single-run" in either source report.

## Measured Result

All rows below are **confirmed unchanged in shape between P17 and RC1** — RC1 touched none of these code
paths (its only change was the Scheduler fix in `scheduler.md`); the re-measurement exists purely as a
regression check.

| Metric | P17 | RC1 (re-measured) |
|---|---|---|
| Pipeline startup — in-memory | 0.03 ms | 0.03 ms |
| Pipeline startup — durable (fresh file) | 8.2 ms | 7.0 ms |
| Pipeline startup — full spine wiring | 0.7 ms | 0.73 ms |
| Event throughput — in-memory (2000 events / 1 txn) | 140,677/sec | 145,072/sec |
| Event throughput — durable (2000 events / 1 txn) | 16,709/sec | 17,389/sec |
| Persistence overhead (durable vs. in-memory) | 8.4x | 8.3x |
| Event throughput — durable (200 txns × 1 event each) | 2,246/sec | 2,503/sec |
| Replay throughput (2,200 events) | 155,335/sec | 170,989/sec |
| Restart latency (2,200 events) | 15.5 ms | 15.35 ms |
| Execution latency (single-node) | 0.78 ms | 0.72 ms |
| Autonomous execution overhead (vs. a direct run) | ~no measurable delta | ~no measurable delta (-11%, within noise) |
| Memory — 5,000 in-memory events | 10.0 MiB | 10.0 MiB |
| Memory — one full spine run | 0.5 MiB | 0.54 MiB |
| Replay at scale (20,000 events) | not measured at this scale in P17's own run | **92,742 events/sec, 215.7 ms** |
| Restart at scale (20,000 events) | not measured at this scale in P17's own run | **180.9 ms** |

### A performance number RC2 added independently (not from `p17_benchmark.py`)

RC2's execution-identity fixes (see [`guarantees.md`](guarantees.md) for what they actually changed)
touched the pipeline's own hot path, so RC2 ran its own targeted before/after comparison, isolated to that
change:

| | pre-fix | post-fix |
|---|---|---|
| Full pipeline run (`build_infrastructure` + `spine_reference_request` + full 9-stage run), 30 iterations | 4.16 ms/run | 4.41 ms/run |

The ~6% delta is explicitly characterized in the source report as within run-to-run noise for a ~4ms
operation on a single-run timing methodology (not a tight loop with warmup) — not a regression.

## Source Reports

`docs/v2/RC1_PRODUCTIZATION_REPORT.md` §6.2 (the main table); `docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md`
§8 (the pipeline-run delta table). Both explicitly re-cite P17's own original figures for comparison, which
this document reproduces unchanged.

## Interpretation

Two structural facts, not just numbers, matter more than any single figure:

- **Durability has a real, bounded, measured cost — roughly 8x on raw event-write throughput** (145,072/sec
  in-memory vs. 17,389/sec durable) — not an unbounded or unknown one. A reader deciding whether to run
  against `build_durable_infrastructure` vs. in-memory `build_infrastructure` (see `examples/06-scheduler/`
  and `examples/08-replay/`) has an actual number to reason from.
- **Replay and restart are fast enough to be a real operational mechanism, not a theoretical one**: 20,000
  events reconstruct in ~216 ms and a full restart from that scale takes ~181 ms — both fast enough that
  "replay from the log" is a genuine recovery path, not something a reader should assume is too slow to use
  in practice.

## Limitations

- **20,000 events is the largest scale measured for replay/restart.** No claim is made about behavior at
  200,000 or 2,000,000 events — see [`README.md`](README.md#what-nexus-has-not-benchmarked)'s "long-running
  durability" entry.
- **All throughput/latency numbers are single-process, single-machine, SQLite/WAL** — no measurement exists
  for any other durable backend, any network-attached storage, or any multi-process contention scenario.
- **"Autonomous execution overhead ~no measurable delta" is a noise-floor observation, not a proof of zero
  cost** — both source reports describe it exactly that way (a -11% delta is itself noise, in the same
  direction a genuinely-zero-cost path would produce, but not distinguishable from one with real overhead
  below this methodology's resolution).
- **RC2's own pipeline-run number (4.16→4.41 ms) is unrelated to `p17_benchmark.py`'s methodology** — it is
  a separate, narrower A/B measurement RC2 constructed specifically to check its own fix, reported here for
  completeness, not as part of the P17/RC1 benchmark suite proper.
