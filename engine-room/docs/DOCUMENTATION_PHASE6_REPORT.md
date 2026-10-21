# Documentation Phase 6 Report — Benchmarks, Performance & Operational Evidence

**Status: Complete. No implementation change was made and no new measurement was run.** Every number in
`docs/benchmarks/` is a direct quotation or faithful transcription of a figure that already existed in one
of the five source reports named below. This phase's job was provenance and organization, not measurement.

---

## 1. Benchmark Audit

Every measured value produced during P17, RC1, RC2, Release Readiness, and Release Execution was
identified by reading all five reports in full. Inventory, by category:

| Category | Measurements found | Where documented now |
|---|---|---|
| Scheduler throughput | `tick()` cost at 10/100/500/1000/2000 registered schedules, before (P17) and after (RC1) the O(n²)→O(n) fix | `docs/benchmarks/scheduler.md` |
| Persistence / event throughput | In-memory vs. durable event write throughput, persistence overhead multiplier, pipeline startup cost (3 variants) | `docs/benchmarks/persistence-and-replay.md` |
| Replay validation | Replay throughput at 2,200 and 20,000 events; replay-equivalence and cross-goal replay tests | `docs/benchmarks/persistence-and-replay.md`, `docs/benchmarks/guarantees.md` |
| Restart validation | Restart latency at 2,200 and 20,000 events; restart regression suite results | `docs/benchmarks/persistence-and-replay.md`, `docs/benchmarks/guarantees.md` |
| Execution correctness / deterministic replay | Cross-goal execution-identity fixes and their regression tests (RC2) | `docs/benchmarks/guarantees.md` |
| Recovery validation | Recovery decision determinism (`retry` on evidence-judged failure); `checkpoint_ref=None` gap disclosed, not fixed | `docs/benchmarks/guarantees.md` (Execution isolation entry); `docs/benchmarks/validation-matrix.md` |
| CI metrics | 5-job CI status at the actual tagged merge commit | `docs/benchmarks/quality-gates.md` |
| Test counts | 2927 (P17) → 2934 (RC1) → 3215 (RC2 / Release Readiness / Release Execution) | `docs/benchmarks/quality-gates.md` |
| Type coverage | mypy --strict file counts and error counts across all five milestones | `docs/benchmarks/quality-gates.md` |
| Package count | 30 (P17) → 31 (RC1 onward) | `docs/benchmarks/quality-gates.md` |
| Build verification | Wheel build + artifact package-count inspection at Release Readiness and Release Execution | `docs/benchmarks/quality-gates.md` |

**No additional measurements were invented.** Two numbers that appear in the source reports but are
explicitly *not* full benchmark rows were deliberately excluded from the headline tables and instead
explained in prose, per the "no fabricated numbers, no synthetic marketing benchmarks" mandate:

- The **39 architectural invariants** figure (`CHANGELOG.md` [2.0.0]) is a count of *ratified invariants* in
  `docs/v2/99_ARCHITECTURAL_INVARIANTS.md`, not a benchmark metric — no source report states a standalone
  "N invariant-conformance tests pass" count distinct from the overall test-suite totals. Reporting it as a
  benchmark row would have implied a precision the source material doesn't support; it is instead explained
  in `quality-gates.md`'s Interpretation section.
- P17's **1000-schedule scheduler figure (~9.6s)** is explicitly marked in P17's own report as a documented
  projection, not a number P17's own script directly measured at that exact count. `scheduler.md` preserves
  this distinction in its own table rather than presenting it as an equally-measured data point.

---

## 2. Benchmark Sources

All five required source reports were read in full before any benchmark document was written:

- `docs/v2/P17_PRODUCTION_READINESS_REPORT.md` — the origin of every "before" figure and the original
  benchmark scripts (`scripts/p17_benchmark.py`, `scripts/p17_scale.py`).
- `docs/v2/RC1_PRODUCTIZATION_REPORT.md` — the Scheduler fix and its re-measurement; the persistence/replay
  re-measurement (confirming no regression); the restart-safety defects found and fixed; risk #12 (the
  cross-goal defect RC2 exists to close).
- `docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md` — the three cross-goal identity defects, their fixes, and their
  dedicated regression tests; the isolated pipeline-run performance delta.
- `docs/v2/V1_RELEASE_READINESS_REPORT.md` — the pre-commit validation snapshot (test/mypy/ruff/wheel) and
  the full validation-method inventory (replay/restart/scheduler/approval/execution-identity) that seeded
  `validation-matrix.md`.
- `docs/v2/V2_RELEASE_EXECUTION_REPORT.md` — the final, post-merge, post-tag numbers: the one genuinely new
  fact this pass surfaced (`ruff format --check` gap, found and closed at merge time) and the final CI/wheel
  confirmation against the actual `v2.0.0` tag.

