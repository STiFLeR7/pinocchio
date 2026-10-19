# P17 — Constitutional Production Readiness & General Availability

Status: **In progress.** This report is being written incrementally as each phase of P17 completes.
Scope: certify whether the **Nexus v2 constitutional spine** (`nexus_*` packages, built across P0–P16)
is ready to become the production control plane. v1 (`nexus/`, the currently-released, pilot-live
Discord/FastAPI product) is in scope only as context — what is actually shipped today — not as the
subject being certified.

No commits were made during this program. Per the standing instruction, nothing in this report's
"Fixes Applied" sections has been committed to git; they are working-tree edits only, exactly like the
uncommitted P9–P16 work this program audited.

---

## Executive Summary

Nexus v2's constitutional spine — 30 packages built across P0–P16 — is **architecturally sound and
extensively proven, but not yet a deployable production system.** This program audited every subsystem
against the 39 ratified invariants, stress-tested nine named failure classes (including a genuine
OS-level process crash), measured performance and scale characteristics with real composition roots (no
mocks), verified operational readiness, wrote the first operator documentation, and audited release
readiness — and found a codebase whose *engineering discipline* is real (zero producer collisions, zero
forbidden dependencies, zero `PolicyDecision` leakage across 25+ consumer packages, genuine
replay/restart-equivalence proofs everywhere they were checked) sitting behind a *product* that has never
been wired up, never been deployed, and — critically — **has never been committed to git**.

