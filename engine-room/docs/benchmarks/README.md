# Nexus v2 — Benchmarks & Operational Evidence

This page indexes every measured value Nexus v2 has actually produced, across `docs/v2/P17_PRODUCTION_READINESS_REPORT.md`,
`RC1_PRODUCTIZATION_REPORT.md`, `RC2_EXECUTION_IDENTITY_REPORT.md`, `V1_RELEASE_READINESS_REPORT.md`, and
`V2_RELEASE_EXECUTION_REPORT.md`. **Nothing here is a new measurement** — this phase re-published existing,
released evidence with provenance, not new benchmarking work. Every number below cites the report and
section it came from; if you can't find a number's source here, treat it as unverified and check the
report directly rather than trusting this index.

**Methodology, stated once, applies everywhere below** (verbatim from the reports themselves):
single-machine, single-run, order-of-magnitude and shape, not calibrated production SLAs. Run-to-run
variance of ±10–15% is expected and already accounted for in every "unchanged" verdict below. Where a
number was re-measured across reports (P17 → RC1), both figures are shown so the comparison is visible,
not just the final one.

## Index

| Document | Covers |
|---|---|
| [`scheduler.md`](scheduler.md) | `Scheduler.tick()` throughput — the O(n²) → O(n) fix, before/after at every measured scale |
| [`persistence-and-replay.md`](persistence-and-replay.md) | Event throughput, replay, restart, memory, execution latency |
| [`quality-gates.md`](quality-gates.md) | Test counts, mypy --strict, ruff, coverage, wheel build, CI, package count — across P17 → RC1 → RC2 → Release |
| [`guarantees.md`](guarantees.md) | Operational guarantees (determinism, replay, restart, policy enforcement, approval integrity, execution isolation) traced to implementation + validation + report |
| [`validation-matrix.md`](validation-matrix.md) | Capability → Validation Method → Evidence → Report → Release, one row per capability |

## What Nexus measures, and why

Every number in this index answers one of four questions a reader actually needs answered before trusting
the platform operationally:

1. **Does the Scheduler stay usable as registered work grows?** (`scheduler.md`) — the one metric this
   program actually found and fixed a real defect against (P17's O(n²) ceiling).
2. **Is the durable log fast enough that durability isn't a tax nobody can afford?** (`persistence-and-replay.md`)
   — event throughput, replay, and restart at measured scale.
3. **Is the codebase itself trustworthy — typed, linted, tested, buildable?** (`quality-gates.md`) — the
   gates every commit in this program had to pass, not a performance number at all, but evidence of a
   different kind that belongs in the same index.
4. **What does Nexus actually guarantee, and how was that guarantee checked?** (`guarantees.md`,
   `validation-matrix.md`) — the operational claims a reader might otherwise take on faith.

## How the numbers were obtained

All performance figures were produced by two scripts written during P17 and re-run, unmodified in
methodology, at RC1: `scripts/p17_benchmark.py` (micro-benchmarks: pipeline startup, event throughput,
replay, restart, execution latency, memory) and `scripts/p17_scale.py` (scale curves: scheduler tick vs.
registered-schedule count, replay/restart at 20,000 events). Both are single-machine, single-run scripts —
not a load-testing harness, not a CI-gated performance regression suite. Test counts, mypy/ruff/coverage,
and wheel-build verification came from the same commands `.github/workflows/core-ci.yml` runs, executed
directly and re-verified at each release milestone (P17, RC1, RC2, Release Readiness, Release Execution).

## Performance Philosophy

Nexus does not optimize for raw throughput as a primary goal, and this index should not be read as a
performance-marketing page. The order of priority, stated explicitly and consistently across every release
report this phase audited:

1. **Correctness** — evidence-validated outcomes (INV-20: never trust a runtime's self-report), one owner
   per decision (INV-02), fail-closed governance by default.
2. **Determinism** — the same input, replayed against the same durable log, reconstructs the same state,
   every time (ADR-001's projection model).
3. **Governance** — nothing runs, retries, or escalates outside what the Policy Engine authorized.
4. **Replayability** — restart and audit-replay are the same mechanism, not a best-effort feature
   (`docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md` exists entirely because two goals sharing one durable log
   is a correctness question, not a performance one).
5. **Operational integrity** — the platform's own account of what happened (Operations, Knowledge) must
   match what actually happened.

**Raw throughput is downstream of all five, not a competing goal.** The one performance defect this whole
program actually found and fixed — the Scheduler's O(n²) `tick()` — was found and fixed *because* it was on
a path to becoming a correctness-adjacent operational ceiling (a Scheduler too slow to tick is a
governance failure, not just a slow one), not because a throughput target was missed. Every "not yet
measured" item in the next section is honestly labeled as such rather than implied by omission.

## What Nexus Has Not Benchmarked

Stated explicitly, per this phase's own instruction that omission must never be allowed to imply
unsupported capability:

- **Distributed deployment.** Nexus v2 runs as a single process against a single SQLite/WAL file
  (`docs/v2/P17_PRODUCTION_READINESS_REPORT.md`'s own security review: "the only I/O boundary is the
  SQLite file"). No multi-node, multi-process, or distributed configuration has ever been built, let alone
  measured.
- **Horizontal scaling.** There is no load balancer, no shared-nothing worker pool, and no sharding story
  for the event log. Not benchmarked because it does not exist.
- **Multi-node execution.** Every "concurrent goals" measurement in this evidence base is **multiple goals
  in one process, on one durable file** (RC2's own subject) — not multiple nodes, not distributed
  consensus, not network partitions.
- **Million-job scheduling.** The largest Scheduler measurement is 2,000 registered schedules
  (`scheduler.md`). Nothing above that scale has been run. Extrapolating linear-scaling behavior beyond
  2,000 is a hypothesis the reports themselves never test.
- **Stress testing / sustained load.** Every benchmark cited here is a single run at a single point in
  time, not a sustained-load or soak test. No number in this index represents behavior under hours or days
  of continuous operation.
- **Cloud latency.** All measurements are local, single-machine timings. No network round-trip, no managed
  database service, no cross-region latency has ever been measured.
- **Long-running durability.** The largest durable-log measurement is 20,000 events
  (`persistence-and-replay.md`). No test has run the durable store for the volume a long-lived production
  deployment (months of continuous operation) would actually accumulate.

None of the above is disclosed as a defect — greenfield, single-process, single-machine operation is the
platform's actual, disclosed scope today (`docs/v2/RC1_MIGRATION_GUIDE.md`). It is disclosed here because
implying otherwise, by silence, would be exactly the kind of unearned claim this phase exists to prevent.

## Provenance discipline

Every figure in `scheduler.md`, `persistence-and-replay.md`, and `quality-gates.md` is a direct quotation or
faithful transcription of a number that already appears in one of the five source reports — none was
recomputed, rounded differently, or extrapolated. Where a source report itself flags a caveat on a number
(e.g. RC1 §2.5's note that pre-RC2 "concurrent sessions" throughput measurements likely under-counted due
to silent event deduplication), that caveat is carried forward here, not dropped.
