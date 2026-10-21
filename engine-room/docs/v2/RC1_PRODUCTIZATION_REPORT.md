# RC1 — Productization & GA Preparation Report

Status: **Complete.** Scope: resolve every evidence-backed blocker `docs/v2/P17_PRODUCTION_READINESS_REPORT.md`
identified as preventing a General Availability recommendation for the Nexus v2 constitutional spine.
No new constitutional capability was introduced; no architecture was redesigned. Every change in this
program traces to a documented P17 finding, or to a defect discovered while closing one (disclosed as
such below, not silently folded in).

Branch: `release/rc1-v2-productization` (off `master`). All work is committed; nothing in this program
was left in the working tree uncommitted, unlike every prior program this branch now carries.

---

## Executive Summary

RC1 closes four of P17's five named GA blockers and formally documents the resolution path for the
fifth. **P10–P17 are now committed** — 8 disciplined, logically-grouped commits, each mapped to its
implementation report, with real isolated diffs even where a fix and its target landed in the same
never-before-committed file (see §1), plus 9 additional RC1-specific commits (the entrypoint, both
scheduler and policy fixes, the ADR, migration/operator docs, this report, and two more fixes this
program's own pre-merge review found — §2.5, §7). **A v2 production entrypoint exists** — `python -m nexus_scheduler`
/ the `nexus-v2` console script — and is exercised by an automated regression suite plus a direct smoke
test (§2). **`Scheduler.tick()` is now linear instead of quadratic** — the ~9.6-second-at-1000-schedules
ceiling P17 measured is gone, replaced by ~7–10 ms at 1000 schedules and ~14–27 ms at 2000, verified
before and after with the same benchmark tooling P17 used (§3, §6). **INV-37's runtime-selection-ownership
contradiction has a proposed, evidence-grounded ADR** (`adr/ADR-009-runtime-selection-ownership.md`) ready
for Architecture Review Board ratification — not implemented, per this workstream's explicit scope (§4).
**Migration, deployment, rollback, and upgrade-validation guidance now exists**
(`docs/v2/RC1_MIGRATION_GUIDE.md`), stating plainly what is and is not supported today rather than
inventing a migration tool (§5).

**Three real defects were found and fixed as a direct consequence of building and reviewing the
entrypoint, not as speculative work** — all share one root cause and were found in two passes: first
while writing the entrypoint's own regression tests (§2.3), then in a dedicated adversarial code review
of this branch's diff performed before merge, which deliberately re-tested the entrypoint end-to-end with
more than one goal in the same process (something no test in this program or in P17 had done — see §2.5
for why that matters). All three are instances of the same pattern: a deterministic event identifier,
re-emitted under a *real*, advancing wall clock, collides with itself in the durable store — same
identifier, different timestamp, which the store correctly treats as a conflict (`DuplicateEventError`)
rather than the harmless byte-identical duplicate it silently absorbs. Every restart/multi-call test in
this program and in P17 used a frozen clock across calls, which accidentally masked all three:

1. `build_constitutional_pipeline`'s policy-seeding step (§2.3) — fixed with the registry's own
   pre-existing (but previously unwired) `rebuild()` projection method.
2. That same fix's own `seed`/rebuild interaction had a narrower gap (§2.3) — corrected in review before
   merge.
3. `RuntimeManager.register_runtime` (§2.5) — the *same* bug, unfixed by the first pass because it lives
   in a different subsystem with no rebuild mechanism at all; found by the pre-merge review, reproduced
   directly, and fixed.

**One severe, pre-existing architectural gap was found and deliberately NOT fixed** — see §2.5 and §7.
It is unrelated to the timestamp pattern above, goes deeper than this program's additive-only scope, and
materially changes what "the entrypoint works" can honestly claim today. Read §2.5 before treating this
report's entrypoint claims as unconditional.

**Zero regressions.** The full v2-scoped suite (`tests/unit/nexus_*`, `tests/integration`, the exact set
`.github/workflows/core-ci.yml` runs) passes at 2934 tests (up from P17's 2927 — 7 new regression tests
this program added, across the entrypoint, the policy fixes, and the runtime-manager fix), 1 opt-in skip,
the same 1 pre-existing-and-unrelated `test_state_machines.py` error `--noconftest` has always produced.
mypy-strict (388 source files, 0 errors) and ruff remain clean across the same 30-package v2 scope P17
closed.

**What RC1 does not close:** the durable schema remains unversioned (deliberately — building a migration
mechanism was out of this program's scope; `RC1_MIGRATION_GUIDE.md` §5 states the "frozen until a real
mechanism exists" policy explicitly), no v1→v2 data-migration tool exists (ADR-008 remains the designed-
but-unbuilt path), and INV-37 itself is *proposed*, not ratified — an Architecture Review Board decision
this program cannot make unilaterally. These are the honest remainder; see §7 and §8.

---

## 1. Release Engineering (Workstream 1)

**Inventory.** At the start of this program, 68 changed/untracked paths existed in the working tree,
spanning P10 through P17's entire deliverable plus several already-tracked files P17 modified in place
(`nexus_policy/*`, `nexus_infra/*`, `nexus_runtime/*`, `nexus_workflows/pipeline.py`, `.github/workflows/
core-ci.yml`, `pyproject.toml`). Every path was verified against its owning implementation report before
staging — nothing was committed on the assumption that "it's probably fine."

**Grouping.** Nine phase commits (P10–P17, one commit per report, `test(platform)` for P12 which added no
new package) plus five RC1-specific commits, in dependency order:

| Commit | Contents |
|---|---|
| `feat(planning)` P10 | `nexus_planning/grounded/` + tests + report |
| `feat(execution)` P11 | `nexus_execution/actuation/` + tests + report |
| `test(platform)` P12 | `test_constitutional_platform.py` + report (no new package) |
| `feat(workflows)` P13 | `nexus_workflows/spine/` + tests + report + the isolated P13/F-2 durable-seam hunk in `nexus_workflows/pipeline.py` |
| `feat(human-interaction)` P14 | `nexus_human_interaction/` + tests + report + `nexus_policy`'s grounding/autonomy baseline additions |
| `feat(approval,operations)` P15 | `nexus_approval/` + `nexus_operations/` + tests + report |
| `feat(scheduler)` P16 | `nexus_scheduler/` (pre-RC1-fix state) + tests + report + the wheel package-list addition |
| `fix(v2)` P17 | the INV-36 wiring fix, `LoggingObservability`, the 46-error mypy-strict gate closure, 3 new failure tests, both benchmark scripts, `OPERATOR_GUIDE.md`, the P17 report |
| `fix(scheduler)` RC1 | the isolated `tick()` linearization diff (§3) |
| `fix(policy)` RC1 | the restart-safety fix found while building the entrypoint (§2.3) |
| `feat(v2)` RC1 | the production entrypoint (§2) |
| `docs(adr)` RC1 | ADR-009 (§4) |
| `docs(operator-guide)` RC1 | the entrypoint + scheduler-fix documentation update |
| `docs(migration)` RC1 | this program's migration guide (§5) |

**A genuine constraint, handled honestly rather than glossed over:** none of P10–P17 had ever been
committed, so several files (`nexus_scheduler/scheduler.py`, `nexus_execution/actuation/composition.py`,
`docs/v2/OPERATOR_GUIDE.md`) already contained a P17 or RC1 fix merged into their only-ever-existing
content, with no prior commit to diff against. Rather than commit the fix invisibly bundled into the
phase's feature commit, this program **reconstructed the pre-fix state from this session's own edit
history** (which is exact — every edit in this program is a recorded tool call, not a guess), committed
the phase as it was originally delivered, and then re-applied and committed each fix as its own isolated,
reviewable diff. `git show <hash>` on the `fix(scheduler)` and `fix(policy)` commits shows exactly the
lines that changed, nothing else. Two already-tracked shared files (`nexus_workflows/pipeline.py`,
`tests/unit/nexus_policy/test_guardrails.py`) needed the same treatment because a single file's diff
spanned two phases — both were split at the real hunk boundary using `git diff HEAD` against their actual
prior commits, not reconstructed from memory.

**Verification.** The full v2-scoped suite was re-run against the final `HEAD` of the release branch
after every commit that touched source (not just at the end) — see §6 for final numbers. Nothing was
committed unverified.

**Release branch.** `release/rc1-v2-productization`, created off `master`, currently 17 commits ahead,
clean working tree. Pushed and opened as a PR against `master` on explicit instruction; two of the 17
commits were added after the PR was opened, during the adversarial pre-merge review this report's §2.5
and §7 describe.

---

## 2. Production Entrypoint (Workstream 2)

### 2.1 What v1's entrypoint does, and what v2's needed to not duplicate

`nexus/__main__.py` configures `structlog`, then hands control to `uvicorn.run("nexus.api:app", ...)` —
it boots an ASGI server; it does not author requests. v2 has no HTTP surface at all (P17's security
review: "the only I/O boundary is the SQLite file") and no channel harness wired to accept operator input
yet, so a literal ASGI-server analog does not apply. What v2 *does* have, per the Operator Guide's own
documented model, is a hard requirement stated as a gap: **"`tick(now)` is the only thing that makes time
pass — nothing fires on a wall clock inside the platform... an operator (or a host process's own
scheduler) must call `tick(now)` periodically."** No process did this. That is the literal shape of "no
entrypoint launches it."

### 2.2 What was built

`nexus_scheduler/__main__.py` (registered as the `nexus-v2` console script):

- `bootstrap(db_path)` wires the full stack unchanged — `build_durable_infrastructure`,
  `build_constitutional_pipeline`, `build_approval_exchange`, `build_operations`, `build_scheduler` — with
  three production-real seams that the composition roots' own defaults are wrong for in production: a
  durable file (not in-memory), the real wall clock (not `FixedTimestampSource`, which every test
  correctly uses but a real process must not), and `LoggingObservability` (not the silent default).
- `run_service(scheduler, ...)` calls `scheduler.tick(now())` in a loop against the real wall clock,
  sleeping `tick_interval` seconds between calls, until `max_ticks` is reached or the caller stops it.
- `main()` parses `--db`/`--tick-interval`/`--once`/`--log-level`, boots, runs, and exits cleanly on
  `KeyboardInterrupt` — the same shutdown shape as v1's `main()`.

It authors zero Goals. Registering a `SpineRequest`/schedule remains a caller concern via
`Scheduler.schedule_goal`/`schedule_operation` — exactly as v1's entrypoint does not author HTTP requests
either. This is the deliberate boundary that keeps this workstream additive: **no new constitutional
capability was introduced, only a process that makes the existing ones runnable.**

**A constraint the architecture-fitness suite caught, correctly:** the first draft imported
`nexus_runtime.events.SystemTimestampSource` for a real-clock source. `tests/unit/nexus_scheduler/
test_guardrails.py::test_scheduler_reaches_no_engine` failed immediately — `nexus_scheduler` is
constitutionally forbidden from reaching `nexus_runtime` (an execution engine) directly; it may only
depend on `{nexus_workflows.spine, nexus_approval, nexus_operations, nexus_policy, nexus_core,
nexus_infra}`. The fix was a one-line local adapter over the package's own already-existing
`nexus_scheduler.events.system_now`, mirroring the pattern every other subsystem already uses instead of
importing an earlier layer's timestamp source. This is exactly the kind of boundary this program was told
to stop and respect, not route around — it held, and the entrypoint now lives entirely within
`nexus_scheduler`'s own documented dependency direction.

### 2.3 A restart-safety defect found and fixed while adding regression tests

Building a genuine restart regression test (`bootstrap()` twice over the same durable file, as a real
process restart would look) surfaced a real bug, not a test artifact: `build_constitutional_pipeline`
calls `build_policy(infrastructure, now=now)` with `seed=True` by default, which unconditionally
re-registers the v1-migrated baseline policies on *every* call — including a restart. Every existing
restart test in the codebase injects a **fixed** clock across both boot calls, so the re-emitted
`policy.registered` events happened to be byte-identical to the first boot's and were silently absorbed
as harmless duplicates by the durable store's own dedup logic. A **real** restart uses a real, advancing
clock — the second boot's re-emission carries a different timestamp under the same event identifier,
which the durable store correctly treats as `DuplicateEventError` (same identifier, different content)
rather than a harmless repeat. **Every real second restart of the platform would have crashed on this**,
undetected until this program built the first entrypoint that boots with a real clock and tested a real
restart against it.

Fixed with the registry's own pre-existing `rebuild(events)` projection method — designed exactly for
this ("ADR-007 restart determinism"), used consistently elsewhere in the codebase's own restart tests, but
never called from `build_policy`'s composition root. Two small, additive changes:

- `nexus_policy/composition.py`: `build_policy` now checks whether the durable log already carries
  `policy.registered` facts; if so, it rebuilds the registry from them instead of re-seeding.
- `nexus_policy/registry.py`: `InMemoryPolicyRegistry.register()` is now a no-op when the exact
  `(identity, version, content)` is already known — restart-safe even for the two other composition roots
  that unconditionally re-register a baseline policy on every call (`build_constitutional_pipeline`'s
  knowledge-grounding baseline, `build_scheduler`'s autonomy baseline).

Neither change affects any fresh/in-memory infrastructure (every existing test's shape) — confirmed by
re-running the full `nexus_policy`, `nexus_scheduler`, `test_constitutional_spine.py`,
`test_constitutional_platform.py`, and `test_learning_loop.py` suites: zero regressions.

### 2.4 Verification

`tests/integration/test_v2_entrypoint.py` (4 tests): bootstrap wires a real durable platform; a
`FULLY_AUTOMATIC` goal registered with `ScheduleTrigger.immediate()` is dispatched through the *real*
Constitutional Pipeline and reaches `pipeline.completed` in exactly one `run_service(max_ticks=1)` call;
`run_service` sleeps between ticks but never after the last one; and a fresh `bootstrap()` over a reopened
durable file reconstructs an identical schedule (the test that caught §2.3). Plus a direct manual smoke
test: `python -m nexus_scheduler --db <tmp> --once` boots, ticks once, and exits 0, producing a real
SQLite file.

**Every test above exercises exactly one goal per process.** §2.5 explains why that boundary matters and
was not exceeded lightly.

### 2.5 What a pre-merge adversarial review found: one more real fix, and one severe unfixed gap

Before merging this branch, its own diff was put through an adversarial multi-angle code review (8
independent finder passes plus cross-verification — see the PR discussion for the full methodology). Two
angles (cross-file tracing and altitude) independently asked the same question: does the restart-safety
pattern just fixed for `nexus_policy` (§2.3) recur anywhere else the entrypoint's real clock now reaches?
It does.

**Fixed: `RuntimeManager.register_runtime` had the identical bug.** Every actuation calls it to announce
its runtime, on a *fresh* `RuntimeManager`/registry built per actuation (unlike Policy, Harness/Runtime
registration has no rebuild-from-log mechanism at all). Two actuations in the same process sharing a
runtime identity — the ordinary case for any deployment running more than one goal — re-announce that
identity, and under a real clock the second announcement's timestamp differs, raising
`DuplicateEventError`. Reproduced directly (two `build_execution_actuation()` calls over one durable
infra, real clock, second call crashes) and fixed the same way as the policy case: the announcement event
id is a pure function of runtime identity alone, so a collision on it can only mean "already announced" —
caught and treated as the no-op it already claimed to be. Full details and the regression test are in the
commit `fix(runtime): make register_runtime restart/re-actuation-safe under a real clock`.

**Found, reproduced, and deliberately NOT fixed: work-item-keyed session/event scoping is not
goal-unique.** Tracing one step further (why did the *second* goal's actuation crash somewhere else
entirely, in Validation, even after the runtime-manager fix) surfaced a second, larger, and unrelated
defect: `nexus_execution/actuation/dispatch.py`'s `_project_intake` builds
`package_identity=f"actuation-pkg-{node.identifier}"`, and the runtime session/validation event scope
that flows from it is derived from that *node identifier alone* — the work item's key (e.g. `"draft"`) —
never from the enclosing Goal, pipeline session, or correlation. Two different goals whose plans both
happen to produce a work item keyed `"draft"` (which the only reference `SpineRequest` builder available
today, `nexus_workflows.spine.spine_reference_request`, always does — its work-item keys are hardcoded,
not parameterized) get the *same* runtime-session and validation-event scope. Reproduced directly:
scheduling two `FULLY_AUTOMATIC` goals built from that reference helper and ticking once crashes inside
`nexus_validation` with `DuplicateEventError`, downstream of a session/event identifier that is identical
for both goals.

This is **not** the timestamp pattern above — it is a real content collision (the two goals' validation
facts are genuinely different, not idempotent duplicates), so catching `DuplicateEventError` the way the
other three fixes did would be **wrong**: it would silently drop the second goal's validation fact rather
than record it, corrupting the log exactly the way that error exists to prevent. A correct fix means
threading goal/session identity into node/session scope construction somewhere in the
Orchestration→Runtime→Execution chain — real, multi-subsystem, behavioral surgery, not a small additive
fix, and squarely the kind of architectural change every program in this series (P17 and this one) was
told not to make unilaterally.

**This is pre-existing, not RC1-introduced** — the scoping scheme dates to P11 and was never RC1's to
build. It surfaces now because RC1's entrypoint is the first thing to plausibly run more than one goal
against a real clock in one process; every prior "concurrent sessions" measurement in this program and in
P17 (`scripts/p17_scale.py::scale_concurrent_sessions`) used `FixedTimestampSource` and the same
reference-request helper for every run, which means — by the same mechanism — those 50 "independent"
runs most likely produced byte-identical events for their shared "draft"/"review" nodes and were silently
deduplicated rather than genuinely exercised as 50 distinct sessions. That measurement's throughput number
is very likely still representative (the work performed per run is the same either way), but its
"50/50 completed, independent sessions" framing should be read as unverified for genuine independence,
not certainly false.

**Practical scope of what is and isn't safe today:** one goal per process is fully verified (§2.4).
Multiple goals in one process are safe *only* if their plans never produce two work items with the same
key — true for hand-built, real `SpineRequest`s with distinct work-item keys (not reproducible with the
reference/demo fixture used throughout this program's own tests). This is now the operative constraint on
the entrypoint's practical use until fixed; see §7 for its position in the risk list and §8 for how it
changes the GA recommendation.

---

## 3. Scheduler Optimization (Workstream 3)

### 3.1 Profiling and root-cause confirmation

P17's finding was re-verified by reading the code directly, not assumed from the prior report:
`Scheduler.tick()` (`nexus_scheduler/scheduler.py`) loops `for schedule in
reconstruct_schedules(self._history())` — one correct, single O(events) pass — but then calls
`self._maybe_complete(schedule.identity, schedule.trigger, now)` **on every iteration**, and
`_maybe_complete` called `reconstruct_schedule(self._history(), identity)`, which itself calls
`reconstruct_schedules` again (a full second fetch of the entire event history and a full
re-reconstruction of *every* schedule) just to find the one matching `identity`. For *n* registered
schedules, this is *n* extra O(events) passes inside one `tick()` call — O(n·events), which is O(n²) once
event count scales with schedule count, matching P17's measured curve exactly (10→100 schedules: ~80×
slower; 100→500: ~26× slower — not linear).

### 3.2 The fix

`_maybe_complete` no longer re-fetches anything. The outer loop already has the schedule it needs; it now
also tracks how many new occurrences it just fired this tick (`newly_fired`). `_maybe_complete(schedule,
newly_fired, now)` computes `total_dispatched = len(schedule.dispatched) + newly_fired` and calls
`is_exhausted(schedule.trigger, now, total_dispatched)` directly — no history read, no reconstruction,
O(1) per schedule. The schedule's `is_active` status is stable across the one outer-loop iteration that
processes it (nothing else transitions it mid-iteration), so the redundant re-check `_maybe_complete` used
to perform was provably unnecessary, not just expensive.

This is the exact fix P17's own report proposed and declined to make ("reuse the outer loop's already-
reconstructed schedule... a well-understood, bounded fix, just correctly out of scope for an audit-only
program"). No behavior changed: same dispatch order, same completion semantics (a schedule completes at
the identical tick it did before), same replay/restart guarantees. All 28 pre-existing scheduler unit and
integration tests pass unchanged — this was verified before writing any new test, confirming the fix is
purely an internal-cost change.

### 3.3 Results

See §6 for the full before/after table. Headline: 500 registered schedules dropped from ~1.14 s to ~3.3 ms
(≈345×); the projected ~9.6 s at 1000 schedules is now ~7–10 ms; growth from 500→1000→2000 schedules is
now consistent with linear scaling, not quadratic.

---

## 4. INV-37 ADR Proposal (Workstream 4)

**Not implemented, per this workstream's explicit scope.** `adr/ADR-009-runtime-selection-ownership.md`
(339 lines) traces runtime-selection ownership across the actual current call graph with file:line
evidence, confirms the contradiction P17 found is real and current (not stale), and proposes a resolution
for a future Architecture Review Board decision.

**The contradiction.** INV-37, ADR-002 §3, and the Constitution's COORDINATE step all say, unambiguously
and repeatedly: Orchestration selects and allocates a runtime; capability resolution returns candidates
only. The runtime subsystem's own design docs (`docs/v2/runtime/06_RUNTIME_SELECTION.md`) say the
opposite, deliberately and in detail: the Runtime Manager performs final selection and allocation, on the
argued grounds that allocation is inherently runtime-facing (reserving against live capacity, binding to
a session). **The implementation followed the runtime docs, not the Constitution** — verified directly:
the match→health→policy→choose funnel lives in `RuntimeSelector` (`nexus_runtime/allocation.py`);
Orchestration never imports `nexus_runtime` and only ever produces `RuntimeRequest` candidates; the
trigger sits in `nexus_execution/actuation/dispatch.py`, which additionally contains two docstrings that
disagree with each other about whether ownership is sole (Runtime Manager's) or joint (Orchestration+
Runtime's) — an internal contradiction against INV-02 regardless of which broader reading wins.

**The proposal (Alternative A of three considered):** ratify the Runtime Manager as sole owner of
selection and allocation, and correct INV-37's wording (plus its three restatements and one enum
docstring) to match — rather than relocating the working implementation to match INV-37 as currently
written (Alternative B, rejected: high blast radius, inverts a near-frozen contract, and weakens a real
architectural boundary the runtime docs argued for on sound grounds) or leaving the contradiction standing
(Alternative C, rejected: a permanent GA blocker with no path to resolution). Alternative A is estimated
**low implementation risk** — it moves approximately zero lines of production logic (four doc edits, two
non-behavioral docstring corrections, one additive architecture-fitness test); Alternative B is estimated
high risk for a proportionally small problem ("two documents disagree about a word").

This program takes no position beyond recommending ratification of Alternative A for the Architecture
Review Board's decision — ratifying an ADR is explicitly the kind of architectural decision this program
was told not to make unilaterally.

---

## 5. Migration Strategy (Workstream 5)

`docs/v2/RC1_MIGRATION_GUIDE.md` — full content there; summary here.

**v1→v2 migration.** Only a greenfield v2 deployment is actually supported today: start from an empty
durable log, boot `nexus-v2`, register work through the composition-root API. No tool exists to move v1's
pilot data (tasks, approvals, memory) into v2, and this program did not build one — that was explicitly
out of scope ("no speculative migration work"). The designed-but-unimplemented mechanism for a real future
cutover is `adr/ADR-008-shadow-migration.md` (already ratified, pre-dates this program): Recorded Shadow
Adjudication, migrating one constitutional owner at a time behind a feature flag, Policy first. The guide
documents this as the path to build against, not a new mechanism invented ad hoc.

**Rollback.** Because v1 and v2 share zero schema, database, process, or code import in either direction
(confirmed both directions in P17's audit), v1 is never at risk from running, upgrading, or removing v2.
Rolling back v2 itself is an ordinary process stop/redeploy against the same durable file (safe — the
schema is unversioned but stable, and every RC1 change is behavioral/performance-only, not a schema
change) or a filesystem-level restore from a pre-deployment backup if the *data*, not the code, is the
problem (the event log is append-only by design; there is no selective-delete).

**Compatibility notes.** The durable schema remains explicitly frozen (no version tracking exists — this
program did not build one, and states the "frozen until a mechanism exists" policy as the operative rule
rather than leaving it implicit). RC1 introduced zero schema changes and zero new dependencies (the
entrypoint uses stdlib only).

**Deployment checklist and upgrade validation.** Both fully specified in the guide: install, choose a
durable path, choose a process supervisor (none is built in — `nexus-v2` is a foreground process), wire
logging, start it, register work, verify health via `nexus_operations`; and for upgrades, re-run the
v2-scoped test suite and the benchmark/scale scripts, then dry-run the new build against a copy of the
production durable file before repointing at the real one.

---

## 6. Benchmark Results

Measured with the same tooling P17 built (`scripts/p17_benchmark.py`, `scripts/p17_scale.py`), re-run
against this branch's final `HEAD` — same methodology, same caveats (single-machine, single-run, order-of-
magnitude and shape, not calibrated production SLAs).

### 6.1 Scheduler — the headline fix

| Registered schedules | P17 (before) | RC1 (after) | Improvement |
|---|---|---|---|
| 10 | 0.5 ms | 0.09 ms | ~6x |
| 100 | 43.1 ms | 0.66 ms | ~65x |
| 500 | 1136.6 ms | 3.29 ms | ~345x |
| 1000 | ~9.6 s (documented, not directly re-measured at this count in P17's own benchmark script) | 6.8 ms | >1000x |
| 2000 | not measured in P17 | 14.4 ms | — |

Growth shape: P17's numbers were consistent with O(n²) (10→100: ~80× slower for a 10× schedule increase;
100→500: ~26× slower for a 5× increase). RC1's numbers are consistent with linear scaling (500→1000: ~2×
slower for a 2× increase; 1000→2000: ~2.1× slower for a 2× increase).

### 6.2 Everything else — confirmed unchanged in shape (RC1 touched none of these paths)

| Metric | P17 | RC1 (re-measured) |
|---|---|---|
| Pipeline startup — in-memory | 0.03 ms | 0.03 ms |
| Pipeline startup — durable (fresh file) | 8.2 ms | 7.0 ms |
| Pipeline startup — full spine wiring | 0.7 ms | 0.73 ms |
| Event throughput — in-memory (2000/1 txn) | 140,677/sec | 145,072/sec |
| Event throughput — durable (2000/1 txn) | 16,709/sec | 17,389/sec |
| Persistence overhead | 8.4x | 8.3x |
| Event throughput — durable (200×1 txn each) | 2,246/sec | 2,503/sec |
| Replay throughput (2200 events) | 155,335/sec | 170,989/sec |
| Restart latency (2200 events) | 15.5 ms | 15.35 ms |
| Execution latency (single-node) | 0.78 ms | 0.72 ms |
| Autonomous execution overhead | ~no measurable delta over direct run | ~no measurable delta (-11%, within noise) |
| Memory — 5000 in-memory events | 10.0 MiB | 10.0 MiB |
| Memory — one full spine run | 0.5 MiB | 0.54 MiB |
| Replay at scale (20,000 events) | not measured at this scale in P17's own run | 92,742 events/sec, 215.7 ms |
| Restart at scale (20,000 events) | not measured at this scale in P17's own run | 180.9 ms |

Run-to-run variance (±10-15%) is expected on a single-machine, single-run measurement — the numbers above
confirm shape and order-of-magnitude parity with P17, not micro-benchmark precision, exactly as both
programs' methodology states.

---

## 7. Remaining Risks

Carried forward from P17, with RC1's disposition stated for each:

| # | Risk | P17 status | RC1 status |
|---|---|---|---|
| 1 | No entrypoint launches v2 | Blocker | **Closed** (§2) — scoped to single-goal-per-process; see #12 |
| 2 | `Scheduler.tick()` O(n²) | Blocker | **Closed** (§3, §6) |
| 3 | P9–P16 uncommitted | Blocker | **Closed** (§1) |
| 4 | No schema migration mechanism | Blocker | **Not closed, deliberately** — "frozen until built" policy documented (§5); building the mechanism was out of scope |
| 5 | No v1→v2 data migration path | Blocker | **Not closed, deliberately** — ADR-008 remains the designed-but-unbuilt path (§5); building it was out of scope |
| 6 | INV-37 ownership drift | Constitutional violation | **ADR proposed, not ratified** (§4) — ratification is an Architecture Review Board decision |
| 7 | `nexus_integration`'s ADR-008 substrate unwired | Should-fix | Unchanged — out of this program's scope |
| 8 | `WorkflowCoordinator` duplicate driver | Should-fix | Unchanged — out of this program's scope |
| 9 | Deployment artifact (Dockerfile stage for v2) | Operational gap | Unchanged — `nexus-v2` exists as a console script; no container packaging was built |
| 10 | Graceful shutdown hook | Operational gap | Unchanged — proven safe (WAL atomicity) but no explicit flush hook |
| 11 | Version/changelog disagreement | Hygiene | Unchanged |
| 12 | **Runtime-session/validation event scope is keyed by work-item identifier alone, not by goal/session identity** | Not known to P17 (never exercised — every multi-run measurement used a frozen clock and the same reference fixture, see §2.5) | **New finding, found in this program's own pre-merge review, NOT fixed** — see §2.5. Two goals whose plans produce a same-keyed work item collide in the durable log under a real clock; the collision is a genuine content conflict, not a safe duplicate, so it cannot be papered over the way the timestamp-only bugs were. Requires threading goal/session identity through Orchestration→Runtime→Execution's scope construction — real cross-subsystem behavioral work, out of this program's additive-only scope. **This is now the platform's most severe open risk** — more severe than any item P17 originally listed, because it is a silent data-corruption path (a dropped validation fact), not a crash-on-restart or a performance ceiling. |

**New findings from this program, already fixed (not carried forward as risks):** the policy restart-
safety defect (§2.3) and the `RuntimeManager.register_runtime` restart/re-actuation-safety defect (§2.5)
— both disposed of, not merely documented, because they blocked the entrypoint workstream itself from
being genuinely safe to run. Risk #12 above is the one defect this program found and did **not** dispose
of, because doing so responsibly requires architectural work outside this program's mandate.

---

## 8. GA Recommendation

**Not recommended for unconditional General Availability.** This is a downgrade from this report's
original conclusion (conditional GA pending only ADR-009 ratification and a migration decision), issued
after this branch's own pre-merge adversarial code review found risk #12 above (§7, §2.5): a real,
reproduced, silent data-corruption path (a dropped validation fact under `DuplicateEventError`, not a
crash that fails loudly) whenever two goals in one process produce a same-keyed work item. This is a more
serious class of problem than anything this report previously listed, and it was found only because the
review deliberately tested the new entrypoint with more than one goal — something no test in this program
or in P17 had done before merge.

**Three items now gate a genuine GA recommendation, in priority order:**

1. **Risk #12 (new, this review): runtime-session/validation scope must incorporate goal/session identity,
   not work-item identifier alone.** This is the one true blocker among the three — it is a correctness
   defect with a silent-corruption failure mode, not a documentation gap or a greenfield-vs-migration
   scoping question. Recommend a narrowly-scoped follow-up program: trace every place node/session scope
   is constructed (`nexus_execution/actuation/dispatch.py`'s `_project_intake` is the entry point; the
   fix likely needs to reach into Orchestration's `RuntimeRequest` construction and/or the Runtime
   session-scope derivation), design the fix as a real ADR-reviewed change (given it touches a near-frozen
   contract-adjacent seam), and prove it with a genuine multi-goal, real-clock, shared-work-item-key
   regression test — the exact scenario this review used to reproduce it.
2. **INV-37's ADR-009 needs Architecture Review Board ratification** (unchanged from this report's
   original conclusion; §4).
3. **A schema-migration mechanism and a real v1→v2 data-migration path remain unbuilt** (unchanged;
   acceptable indefinitely for greenfield-only deployment; §5).

**What is still true and still solid:** every blocker P17 originally named is closed or has a proposed
resolution path (§1–§6); the platform is committed, launchable for the single-goal-per-process case that
is fully verified, and its one measured production-scale ceiling is gone; two additional real restart/
re-actuation-safety defects were found and fixed by this program's own pre-merge review, not left for a
future program to discover the hard way; and every fix in this program — including the two found during
review — was verified against the full v2-scoped suite with zero regressions (§6, §Executive Summary).
This program's engineering discipline held under adversarial pressure; what it found is a genuine reason
to gate GA, not a reason to distrust the rest of the work.

**Recommendation: merge this branch** (every fix in it is a real, net improvement, independently verified
— reverting any of them would restore a known bug, not remove a risk) **but do not recommend v2 for GA
until risk #12 is resolved and proven.** Multi-goal-per-process autonomous operation — the core value
proposition of the Scheduler this program just made performant and the entrypoint this program just
shipped — is not yet safe to claim for any deployment where two goals might share a work-item key, which
today means "not safe to claim in general," since nothing enforces work-item-key uniqueness across goals.