**Three constitutional violations were found**, all structural wiring issues rather than design flaws:
no entrypoint launches the v2 spine (only v1 does); two composition roots silently split the Harness
Registry (INV-36) into two unsynchronized instances (**fixed** in this program, with a Protocol-typing
follow-up that also hardened the fix under mypy strict); and runtime selection ownership has quietly
drifted from Orchestration into Runtime/Execution (INV-37, documented, not fixed — relocating a decision
point is out of this program's additive-only scope). **One significant, measured production risk** was
found: `nexus_scheduler.Scheduler.tick()` is quadratic in the number of registered schedules — ~9.6
seconds at 1000 schedules — a real ceiling for any deployment expecting hundreds-to-thousands of
recurring jobs.

Everything this program could fix additively and safely, it fixed, with regression tests and full
mypy-strict/ruff/pytest verification after each change: the INV-36 registry split; a production-usable
`LoggingObservability` sink (the platform had none before); and — the largest single piece of work — 46
real mypy-strict errors across 7 previously ungated packages, closing a CI blind spot down to a single
remaining, honestly-scoped coverage gap. One candidate fix (a stricter approval-taxonomy guard on
`FULLY_AUTOMATIC` scheduling) was investigated, found to contradict deliberately-tested P16 behavior, and
correctly reverted rather than silently overriding a reviewed design decision.

**Final tally:** 3 constitutional violations (1 fixed, 2 documented for a future ADR/decision), 8 risks
documented, 1 measured production-blocking scale ceiling, 2927 passing tests (zero regressions from any
change in this program), mypy-strict clean across all 30 packages, ruff clean, 97.97% coverage on the
gated scope. See the GA Checklist below for the recommendation.

---

## Phase 1 — Constitutional Audit

**Method.** Six read-only audit agents ran in parallel: one synthesized all 18 P0–P16 implementation
reports (plus 6 legacy phase docs) into a subsystem ownership map and a consolidated self-reported gap
register; five audited disjoint subsystem clusters directly against `99_ARCHITECTURAL_INVARIANTS.md`
(39 invariants) and `ARCHITECTURE_CONSTITUTION.md`, independently re-verifying every claim by reading
code and re-running greps/tests rather than trusting docstrings or prior reports. I cross-checked the
highest-signal claims myself directly (CI configuration, mypy/ruff runs, entrypoint resolution,
git history, `Observation`/`PolicyContext` greps) before accepting them into this report.

Clusters: **Foundation & Persistence** (`nexus_core`, `nexus_infra`, `contracts/`, `nexus_harness`) ·
**Reasoning & Grounding** (`nexus_intent`, `nexus_engineering`, `nexus_estimation`, `nexus_repository`,
`nexus_operator`, `nexus_history`, `nexus_research`, `nexus_context`, `nexus_planning`, `nexus_knowledge`) ·
**Execution & Orchestration** (`nexus_orchestration`, `nexus_runtime*`, `nexus_execution`+`actuation`,
`nexus_validation`, `nexus_recovery`, `nexus_reflection`) · **Governance & Platform Ops** (`nexus_policy`,
`nexus_human_interaction`, `nexus_approval`, `nexus_operations`, `nexus_scheduler`, `nexus_briefings`) ·
**Spine Composition & Entrypoints** (`nexus_workflows`, `nexus_workflows/spine`, `nexus_integration`,
process entrypoints).

### 1.1 Constitutional violations found

| # | Finding | Evidence | Status |
|---|---|---|---|
| V1 | **No entrypoint launches the v2 spine.** `pyproject.toml`'s only `[project.scripts]` entry, `python -m nexus`, and the Docker `CMD` all resolve to `nexus/__main__.py` → `uvicorn.run("nexus.api:app", ...)` — 100% legacy v1. Nothing in the repository invokes `nexus_workflows.spine.build_constitutional_pipeline`/`ConstitutionalPipeline` outside test code. The Engineering Program's P10 DoD ("single entrypoint launches v2 spine") is **not met**. | `pyproject.toml:27`, `nexus/__main__.py:44-50`, `docker/Dockerfile:33`; independently confirmed by me via `pyproject.toml` read | **Documented, not fixed** — cutover is a product decision, out of scope for an additive audit fix |
| V2 | **INV-36 broken at runtime: two divergent `HarnessRegistry` instances.** Two composition roots — `nexus_workflows/pipeline.py` (`PipelineBuilder.build()`) and `nexus_execution/actuation/composition.py` (`build_execution_actuation()`) — called `nexus_runtime.build_runtime()` without forwarding the `harness_registry=` they had already built for Orchestration/Actuation, so `build_runtime` silently default-constructed a second, unsynchronized `InMemoryHarnessRegistry`. Found independently by two audit clusters (Foundation, via `pipeline.py`; Execution, via `actuation/composition.py`) — convergent evidence, not a single false positive. | `nexus_workflows/pipeline.py:96` (pre-fix), `nexus_execution/actuation/composition.py:51` (pre-fix), `nexus_runtime/composition.py:38-63` | **Fixed** (§1.4) |
| V3 | **INV-37 broken in the call graph: runtime selection doesn't sit in Orchestration.** `nexus_orchestration` never imports `nexus_runtime` and correctly produces candidates only (`nexus_orchestration/runtime_requests.py`). But the actual match→health→policy→choose funnel (`nexus_runtime/allocation.py::RuntimeSelector.select`) is invoked from `nexus_runtime/runtime_manager.py:153`, which is called from `nexus_execution/actuation/dispatch.py:90` (`RuntimeDispatcher.dispatch`) — i.e. Execution/Actuation triggers selection, not Orchestration. `dispatch.py`'s own docstring asserts "selection/allocation stays Orchestration+Runtime's — INV-37," quietly redefining sole ownership to joint ownership with no superseding ADR. | `nexus_execution/actuation/dispatch.py:90-94`, `nexus_runtime/runtime_manager.py:153-159`, `nexus_runtime/allocation.py:97-135` | **Documented, not fixed** — relocating the decision point between subsystems is an architectural change, explicitly out of scope for this program (see §1.5) |

### 1.2 Risks (documented, not code-illegal, but load-bearing for the GA decision)

| # | Finding | Evidence | Severity |
|---|---|---|---|
| R1 | `nexus_integration` — the full ADR-008 flag/shadow/correlation substrate (`FlagStore`, `ShadowDecisionCoordinator`) — is built, durable, and fully tested (30/30 passing when exercised directly), but has **zero callers outside its own tests anywhere in the repository**. No live flag gates v1-vs-v2 routing; v1/v2 separation today is "two disjoint package trees," not the flagged strangler-fig seam ADR-008/P3 specified. Independently corroborated by the report-synthesis agent (P4–P16 all read as greenfield builds, never shadowed via `adjudicate()`) and the spine-cluster agent (empirical zero-caller grep). | `nexus_integration/*.py`; repo-wide grep | High — this is the entire migration mechanism the program's own plan depended on |
| R2 | Duplicate `InMemoryHarnessRegistry` **class** definitions (`nexus_orchestration/registry.py` and `nexus_runtime/runtime_registry.py`, near-identical, independently coded) compound V2 — even with instances now correctly shared (§1.4), the two implementations can drift structurally. | Both files | Medium |
| R3 | **INV-14 ("state is a projection of the log") is unproven for 5 named repositories** (Goal/Plan/Artifact/Policy/Knowledge). They are dual-written directly (`.add()`) inside the same `UnitOfWork` as their paired event — atomicity holds (INV-13 intact) — but no test rebuilds these specific stores by folding events through a Projection; only the generic `ProjectionEngine` path has a replay-equivalence test. | `nexus_infra/durable.py:300-396`, `nexus_planning/planner.py:157-162`, `nexus_recovery/engine.py:161` | Medium — a real gap in the strongest form of the restart guarantee, not a violation of the weaker (atomicity) guarantee |
| R4 | `nexus_workflows/coordinator.py`'s `WorkflowCoordinator` is a **second, fully-live, exported Goal→Knowledge driver** that bypasses Execution Actuation (uses raw Orchestration/Harness/Runtime/Execution instead of `nexus_execution.actuation`). Its only non-test instantiation is `a0.py:234`, a superseded P7 prototype unreachable from any entrypoint — low exposure today, but it is a second owner of the same responsibility (INV-02) and was never retired. | `nexus_workflows/coordinator.py:84-140` vs `nexus_workflows/spine/coordinator.py:214-334` | Medium |
| R5 | **`AutonomyMode.FULLY_AUTOMATIC` auto-approves every waiting gate regardless of the gate's own declared approval taxonomy** (Automatic/HumanReview/MultiStage/Deferred, `ExecutionStrategy.approval_policy`). Only the top-level `autonomous_execution` Policy check (attributes: `mode` + `schedule`) gates dispatch; there is no per-gate check. Investigated as a candidate fix and **reverted** — `tests/unit/nexus_scheduler/test_autonomy.py::test_fully_automatic_auto_approves_when_policy_permits` and the P16 integration suite explicitly assert this as the intended, reviewed behavior (a `HUMAN_REVIEW`-gated node under a `FULLY_AUTOMATIC` schedule is expected to auto-approve and complete). This is a **designed** safety posture, not an oversight — but it means "Fully Automatic" can override a Plan's own human-review requirement on nothing stronger than a coarse mode+schedule policy check. Worth an explicit operator decision before GA, not a silent code change. | `nexus_scheduler/autonomy.py:83-94`, `nexus_approval/exchange.py:88-110`, `tests/unit/nexus_scheduler/test_autonomy.py:74-81` | High (safety-relevant, but working as designed — a policy/process risk, not a bug) |
| R6 | `nexus_briefings` (real, live v2.0.0a1 code driving the actual Constitutional Pipeline — **not**, as I initially mis-scoped it, superseded v1-era code) and its only consumer `nexus_operator` are both real, tested, but **unwired into the running product** — `nexus_operator` is "imported by nothing" (its own docstring) and has zero references from the live v1 entrypoints. | `nexus_operator/__init__.py:19`; `nexus_briefings/__init__.py` | Medium |
| R7 | **`contracts/engineering_strategy.md` and `contracts/repository_understanding.md` were never frozen**, despite the Constitution's own trigger ("freeze only when a second consumer needs the shape") having been met — `EngineeringStrategy` now has ≥3 real consumers (`nexus_planning/planner.py`, `nexus_planning/strategy_binding.py`, `nexus_planning/grounded/model.py`, `nexus_context/grounding/model.py`); `RepositoryProfile` likewise. No competing second schema exists for either (INV-07 itself is not breached), but the freeze discipline the Constitution prescribes for itself was not followed. | `contracts/` (18 files, missing these 2); `nexus_engineering/model.py:78` | Low-Medium — a process gap, not a code defect |
| R8 | **`docs/v2/ARCHITECTURE_CONSTITUTION.md`'s own Object Model table is stale.** It marks Estimation "Void" and `EngineeringStrategy`/`RepositoryUnderstanding` "Proposed," but all three are fully implemented (P4–P9) with multiple live consumers. A reader of the canonical doc today would not know these subsystems exist. | Constitution "Canonical Object Model" table vs. `nexus_estimation/` (13 source files) | Low — documentation currency, not architecture |

### 1.3 Confirmed-clean (positive evidence, not just absence of complaint)

The audit was designed to produce explicit CLEAN-confirmed evidence, not just flag problems — summarized (full per-cluster tables available in the agent transcripts if needed):

- **Event ownership (INV-02/39):** 20 distinct `_PRODUCER` constants repo-wide, zero collisions.
- **Dependency direction:** zero forbidden imports found anywhere — Reason never imports downstream engines; Planning never imports Execution/Orchestration; Context never writes Knowledge; Knowledge never imports Planning/Execution; Reflection never imports Planning or writes Knowledge directly; Recovery never references Goal or imports Execution/Orchestration; Actuation carries only a `goal_ref` reference, never the Goal itself.
- **Schema uniqueness (INV-07):** all 17 objects with a `contracts/*.md` file map 1:1 to exactly one `nexus_core/domain` class; zero duplicate class definitions found anywhere outside `nexus_core/domain/`.
- **Determinism (INV-17):** `datetime.now`/`time.time`/`random`/bare `uuid.uuid4` appear only inside injected `now`/`Clock`/`TimestampSource`/`IdentifierFactory` seams across every package audited — never in domain or decision logic.
- **Policy boundary (INV-28):** the literal string `PolicyDecision` is confined to `nexus_policy` and `nexus_core` (its frozen contract home) across the *entire* repository — zero leakage into any of the 25+ consumer packages.
- **Fail-closed (INV-30):** `nexus_policy`'s `DEFAULT_POLICY` is a permanent deny catch-all; both the no-match and evaluation-exception paths are exercised by dedicated tests.
- **Approval Exchange ownership:** zero direct emission of `approval.*` lifecycle facts from any package other than `nexus_approval`, including `nexus_human_interaction` and `nexus_scheduler`.
- **Cross-stratum isolation:** zero v1→v2 imports and zero v2→v1 imports, confirmed by grep in both directions across the whole tree.
- **`async def` count:** zero in `nexus_core`/`nexus_infra`, confirmed by grep (though see note below — this is not CI-enforced).
- **Replay/restart:** every cluster's durable integration tests assert genuine reconstructed-state equality (not merely "doesn't crash") — spot-verified directly by me and by the audit agents across `nexus_infra`, `nexus_planning`, `nexus_engineering`, `nexus_repository`, `nexus_context`, `nexus_execution/actuation`, and the full spine (`test_constitutional_spine.py`).
- **Spine composition:** all 9 `SpineStage`s (Intent→Engineering→Context→Planning→Actuation→Validation→Recovery→Reflection→Knowledge) are wired with no stub, verified live via the full integration suite including 3 distinct restart scenarios.
- **`nexus_workflows/pipeline.py` is not dead/competing code** — it is deliberately reused by the spine for the Validate→Knowledge back-chain; the uncommitted diff adding an `infrastructure` parameter is exactly that wiring seam (P13/F-2).

### 1.4 Fix applied: INV-36 Harness Registry unification

**What was broken.** `nexus_runtime.build_runtime(infrastructure, *, harness_registry=None, ...)` silently
constructs its own `InMemoryHarnessRegistry` when no registry is passed. Two composition roots called it
without passing the registry they had already built and registered adapter descriptors into for
Orchestration/Actuation's candidate discovery — so descriptors registered on one side were invisible to
the Runtime Manager's selection funnel on the other, the exact split INV-36 exists to prevent.

**Fix.** Threaded the existing `harness_registry`/`registry` local through both call sites:
- `nexus_workflows/pipeline.py:96` — `build_runtime(infra, timestamps=ts)` → `build_runtime(infra, harness_registry=harness_registry, timestamps=ts)`.
- `nexus_execution/actuation/composition.py:51` — `build_runtime(infrastructure, timestamps=ts)` → `build_runtime(infrastructure, harness_registry=registry, timestamps=ts)`.

No other call site needed changing (`grep`-verified — all other `build_runtime(` calls are standalone
test helpers that intentionally build a runtime-only context, not a full pipeline).

**Regression coverage.** New `tests/integration/test_harness_registry_unity.py` (2 tests): asserts registry
*identity* (`pipeline.harness_registry is pipeline.runtime.harness_registry`) for both composition roots,
plus a functional check that a descriptor registered on one side is visible through the other's view. Both
pass; full affected-package sweep (`nexus_workflows`, `nexus_execution`, `nexus_runtime`, `nexus_orchestration`,
`tests/integration`) shows zero regressions (1023 passed, 1 pre-existing unrelated error, before the
rest of the suite was re-added).

**Follow-up refinement (found while closing the CI gap, §Validation).** Once `nexus_runtime` was
mypy-strict-checked against these two now-live call sites, mypy correctly flagged that
`nexus_orchestration.registry.InMemoryHarnessRegistry` and `nexus_runtime.runtime_registry.InMemoryHarnessRegistry`
are two distinct, nominally-unrelated classes — passing one where the other was declared broke type-checking
even though both structurally satisfy the same shape and the fix worked correctly at runtime. This is
Risk R2 (§1.2) made concrete by the type checker, not a new bug. Fixed by typing `build_runtime`'s
`harness_registry` parameter, `RuntimeContext.harness_registry`, and `RuntimeRegistry.__init__` against
the shared `nexus_core.registries.interfaces.HarnessRegistry` **Protocol** (INV-36's own frozen interface)
instead of either concrete class — `nexus_runtime/runtime_registry.py`'s own docstring already stated this
was the intent ("every consumer depends on the `HarnessRegistry` Protocol... so the reference is
swappable"), so this aligns the code with its own stated design rather than introducing a new one. Purely
a type-annotation change (three signatures); no behavior changed. R2 (the underlying class duplication)
remains open and undoing it — collapsing two independently-coded classes into one canonical location —
is left as a documented recommendation, not fixed here, since it touches which package "owns" the
canonical registry implementation.

Final full v2 sweep after every fix in this program: **2927 passed, 1 opt-in skip, 1 pre-existing
unrelated error** (`test_state_machines.py` — `db_session` fixture, stripped by `--noconftest`, unrelated
to this program). Mypy-strict clean across all 30 v2 packages (387 source files, zero errors). Ruff
(lint + format) clean across the same scope. Coverage gate: 97.97% (95% required), unaffected.

This is the only code fix applied in Phase 1. It is a pure wiring correction (an already-existing
constructor parameter simply wasn't being passed) — it moves no decision boundary, changes no invariant's
meaning, and does not qualify as an architectural redesign.

### 1.5 Fix investigated and reverted: FULLY_AUTOMATIC gate-taxonomy guard

I initially attempted to gate `AutonomousExecutionCoordinator`'s `FULLY_AUTOMATIC` auto-approval loop on
each waiting gate's own declared taxonomy (only auto-approve `AUTOMATIC`-tagged gates, leave
`HUMAN_REVIEW`/`MULTI_STAGE`/`DEFERRED` gates pending for a human). This broke two existing, deliberately
written P16 tests (`test_fully_automatic_auto_approves_when_policy_permits`,
`test_policy_controlled_auto_approval`) that explicitly assert a `HUMAN_REVIEW`-gated node under a
`FULLY_AUTOMATIC` schedule auto-approves and completes. That is reviewed, intentional P16 behavior, not
an oversight — changing it is a behavioral/architectural decision, not an additive audit fix. **Reverted
in full**; documented as Risk R5 above (§1.2) for an explicit operator/policy decision rather than a
silent code change.

### 1.6 Notes (low severity, documented for completeness)

- No CI-enforced guardrail asserts the `async def`-in-`nexus_core` count stays 0 — ADR-007 declares this
  invariant but it is currently checked only by manual/ad-hoc grep, not a test.
- `nexus_scheduler/dispatcher.py` hardcodes `policy_allowed=True, policy_decision="not_applicable"` for
  scheduled platform operations (health/diagnostics/runtime-refresh/replay — all read-only) instead of
  querying Policy even ungoverned. Harmless in practice (flagged by its own auditor as such); a literal
  INV-28 letter-of-the-law gap.
- `nexus_integration/flags.py`'s `FlagStore` correctly defaults every unknown owner to disabled
  (fail-closed spec) but is dormant since nothing calls it from live code (see R1).
- Two unrelated classes are both named `PolicyContext` (`nexus_engineering/model.py:42`, EI's read-only
  policy-verdict projection; `nexus_policy/composition.py:27`, the Policy composition-root bundle) —
  verified this is a harmless naming coincidence, not an INV-07 violation (different objects, different
  modules). Downgraded from the P12/P13 reports' framing of this as an open "finding."
- `execution.*` traversal events carry `producer="runtime"` (shared event builder) rather than a distinct
  `execution`/`actuation` producer constant — a lineage-attribution nuance already self-identified in P12
  (finding F-6, "Low," reconfirmed unchanged through P16). Each event still has exactly one producer and
  reconstruction is lossless; cosmetic.
- `nexus_operator`/`nexus_research` are legitimate top-level consumer/application packages sitting above
  the entire spine (self-documented, imported by nothing in production code) — not code violations, but
  their names collide with the Constitution's still-unbuilt "Operator Profile" grounding subsystem and a
  "Research" capability that does not exist in the Constitution at all. Worth a naming clarification
  before GA docs are finalized.
- `tests/integration/test_constitutional_spine.py` (the primary end-to-end proof) covers full real-engine
  traversal, determinism, durable replay, and 3 restart scenarios — but does **not** cover a real
  `ApprovalExchange`/Human-Interaction round-trip (`granted_gates` is passed as a static tuple in that
  test, never sourced live), the ADR-008 shadow substrate combined with a spine run, real runtime
  execution (still `StubClaudeInvoker` throughout — "Runtime executes" remains simulated in every existing
  test), concurrent/multi-session pipelines, or malformed-input handling. These gaps are exactly what
  Phase 2 (Failure Testing) and Phase 4 (Scale) below are for.
- Version/changelog signals disagree: `pyproject.toml` says `0.1.0`; `nexus_workflows/__init__.py` says
  `2.0.0a1`; `CHANGELOG.md`'s latest entry is `[1.1.0]` (2026-06-25) and is entirely v1-scoped; the
  README's "authoritative" status doc (`blueprint/STATUS.md`, dated 2026-06-24) never mentions
  `nexus_workflows/spine` at all. No single source of truth currently describes the v2 spine's release
  state.
- **None of P9–P16's work is committed to git.** `nexus_workflows/spine/`, `nexus_execution/actuation/`,
  `nexus_human_interaction/`, `nexus_planning/grounded/`, `nexus_approval/`, `nexus_operations/`,
  `nexus_scheduler/`, and all P10–P16 report docs are untracked; `nexus_policy/__init__.py`,
  `nexus_policy/defaults.py`, and `nexus_workflows/pipeline.py` are modified-but-uncommitted.
  `git log` returns nothing for any `spine/*.py` file. Independently confirmed by two audit agents and by
  me. This is the single largest practical blocker to treating any P9–P16 claim as "shipped" — see the
  GA Checklist.

### 1.7 An open constitutional void (not a violation): Observation / Supervise-Observe

The Constitution's capability #9 (**OBSERVE**, owner: Supervision) is never built as its own subsystem
through P16, and the frozen `contracts/observation.md` `Observation` object has **zero producers anywhere
in the codebase** (verified directly: `grep -rn "Observation("` over the whole tree returns only the
domain-object definition itself and its own unit test — no subsystem ever constructs one from real
execution facts). This is not a violation of any invariant — INV-11 assigns Observation production to
Supervision, and Supervision was simply never built. The Constitution's own Simplification #2 ("MERGE the
Supervision layer into the Operations/Observe capability") suggests Operations (`nexus_operations`, P15)
was meant to absorb this responsibility, but Operations was deliberately built to produce only read-only
projections and instrumentation, not the frozen `Observation` domain object (a design choice already made
correctly in P15 to keep Operations from constructing a domain object it doesn't own). The practical
effect: Recovery and Orchestration operate directly on raw execution facts and a bounded `RecoveryPolicy`
today, without ever consuming an `Observation` — which the Execution-cluster audit confirmed is internally
consistent (INV-20/21/22 all hold without it) — but it means one piece of the ratified capability model
is simply absent, not deferred-and-compensated-for. Recommended for a future program, not fixed here (a
new subsystem is explicitly out of scope for P17's "no new constitutional capabilities" rule).

---

## Phase 2 — Failure Testing

**Method.** Inventoried existing restart/interruption/failure coverage across `tests/integration/`
before writing anything new (avoid duplicating what already exists — see the file list this program
grepped). Six of the nine required failure classes already had genuine, non-cosmetic tests (asserting
reconstructed-state equality or an identical decision, not merely "doesn't crash"); all six were
directly re-run for this report, not assumed from memory. Three classes were under-covered — a real
OS-level process crash (all existing "restart" tests are controlled close-and-reopen, not a hard kill),
replay's safety under interruption/repetition, and a Recovery decision's durability across a restart —
and got new, targeted tests in `tests/integration/test_p17_failure_resilience.py`.

### 2.1 Evidence per required failure class

| # | Failure class | Evidence | Result |
|---|---|---|---|
| 1 | **Runtime failures** | `test_recovery_pipeline.py::test_claude_failure_is_recovered_retry`, `test_validation_pipeline.py::test_claude_failure_is_validated_failed`, `test_cross_runtime.py::test_failure_flow_is_identical_across_runtimes` (re-run live) | PASS — a failing runtime deterministically yields `ValidationDecision.FAILED` → `RecoveryDecision.RETRY`, identically across every runtime adapter |
| 2 | **Pipeline interruption** | `test_constitutional_spine.py::test_pipeline_restarts_after_a_mid_execution_interruption`, `::test_pipeline_restarts_from_the_last_completed_stage` (re-run live) | PASS — a spine run killed mid-stage resumes from the last completed stage, never re-executes a finished one |
| 3 | **Scheduler interruption** | `test_scheduler.py::test_restart_never_double_dispatches` (re-run live) | PASS — an occurrence dispatched before a restart is never re-dispatched after one; exactly one `pipeline.completed` survives |
| 4 | **Approval interruption** | `test_approval_exchange.py::test_restart_resumes_an_in_flight_approval_wait`, `::test_replay_reconstructs_identical_approval_history` (re-run live) | PASS — a pending approval survives a restart and resumes/replays identically |
| 5 | **Database restart** | Full `test_durable_restart.py` (7 tests: history, projection replay, identical-input replay, global ordering, snapshot+tail vs. full replay, idempotent re-append, UnitOfWork commit survival) — re-run live | PASS — all 7 |
| 6 | **Process crash** | **New:** `test_p17_failure_resilience.py::test_process_crash_mid_transaction_leaves_only_committed_writes` — a genuine subprocess is `kill()`-ed (`TerminateProcess` on Windows / `SIGKILL`-equivalent) mid-transaction, synchronized via a filesystem marker (no sleep-based race) so the kill lands exactly inside an open, uncommitted `BEGIN` | PASS — the prior committed write survives; the uncommitted write **never appears** after recovery (SQLite WAL atomicity holds across a hard kill, not just a clean close); the recovered connection is immediately reusable |
| 7 | **Partial execution** | `test_constitutional_platform.py::test_execution_actuation_restarts_over_the_durable_log` (re-run live) — a multi-wave actuation stopped after node-a resumes over a reopened file and completes node-b without re-running node-a | PASS |
| 8 | **Replay interruption** | **New:** `test_p17_failure_resilience.py::test_replay_is_idempotent_and_safe_to_repeat` — a partial read (simulating an interrupted replay), three full replays in a row, and three consecutive file reopenings all reproduce byte-identical ordering; replay never appends to the log (`global_length()` unchanged throughout) | PASS |
| 9 | **Recovery interruption** | **New:** `test_p17_failure_resilience.py::test_recovery_decision_is_durable_and_deterministic_across_restart` — a Recovery decision recorded before a restart replays byte-identically after one, and re-invoking the Recovery engine over the replayed facts reaches the identical plan (`RETRY`, same `retry_eligible`) | PASS |

**19/19 tests green** (16 pre-existing, re-verified live; 3 new). No new test doubles as a substitute
for a missing scenario — every row above is a genuinely distinct failure mode with its own assertion on
reconstructed state, not a restatement of the same restart test under a different name.

### 2.2 What this does and does not prove

Proves: every failure class named in the P17 program is handled deterministically — a restart or crash
never loses committed state, never double-executes, never re-decides a governed outcome differently, and
never corrupts the durable store. Does **not** prove: behavior under a crash *during* the SQLite `COMMIT`
statement itself (as opposed to before it) — SQLite's own atomic-commit guarantee is well-established
and out of scope to re-derive here, but this program did not fault-inject at that specific instant;
concurrent multi-process access to one durable file (the single-shared-connection design, see Phase 4 §4.3,
was not exercised under a crash); or a crash inside the v1 stack (out of this program's v2 scope).


## Phase 3 — Performance

**Method.** `scripts/p17_benchmark.py` (new, additive operational tooling) measures every metric the
program asks for using the real composition roots (`build_durable_infrastructure`,
`build_constitutional_pipeline`, `build_scheduler`, `build_execution_actuation`) — no mocks, no
synthetic timing harness. Run with `.venv/Scripts/python.exe scripts/p17_benchmark.py`. Single-machine,
single-run numbers (Windows, this environment) — order-of-magnitude and shape (linear vs. quadratic),
not calibrated production SLAs. No optimization was attempted; per Phase 3's own instruction this
program measures and reports only.

### 3.1 Results

| Metric | Result |
|---|---|
| Pipeline startup — in-memory `InfrastructureContext` | 0.03 ms |
| Pipeline startup — durable `InfrastructureContext` (fresh SQLite file) | 8.2 ms |
| Pipeline startup — full constitutional spine wiring (9 stages) | 0.7 ms |
| Event throughput — in-memory append, 2000 events/1 txn | 140,677 events/sec |
| Event throughput — durable append, 2000 events/1 txn | 16,709 events/sec |
| **Persistence overhead** — durable vs. in-memory (same batched op) | **8.4×** |
| Event throughput — durable append, 200 events/**1 txn each** (realistic per-decision pattern) | 2,246 events/sec (0.45 ms/event) |
| Replay throughput — `read_all()` over 2200 durable events | 155,335 events/sec |
| Restart latency — reopen + full replay, 2200 events | 15.5 ms |
| Execution latency — single-node actuation traversal (stub runtime) | 0.78 ms |
| Scheduler latency — `tick()`, 10 registered (non-due) schedules | 0.5 ms |
| Scheduler latency — `tick()`, 100 registered (non-due) schedules | 43.1 ms |
| Scheduler latency — `tick()`, 500 registered (non-due) schedules | **1136.6 ms** |
| Autonomous execution overhead — direct `pipeline.run()` | 5.1 ms |
| Autonomous execution overhead — `scheduler.tick()` dispatch (timing + provenance + run) | 4.4 ms (no measurable overhead — within run-to-run noise) |
| Memory usage — peak, 5000 events held in-memory | 10.0 MiB |
| Memory usage — peak, one full Goal→Knowledge spine run | 0.5 MiB |

### 3.2 Finding: `Scheduler.tick()` is quadratic in the number of registered schedules

The scheduler latency numbers above are not linear (10→100 schedules: ~80× slower; 100→500: ~26×
slower — consistent with O(schedules × events), not O(events)). Root-caused by reading the actual code,
not just fitting a curve: `Scheduler.tick()` (`nexus_scheduler/scheduler.py:124-136`) loops
`for schedule in reconstruct_schedules(self._history())` and, **on every iteration**, calls
`self._maybe_complete(schedule.identity, ...)` (line 135), which itself calls
`reconstruct_schedule(self._history(), identity)` (line 182) — a **second full fetch of the entire
event history and a second full reconstruction of every schedule**, just to find the one matching
`identity`. `reconstruct_schedules` itself (`nexus_scheduler/registry.py:49-69`) is a single efficient
O(events) linear pass — the quadratic cost is entirely in `tick()` re-deriving the whole schedule set
once per registered schedule to check completion. At 500 schedules this makes one `tick()` call take
over a second; at a larger fleet the cost would keep growing quadratically. **Not fixed** — restructuring
the completion check to reuse the outer loop's already-reconstructed schedule (an O(1) lookup instead of
a second O(events) reconstruction) is a real, well-scoped future fix, but it touches the scheduler's core
dispatch loop, which is beyond this program's additive-only, no-redesign mandate this late in the audit.
Documented as a **scale ceiling**, carried into the GA checklist and Phase 4.

### 3.3 Other observations

- **Persistence overhead (8.4×) is durability's honest price**, not a defect — SQLite WAL commit +
  serialization vs. a bare in-memory list append. 16,700 events/sec in a single batched transaction is
  comfortably above any load this platform's own event volume (schedules, approvals, pipeline stages)
  would plausibly generate; the realistic one-decision-per-transaction pattern (2,246 events/sec) is the
  number that matters operationally, and it's still fast relative to human-paced governance decisions.
- **Scheduler-mediated dispatch shows no measurable overhead** over a direct pipeline run for a single
  goal — the entire autonomy layer (Policy consult, provenance recording, Approval Exchange publish) adds
  no discernible cost until the O(n²) `tick()` scan (§3.2) dominates at higher schedule counts.
- **Memory usage is not a near-term concern** at the scales tested (10 MiB for 5000 in-memory events; a
  full spine run peaks under 1 MiB) — Phase 4 pushes this further.


## Phase 4 — Scale

**Method.** `scripts/p17_scale.py` (new, additive operational tooling), same composition roots as
Phase 3, pushed to larger N per dimension. Every dimension the program asks for was measured.

### 4.1 Results

| Dimension | Result |
|---|---|
| **Many concurrent pipeline sessions** — 50 sequential Goal→Knowledge runs over one shared durable log | 1533 ms total, 30.7 ms/run, **50/50 completed**, 904 events on the shared log — linear, no contention observed |
| **Many scheduled jobs** — `tick()` at 500 registered schedules | **1865 ms** |
| **Many scheduled jobs** — `tick()` at 1000 registered schedules | **9571 ms** (~5× for 2× the schedules — confirms the O(n²) finding from Phase 3 §3.2 at a larger scale; run stopped here, already past a 3-second operational budget) |
| **Many approvals** — 40 independent gated sessions (publish + approve each), one shared Approval Exchange | first-5 average 3.80 ms/session vs. last-5 average 3.64 ms/session — **flat (1.0×)**, no degradation as approval history accumulates |
| **Large execution graph** — 60-node actuation traversal | 34.9 ms, 60/60 completed |
| **Large knowledge store** — ingest 500 distinct candidates | 58.2 ms total, 8584 ingests/sec; `list_all()` over the resulting 500 items: 0.01 ms |
| **Replay at scale** — `read_all()` over 20,000 durable events | 238 ms, 84,028 events/sec |
| **Restart at scale** — reopen + full replay, 20,000 events | 263 ms |

### 4.2 Observed limits

- **`nexus_scheduler.Scheduler.tick()` is the one genuine scale ceiling found anywhere in the platform.**
  At ~1000 concurrently-registered schedules, a single `tick()` call takes **~9.6 seconds** — for a
  platform whose scheduler is meant to be polled/ticked frequently (autonomous operation), this is an
  operationally real limit well below what a production governed-autonomy deployment might plausibly
  want to register (hundreds to low thousands of recurring jobs across an organization). Root cause is
  architectural, not incidental (§3.2) — a per-schedule full-history re-reconstruction inside the
  completion check — so the ceiling scales quadratically, not linearly, meaning it degrades sharply
  rather than gracefully as schedule count grows. **This is the single most significant production risk
  this program's measurement phases found.**
- **Everything else scales linearly and comfortably** at the tested scales: 50 concurrent sessions,
  40-session approval history, a 60-node execution graph, a 500-item knowledge store, and a 20,000-event
  durable log all show no quadratic behavior, no resource contention, and no correctness degradation.
  The single-shared-SQLite-connection design flagged in Phase 1 (§1.2, foundational risk about the
  self-documented `# ponytail: single-threaded` comment) was not stress-tested under genuine concurrent
  (multi-thread/multi-process) access in this program — only sequential load at increasing volume — so
  "no contention observed" here specifically means no contention under sequential load, not a clearance
  of concurrent-access safety.
- 20,000 events is a modest scale for a long-lived production log (a single moderately active governed
  platform could exceed this in weeks); the fact that replay/restart stayed linear (84k events/sec) up
  to that point is a positive signal but was not pushed further (e.g., 500k+ events) within this
  program's time budget — flagged as an area for a future, larger-scale soak test rather than asserted
  as unlimited.

## Phase 5 — Operational Readiness

**Method.** Direct verification against the running code (no dashboards, per the program's own
instruction — operational correctness only) for each named checklist item.

| Item | Finding |
|---|---|
| **Startup** | Every composition root (`build_infrastructure`, `build_durable_infrastructure`, `build_constitutional_pipeline`, `build_scheduler`) boots cleanly and fast (Phase 3: 0.03–8.2 ms cold). No hidden global state, no required environment setup — confirmed by Phase 1's audit (pure DI throughout) and by every benchmark/scale script in this program running with zero setup beyond an import. |
| **Shutdown** | **No explicit `close()`/`shutdown()` exists anywhere in the durable infrastructure** (`grep` confirmed zero matches in `nexus_infra/durable.py` and `composition.py`). The single shared `sqlite3.Connection` (autocommit mode, WAL) is released only when the Python object is garbage-collected or the process exits. Phase 2's crash test (§2.1, row 6) confirms this is *safe* — SQLite's own atomicity holds even on an unclean exit — but there is no graceful-shutdown hook an operator could use to flush/checkpoint the WAL deliberately before a planned stop. Low risk (proven safe by the crash test) but a real API gap. |
| **Deployment** | v1 has a working `docker/Dockerfile` (confirmed by the spine-cluster audit, §1.1 V1) — but it launches `nexus.api:app` (v1) exclusively. **There is no deployment artifact, Dockerfile stage, or documented procedure for running the v2 constitutional spine as a service today.** A v2 deployment today would mean an operator writing their own process wrapper around `nexus_workflows.spine.build_constitutional_pipeline` — nothing packaged does this. |
| **Configuration** | **Zero environment-variable or config-file usage anywhere in v2** (`grep` for `os.environ`/`os.getenv`/`pydantic_settings`/`BaseSettings` across all 31 `nexus_*` v2 packages returns nothing). Every composition root takes explicit constructor parameters — deliberate, disciplined DI (a real strength for testability and determinism) but it also means there is currently no "configure this for production" story: no way to point a deployed v2 instance at a db path, a log level, or a policy file via the environment; a caller must write that wiring themselves. |
| **Migrations** | Confirmed in Phase 1 (§1.2 context): the durable schema uses `CREATE TABLE IF NOT EXISTS` only (`nexus_infra/durable.py:57-91`) — idempotent bootstrap, **no version tracking, no migration mechanism** of any kind. A future schema change (e.g., a new indexed column) has no upgrade path for an existing durable file; today the schema has been stable enough that this has not yet mattered, but it is a real gap before a first production cutover. |
| **Logging** | **Zero use of `logging`/`structlog` anywhere in v2 before this program.** Fixed additively (§5.1 below): `nexus_infra.LoggingObservability`, a new stdlib-`logging`-backed implementation of the existing `Observability` protocol. |
| **Diagnostics** | `nexus_operations.DiagnosticsService` (P15) exists, is wired, and is tested — event-producer/type consistency checks, no missing-producer detection, unique-id verification. Confirmed live via the governance-cluster audit (zero write paths back into execution — read-only, as designed). |
| **Observability** | Prior to this program: `NullObservability` (discard) and `InMemoryObservability` (test-only, process-local, lost on exit) were the only two implementations of the `Observability` protocol — no sink an operator could read after the process exited. Fixed additively (§5.1). |
| **Health reporting** | `nexus_operations.HealthInspector` (P15) exists, is wired, records durable `operations.snapshot` events, and is tested. Confirmed sound by the governance-cluster audit. No gap found here. |

### 5.1 Fix applied: a production-usable Observability sink

**What was missing.** The `Observability` protocol (`record`/`increment`/`observe`) is correctly designed
for extension — but the platform shipped with exactly two implementations, both unsuitable for
production: `NullObservability` discards everything, and `InMemoryObservability` is explicitly
documented as "for tests and local inspection" (it accumulates in a Python list with no eviction — using
it in a long-running process is a memory leak, not a sink).

**Fix.** Added `nexus_infra.LoggingObservability` — a third protocol-conforming implementation that
writes each infrastructure event, counter, and observation as one structured `logging` record via a
named `"nexus.infra"` logger (or an injected one). Errors (`HANDLER_FAILED`, `CONCURRENCY_CONFLICT`,
`EVENT_DEAD_LETTERED`) log at `WARNING`; everything else at `INFO`. An operator wires it in by passing
`observability=LoggingObservability()` to any composition root (the same seam every other Observability
implementation already uses — zero API change) and configuring the `"nexus.infra"` logger's handler
(file, stdout, a log-shipping handler) with ordinary stdlib `logging` configuration. No new dependency —
stdlib `logging` only, matching everything else the platform already depends on.

**Regression coverage.** 4 new tests in `tests/unit/nexus_infra/test_observability.py` (INFO-level
event logging, WARNING-level for conflict/failure/dead-letter types, counter/observation logging, and
the default logger name). `nexus_infra`'s full suite (230 tests), mypy-strict, and ruff (lint + format)
all pass clean — `nexus_infra` is in the CI gate, so this addition is fully covered by the existing
quality bar, not exempted from it.

This closes the Logging and Observability rows above. Deployment, Configuration, Migrations, and
Shutdown remain open gaps — each is a genuine "build this" item (a Dockerfile stage, a settings loader,
a migration tool, a shutdown hook) rather than a small wiring correction, so per this program's
additive-only mandate they are documented here and carried into the GA Checklist rather than built.

## Phase 6 — Documentation

Produced `docs/v2/OPERATOR_GUIDE.md` — a single consolidated operator guide (one file, not ten
fragments, for ctrl-F navigability) covering every required section: architecture overview, subsystem
map (every `nexus_*` package, its capability, what it owns, its producer prefix), the execution lifecycle
(Goal→Knowledge, with the approval-gate pause point called out), the replay model, the restart model, the
approval model, the scheduler model (including the §3.2/§4.2 O(n²) ceiling, stated as an operational
warning with a concrete "don't do this" threshold), the learning loop, a troubleshooting table grounded
in this program's own findings (including the pre-existing unrelated `test_state_machines` failure so
operators don't mistake it for a regression), and an extension guide encoding the pattern every P0–P16
program actually followed (one producer, consult-not-evaluate Policy, reconstruct-from-log, the
determinism seam, drive execution only through the pipeline, wire into all three CI gates, write the
three guardrail-test classes). Every claim in it is traceable to a specific finding or test elsewhere in
this program — nothing was described from memory of the architecture without checking the current code.

## Phase 7 — Release Readiness

### 7.1 Packaging

`pyproject.toml` (hatchling build backend) explicitly lists all 31 `nexus_*` v2 packages plus `nexus`
(v1) under `[tool.hatch.build.targets.wheel] packages` — confirmed complete and current (matches the
actual package directories on disk 1:1). `uv build` (the CI `build` job) succeeds. **The only
`[project.scripts]` entry (`nexus = "nexus.__main__:main"`) launches v1** — there is no installed
console entrypoint for v2 at all (restates Phase 1 §1.1 V1 in packaging terms: even if a user `pip
install`s this project today, there is no `nexus-spine` or equivalent command to run).

### 7.2 Versioning

No single coherent version exists for v2. Four different signals disagree:

| Source | Value |
|---|---|
| `pyproject.toml` `[project] version` | `0.1.0` |
| `nexus_workflows/__init__.py` `__version__` | `2.0.0a1` |
| `CHANGELOG.md` latest entry | `[1.1.0]` (2026-06-25) — entirely v1-scoped, zero P0–P16/v2 entries |
| README badges / `blueprint/STATUS.md` | "released v1.0.0", "v1.0.1 Alignment in progress" — v1 only, never mentions `nexus_workflows/spine` |
| `contracts/` (18 frozen schemas) | no version field visible per-contract; no contract-versioning scheme found |

Before any GA claim, pick one authoritative version identifier for the v2 spine and update all of the
above to agree — this is pure hygiene, not a code change, and out of scope for this program to decide
unilaterally (a product/release-management call).

### 7.3 API stability

The closest thing v2 has to a public API is the 18 frozen `contracts/*.md` schemas (INV-07) plus each
package's `composition.py` `build_*` functions (the DI seams every consumer uses). Neither has an
explicit stability/versioning policy:
- **Two objects with real, multi-consumer shapes were never frozen** (`engineering_strategy`,
  `repository_understanding` — Phase 1 §1.2 R7), despite the Constitution's own freeze trigger having
  been met. Until frozen, their shape can change without the formal process the other 18 objects get.
- **No deprecation/compatibility policy exists** for a `build_*` composition function's signature —
  changing one (as this program's own INV-36 fix did, adding a keyword-only parameter with a safe
  default, §1.4) is currently a purely social convention (grep for callers, update them), not a checked
  contract.
- This is expected and appropriate for a **pre-GA** codebase — flagged here as a "define before GA," not
  as a defect.

### 7.4 Migration guidance

- **Schema migration:** none exists (Phase 5) — a future durable-schema change has no upgrade path for
  an existing file. Needed before any long-lived production deployment.
- **v1→v2 data migration:** the two strata are fully isolated (Phase 1: zero cross-imports, confirmed
  both directions) and **use entirely different persistence models** (v1: async SQLAlchemy CRUD +
  separate append-only audit log; v2: synchronous, fully event-sourced). No tool, script, or documented
  procedure exists to migrate v1's existing pilot data (tasks, approvals, memory) into v2's event log —
  this was always going to be required for a real cutover (per the Engineering Program's own P10 "Spine
  Convergence & Cutover" — never reached) and remains unaddressed.

### 7.5 Dependency inventory

Enumerated by AST-scanning every import statement across all 31 `nexus_*` v2 packages (not just what
`pyproject.toml` declares — what the code actually imports):

- **The entire v2 spine's third-party footprint is exactly one package: `pydantic` (>=2.0, locked to
  2.13.4 in `uv.lock`).** Every other import across `nexus_intent`, `nexus_engineering`, `nexus_policy`,
  `nexus_scheduler`, `nexus_workflows/spine`, and every other v2 package is either stdlib or another
  `nexus_*` package. The runtime adapter packages (`nexus_runtime_claude/_gemini/_shell`) import zero
  third-party packages — stdlib only (they shell out to external CLIs rather than using a provider SDK).
- `pyproject.toml`'s top-level `dependencies` list (fastapi, uvicorn, sqlalchemy[asyncio], aiosqlite,
  pydantic-settings, structlog, apscheduler, discord.py, httpx, jinja2, aiosmtplib, python-dotenv, pyyaml)
  is **entirely v1's dependency surface** — v2 needs none of it except the shared `pydantic`.
- `pydantic` is pinned with no upper bound (`>=2.0`) — recommend adding a `<3` ceiling before GA so a
  future breaking pydantic major version can't silently break the build; a one-line, low-risk change but
  one that affects the whole project's shared dependency, so left as a recommendation rather than made
  unilaterally here.
- `uv.lock` exists, is committed, and matches `pyproject.toml` (`git status` shows no drift) — dependency
  resolution is reproducible.
- No live CVE/vulnerability database lookup was performed in this program (no network access exercised
  for this purpose) — recommend `uv pip audit` (or equivalent) as a release-checklist gate, not asserted
  as clean here.

### 7.6 Security review

- **No secrets found in tracked files** — no committed `.env*` files (`.gitignore` correctly excludes
  them), no hardcoded API-key/password/token-shaped literals found by pattern search across v2 source.
- **v2 has no network/HTTP/shell surface of its own** — the entire spine is a local, in-process,
  synchronous event-sourcing library; the only I/O boundary is the SQLite file and (behind the Harness
  boundary) whatever a runtime adapter shells out to. This is a small, auditable attack surface by
  construction.
- **The durable event log stores payloads in plaintext JSON** on local disk (`nexus_infra/durable.py`) —
  reasonable for the current local/single-operator threat model the platform targets, but worth an
  explicit decision before any deployment where the event log might contain sensitive operator data and
  the filesystem isn't already trusted (encryption-at-rest is not this platform's job, but operators
  should know payloads aren't redacted or encrypted by the platform itself).
- **Zero `TODO`/`FIXME`/`XXX` markers** anywhere in the 31 v2 packages — no known-incomplete work left as
  a silent marker.
- Nothing in this program's scope constitutes a penetration test; this is a code/dependency/secrets
  review only.

### 7.7 Release checklist (GA blockers vs. hygiene)

**Blockers (must resolve before a v2 GA claim):**
1. No process entrypoint launches v2 (Phase 1 §1.1 V1) — a real cutover decision, not made in this
   program.
2. `nexus_scheduler.tick()`'s O(n²) ceiling (§3.2/§4.2) — a real production risk for any deployment
   using more than a few hundred schedules.
3. None of P9–P16's work (the entire spine, actuation, human interaction, approval exchange, operations,
   scheduler) is committed to git (Phase 1 §1.6) — nothing above can be "released" until it exists on a
   branch that ships.
4. No schema migration mechanism (§7.4) — acceptable only if the durable schema is treated as frozen
   until this exists.
5. No v1→v2 data migration path (§7.4) — required if cutover is meant to preserve existing pilot data.

**Should-fix (real but not release-blocking on their own):**
6. `nexus_integration`'s ADR-008 substrate is fully built and tested but unwired (Phase 1 §1.2 R1) —
   either wire it in for a genuine flagged/shadowed cutover, or formally retire it and document the
   direct-cutover decision that superseded it.
7. INV-37 runtime-selection ownership (Phase 1 §1.1 V3) — needs an ADR either ratifying joint
   Orchestration+Runtime ownership or relocating the decision point.
8. `WorkflowCoordinator` duplicate driver (Phase 1 §1.2 R4) — retire once confirmed unreferenced, or
   formally document why it remains.
9. Freeze `engineering_strategy` and `repository_understanding` contracts (§7.3).
10. ~~Seven packages outside all three CI quality gates~~ — **closed during this program**, see
    Validation below. One narrower item remains: `nexus_repository` and `nexus_scheduler` are not yet
    in the coverage-gated `--cov=` list (60% and ~90% on their lowest-covered modules) — closing that
    honestly needs new tests for `nexus_repository/discovery.py`'s framework/build-detection branches and
    `nexus_scheduler/scheduled_operations.py`, not a config change.

**Hygiene (low risk, easy, worth doing):**
11. Reconcile the version/changelog/status-doc disagreement (§7.2).
12. Add a `pydantic<3` upper bound (§7.5).
13. Add `uv pip audit` (or equivalent) to CI (§7.5).
14. Document the FULLY_AUTOMATIC gate-taxonomy behavior as an explicit operator decision, not a silent
    default (Phase 1 §1.2 R5).

## Validation

### Comprehensive coverage

Every item the program named is covered by a passing, directly-re-run test, not a claim:

| Area | Evidence |
|---|---|
| Replay determinism | Phase 2 §2.1 rows 5/8; Phase 1 §1.3 "replay/restart"; `test_replay_is_idempotent_and_safe_to_repeat` |
| Restart determinism | Phase 2 §2.1 rows 5/6/7; full `test_durable_restart.py` (7 tests) |
| End-to-end Goal → Knowledge | `test_constitutional_platform.py::test_back_spine_reaches_knowledge_with_real_engines` (all 10 engines participate, Knowledge recorded, evidence-backed) |
| Autonomous execution | `tests/integration/test_scheduler.py` (policy-auto-approval, approval-required→completed, restart-no-dup); Phase 3/4 scheduler benchmarks |
| Approval flow | `tests/integration/test_approval_exchange.py` (full suite); Phase 2 §2.1 row 4 |
| Scheduler | Phase 1 §1.2 (governance cluster, fully clean on ownership/purity); Phase 3/4 (the one real ceiling found) |
| Operations | Phase 1 §1.2/§1.3 (read-only, clean); `nexus_operations` test suite |
| Learning loop | `tests/integration/test_learning_loop.py`; Operator Guide §8 |
| Policy enforcement | Phase 1 §1.3 (sole evaluator, fail-closed, zero leakage — the most heavily cross-verified finding in this whole program, checked independently by all 5 cluster audits) |

### Full sweep (after every fix in this program)

```
2927 passed, 1 skipped (opt-in, requires an authenticated claude CLI), 1 error (pre-existing,
unrelated — test_state_machines.py needs v1's db_session fixture, stripped by --noconftest)
```

Zero regressions from any fix applied in this program, confirmed by running the affected-package suite
after each change and the full suite at the end.

### CI gap closed

Phase 1 found 7 packages (`nexus_policy`, `nexus_intent`, `nexus_engineering`, `nexus_estimation`,
`nexus_repository`, `nexus_integration`, `nexus_history`) entirely outside every CI quality gate, plus 4
more (`nexus_human_interaction`, `nexus_approval`, `nexus_operations`, `nexus_scheduler`, a known gap
since P14–P16) missing from ruff and the pytest job specifically. All 11:

1. **Fixed 46 real mypy-strict errors** across 17 files in the first 7 (missing/incorrect type
   annotations, one genuine type-inconsistency bug in `nexus_policy/precedence.py`'s tuple-ordering
   comparison — an annotation defect, not a runtime behavior bug, but exactly the kind of thing strict
   typing exists to catch before it becomes one).
2. **Added all 11 to `.github/workflows/core-ci.yml`'s ruff (lint + format) and mypy gates**, and to the
   pytest job's execution list — their dedicated unit and guardrail tests now run in the dedicated CI job,
   not only implicitly via v1's separate `ci.yml` sweep.
3. **Did not add `nexus_repository` or `nexus_scheduler` to the coverage-gated `--cov=` list** — their
   current coverage (60% and ~90% on specific modules) sits below the existing 95% `--cov-fail-under` gate;
   closing that honestly requires writing new tests for real branches (framework/build-system detection,
   scheduled-operations dispatch), which is out of this program's additive-fix scope. Documented as an
   open item (Release Readiness §7.7 #10), not silently skipped.
4. **A second, deeper issue surfaced by turning mypy on for real call sites**: the INV-36 fix (§1.4)
   only passed strict typing after also fixing the `HarnessRegistry` Protocol-vs-concrete-class typing
   Risk R2 had already flagged — direct confirmation that mypy strict on previously-ungated code finds
   real things, not just annotation busywork.

Final state: **mypy-strict clean across all 30 v2 packages (387 source files, 0 errors)**; **ruff
(lint + format) clean across the same 30 packages + all their test directories**; **2927 tests passing**;
**coverage gate 97.97%** (95% required, scope unchanged from before this program).

## GA Checklist & Final Recommendation

### GA Checklist

| # | Item | Status |
|---|---|---|
| 1 | No constitutional violations remain | ✗ — 2 of 3 remain (V1 entrypoint, V3 INV-37 ownership); 1 fixed (V2 INV-36) |
| 2 | Determinism demonstrated end-to-end | ✓ — INV-17 seam verified in every reasoning subsystem; zero wall-clock/randomness outside injected seams anywhere in v2 |
| 3 | Replay and restart are production-ready | ✓ — genuine equivalence proofs across every subsystem, plus a real OS-level crash test proving WAL atomicity; one caveat: 5 named repositories' "rebuildable from log alone" property (INV-14, strongest form) is unproven, though atomicity holds (R3) |
| 4 | Operational readiness documented | ✓ — `docs/v2/OPERATOR_GUIDE.md`; 4 of 9 checklist items were real gaps (shutdown, deployment, configuration, migrations), 2 fixed (logging, observability), rest documented |
| 5 | Performance characteristics measured | ✓ — `scripts/p17_benchmark.py`, `scripts/p17_scale.py`, re-runnable, real composition roots |
| 6 | Remaining risks explicitly documented | ✓ — 3 violations, 8 risks, 1 scale ceiling, all with file:line evidence, all in this report |
| 7 | GA recommendation with evidence | see below |

### Blockers to General Availability (unchanged from Phase 7 §7.7, restated as the headline)

1. **Nothing is committed to git.** The entire spine, actuation layer, human interaction, approval
   exchange, operations plane, and scheduler — everything P9 through P16 built, and every fix this
   program made — exists only in the working tree. There is no branch, no PR, no reviewable diff. This
   is not a code-quality finding; it means the "platform" this report certifies does not yet exist
   anywhere durable.
2. **No entrypoint launches it.** Even fully committed, nothing today boots the v2 spine as a running
   service — a caller must write their own driver script.
3. **The scheduler has a real, measured, production-relevant scale ceiling.** ~9.6s per `tick()` at
   1000 schedules, growing quadratically. Any deployment planning autonomous operation at meaningful
   scale hits this early.
4. **No schema migration path and no v1→v2 data migration path exist.** Fine for a greenfield v2-only
   deployment; a blocker for any cutover that must preserve today's v1 pilot data.
5. **INV-37's runtime-selection ownership needs a decision** (ratify joint ownership via ADR, or
   relocate the decision to Orchestration) before it's fair to call the platform's own invariant set
   internally consistent.

### What is genuinely solid

The reasoning spine's engineering is not in question: 20 distinct event producers with zero collisions;
correct one-way dependency flow everywhere checked (Reason never imports downstream, Planning never
imports Execution, Context never writes Knowledge, Recovery never touches the Goal); the INV-28 policy
boundary holds with zero exceptions across the entire repository; every replay/restart test that exists
proves genuine state equivalence, not just "didn't crash"; cross-stratum (v1/v2) isolation is real and
verified in both directions; and the platform's third-party dependency footprint is exactly one package
(`pydantic`). This is a codebase that was built with real discipline. The gap to GA is entirely in
*productization* — commit it, wire an entrypoint, fix the one scale ceiling, decide the two open
ownership questions — not in re-litigating the architecture.

### Final Recommendation

**Not recommended for General Availability today.** Recommended for GA once, in order:

1. The existing work is committed and reviewed (this is the precondition for everything else — a
   platform that isn't in version control isn't a platform yet).
2. A real entrypoint exists and is exercised by at least one deployment (even a minimal one).
3. The `Scheduler.tick()` quadratic-scan is fixed (reuse the outer loop's already-reconstructed schedule
   in `_maybe_complete` instead of a second full-history reconstruction — a well-understood, bounded fix,
   just correctly out of scope for an audit-only program to make unilaterally this late).
4. INV-37 ownership is formally resolved one way or the other.
5. A schema-migration story exists, at minimum a documented "the durable schema is frozen until v1"
   policy if nothing else.

None of these are architectural doubts — every one is a concrete, scoped, achievable piece of follow-up
work, and this report's own additive fixes (INV-36, the CI gap, the logging sink, three new failure-mode
tests) demonstrate the codebase responds well to exactly that kind of targeted closing work. **Recommend
scheduling a P18 focused narrowly on these five items** — commit-and-wire, the scheduler fix, the INV-37
decision, and migration groundwork — as a short, high-confidence path to a genuine GA recommendation,
rather than treating this as a signal to revisit the architecture itself.