`docs/DOCUMENTATION_MASTER_PLAN.md` §6 (this initiative's own earlier benchmark proposal, from Phase 2/3)
and `docs/DOCUMENTATION_PHASE5_REPORT.md` (the immediately preceding phase, establishing ADR/traceability
conventions this phase's `validation-matrix.md` follows the same pattern as) were also read, per this
phase's "Read First" instruction, to keep terminology and structure consistent with the prior four phases.

---

## 3. Operational Guarantees

Seven guarantees documented in full in `docs/benchmarks/guarantees.md`, each with implementation +
validation + report links and an explicitly stated boundary:

1. Deterministic replay
2. Restart correctness
3. Policy enforcement (fail-closed)
4. Approval integrity
5. Scheduler determinism
6. Execution isolation (cross-goal) — the guarantee with the most disclosed remaining risk (RC2 §9's four
   carried-forward items), stated as such rather than presented as unconditionally closed
7. Deterministic scale ceiling removed (Scheduler linear, not quadratic)

No guarantee is stated more strongly than its cited evidence supports. Two guarantees (Approval integrity,
Execution isolation) explicitly note where the supporting evidence is a *trace/audit* rather than a
purpose-built adversarial test, because that is what the source reports themselves say — overstating this
distinction would have violated the phase's "do not overstate guarantees" instruction.

---

## 4. Validation Matrix

`docs/benchmarks/validation-matrix.md` — 20 rows, one per capability, each tracing
**Capability → Validation Method → Evidence → Report → Release**. Every "Evidence" cell names a real test
function, script, or artifact that exists in the repository (spot-checked against source — see §7);
every "Report" cell cites a real section of a released document. No row was constructed for a capability
this audit could not find real evidence for.

---

## 5. Known Limits

`docs/benchmarks/README.md`'s "What Nexus Has Not Benchmarked" section states seven explicit gaps, matching
the governing prompt's own list: distributed deployment, horizontal scaling, multi-node execution,
million-job scheduling, stress/sustained-load testing, cloud latency, and long-running durability at scale.
Each is stated as an absence of measurement (or, in most cases, an absence of the underlying capability
itself — e.g. no distributed deployment mechanism exists to benchmark), never implied to be a supported-but-
unmeasured capability. This section exists precisely so that the detailed, real numbers in the other four
documents cannot be read as implying capabilities beyond what was actually measured.

---

## 6. Documentation Added

- `docs/benchmarks/README.md` — index, methodology, performance philosophy, and the "What Nexus Has Not
  Benchmarked" section (Phase 6E).
- `docs/benchmarks/scheduler.md` — the Scheduler `tick()` O(n²)→O(n) benchmark, full before/after table.
- `docs/benchmarks/persistence-and-replay.md` — event throughput, replay, restart, memory, execution
  latency, and RC2's isolated pipeline-run delta.
- `docs/benchmarks/quality-gates.md` — test counts, mypy/ruff/coverage/wheel/CI across all five milestones.
- `docs/benchmarks/guarantees.md` — the seven operational guarantees (Phase 6C).
- `docs/benchmarks/validation-matrix.md` — the 20-row capability traceability matrix (Phase 6D).
- `docs/DOCUMENTATION_PHASE6_REPORT.md` (this document).

No file outside `docs/benchmarks/` and this report was modified. No `nexus_*` package, test, script, or CI
file was touched — confirmed in §7.

---

## 7. Validation Results

- **Every benchmark links to a released report.** Every figure in `scheduler.md`, `persistence-and-
  replay.md`, and `quality-gates.md` cites the specific report and section it came from; spot-checked by
  re-opening each cited section during writing (not assumed from a first pass).
- **Every number has provenance.** No number appears in `docs/benchmarks/` without an adjacent citation to
  its source report; the two borderline figures (39 invariants; the P17 1000-schedule projection) are
  explicitly flagged as different in kind from the measured rows around them (§1).
- **No contradictory figures exist.** Cross-checked every metric that appears in more than one source report
  (test counts, mypy file counts, ADR-009 status) for consistency across P17 → RC1 → RC2 → Release
  Readiness → Release Execution — all five reports' numbers form one consistent, monotonically-increasing
  series (test count and mypy scope only grow; the ADR-009 unratified status is stated consistently in all
  five). No two documents in this evidence base assert different values for the same measurement at the
  same point in time.
- **No undocumented assumptions.** Every methodology caveat the source reports themselves state (single-
  machine, single-run, ±10–15% variance, order-of-magnitude not calibrated SLA) is repeated at the top of
  every new benchmark document, not left implicit.
- **Scope discipline:** `git status --short` after this phase's edits shows only `docs/benchmarks/` (five new
  files) and `docs/DOCUMENTATION_PHASE6_REPORT.md` (new) as this phase's changes — no `nexus_*/` package,
  test, script, or CI file was modified, and no new measurement was run.

---

Per the governing prompt: stopping here. Not starting tutorials, contributor experience, release cadence,
governance documentation, or roadmap revisions.
