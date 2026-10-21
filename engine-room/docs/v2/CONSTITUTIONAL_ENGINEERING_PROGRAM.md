# Constitutional Engineering Program

**Status:** Engineering backlog — authoritative for execution planning
**Role:** Chief Engineer conversion of frozen architecture into executable work
**Governs:** v2.2 → v3.0
**Inputs (fixed, not re-opened here):**
- `ARCHITECTURE_CONSTITUTION.md` — *law*
- `CONSTITUTIONAL_MIGRATION_BLUEPRINT.md` — *migration is fixed*
- `IMPLEMENTATION_READINESS_REVIEW.md` — *authoritative verdict (APPROVED WITH CONDITIONS)*
- `99_ARCHITECTURAL_INVARIANTS.md` — *39 ratified invariants*
- `contracts/` — *18 frozen contracts*

> This document contains **no architecture, no code, and no redesign.** It identifies engineering work, sequences it, and defines how each piece is proven done. Where the Constitution marks an item `[Constitutional — ratify via new ADR]`, this program schedules the ADR as *work to be written*, never writes it.

---

## 0. How To Read This Document

**Verified ground truth (independently re-checked against the repository, not taken from prior reports):**

| Fact | Verified state |
|---|---|
| v1 (`nexus/`) | 69 files / 11,739 LOC. Async SQLAlchemy 2.x, `AsyncSession`, CRUD-authoritative + separate append-only `audit_log`. The **only** thing `__main__` launches (`uvicorn nexus.api:app`). Contains durable Memory, executable Policy service, Approvals, sandbox, Outbox/Scheduler. |
| v2 (`nexus_*`) | 20 packages, ~26.7k LOC. Synchronous, event-sourced, **in-memory only**. `async def` count = **0**. Durable persistence impls = **0**. Never wired into any entrypoint. |
| Cross-imports | v1 importing `nexus_` = **0**. v2 importing `nexus.` = **0**. The two strata are fully disjoint. |
| Persistence seam | `nexus_core/persistence/interfaces.py` — all sync `def`. Concrete impls all `InMemory*` in `nexus_infra/`. "Nothing here opens a connection." |
| Event transport | `InProcessEventBus` only. **No cross-process/cross-package event gateway.** |
| Feature flags / shadow | **None.** `grep feature_flag` = 0. No toggle/shadow infra anywhere. |
| Policy in v2 | Contract + domain object (`nexus_core/domain/policy.py`, "declarative, never executed") + `PolicyResolver` (`nexus_harness/policy_resolver.py`, "never evaluates") + `InMemoryPolicyRegistry`. **No evaluation engine.** Only executable policy engine = v1's. |
| Prototypes present | `nexus_workflows/{a0,a1,git_actions,human_approval,repo_intelligence,repo_profile}.py`, `scripts/{a0_run,a1_run}.py`, tests `test_a0_vertical`, `test_a1_governed_approval`, `test_a2_repo_profile`. |
| Tests | 189 test files / 235 total `.py`. |

**The central engineering fact:** ~60% of the constitutional substrate already exists — *in v1*, in the wrong shape (async CRUD) for a v2 spine that is (sync, event-sourced). The program is therefore **convergence, not construction**, and the single largest risk cluster is the **persistence authority seam** (sync-vs-async, CRUD-vs-event-log, INV-13/14).

**Work-package field key.** Every work package (WP) below carries the nine mandatory fields:
`Purpose · Scope · Inputs · Outputs · Dependencies · Acceptance Criteria · Tests Required · Risks · Rollback`.

**Notation:** `⟶` unlocks · `⊣` blocked-by · `∥` parallelizable-with · `★` on critical path to "Runtime executes. Nexus thinks."

---

## 1. Executive Summary

The constitutional architecture is frozen and correct. It is not executable because:

1. **No decision closure.** Six readiness conditions (C1–C6) and eleven hidden decisions (H1–H11) gate all downstream work. The most dangerous is unresolved persistence authority (sync/async + CRUD/event-log), which, if built wrong, violates INV-13/14 irreversibly.
2. **No durable foundation.** The v2 spine persists nothing. Every capability that "thinks" loses its memory on process exit.
3. **No policy evaluation.** Governance is declarative in v2; the only engine that *evaluates* policy lives in v1 and is async CRUD.
4. **No integration substrate.** Strangler Fig migration presupposes feature flags, shadow-mode, and a cross-boundary event gateway — none of which exist.
5. **Reasoning capabilities are stubs.** Understand (Intent Resolution) and Reason (Engineering Intelligence + Estimation) — the two capabilities that make "Nexus thinks" true — are unbuilt.

This program defines **eleven engineering programs (P0–P10)**, decomposed into epics and independently shippable work packages, sequenced so the repository is **releasable after every milestone**. The critical path to *"Runtime executes. Nexus thinks."* runs:

> **P0 Decision Closure → P1 Durable Foundation → P2 Policy Engine → P3 Integration Substrate → P7 Intent Resolution → P8 Engineering Intelligence + Estimation → P10 first governed end-to-end cutover.**

Repository Intelligence (P4), Human Interaction (P5), Actuation (P6), and Operations (P9) are **required for governed autonomous production** but are **off the minimal thinking-path** and are scheduled in parallel bands.

**Roadmap in one line:** v2.2 governs & persists (P0+P1+P2) · v2.3 grounds & integrates (P3+P4+P5) · v2.4 acts & understands (P6+P7+P8-core) · v2.5 reasons & operates end-to-end (P8+P9, first constitutional workflow) · v3.0 full cutover & duplicate retirement (P10).

---

## 2. Engineering Programs

| ID | Program | Package(s) touched | Constitutional driver | On min. path? |
|---|---|---|---|---|
| **P0** | Decision Closure & Enabling ADRs | `docs/v2/` only | C1–C6, H1–H11; Readiness "move Policy + ADR-007/008 to front" | ★ (gate) |
| **P1** | Durable Foundation | `nexus_core`, `nexus_infra`, (v1 `nexus/memory`) | Void: Durable Memory; INV-13/14/17 | ★ |
| **P2** | Policy Engine | new `nexus_policy` (converge v1 `policy_service`) | INV-28/29/30; Policy sole evaluator | ★ |
| **P3** | Strangler Integration Substrate | `nexus_infra`, new `nexus_gateway` | H3 flag/shadow gap; INV-39; Blueprint Stages 0–1 | ★ |
| **P4** | Repository Intelligence | new `nexus_repository` (promote `repo_profile`) | Grounding plane; `repository_understanding` contract | — |
| **P5** | Human Interaction | new `nexus_human_interaction` (converge v1 approvals/discord) | Void: Human Interaction; INV-23 | — |
| **P6** | Actuation | new `nexus_actuation` (converge v1 sandbox) | Act capability; Harness boundary INV-34/35/36/37 | — |
| **P7** | Intent Resolution | new `nexus_intent` (promote `a0`/`a1`) | Understand capability; INV-17 seam | ★ |
| **P8** | Engineering Intelligence + Estimation | new `nexus_engineering`, `nexus_estimation` | Reason + Estimation capabilities; C3 | ★ |
| **P9** | Operations | new `nexus_operations` (converge v1 metrics/briefing) | Operations plane; C4 | — |
| **P10** | Spine Convergence & Cutover | all `nexus_*` + v1 retirement | First principle; Blueprint Stages 2–8 | ★ |

**Evidence-based additions/removals vs. the prompt's example list:**
- **Split** "Engineering Intelligence" and "Estimation" packaging but keep them one program (P8): they share the INV-17 determinism seam and Estimation is a dependency of Reason's plan-scoring, so co-locating avoids a false barrier while still freezing two contracts.
- **Merged** "Runtime integration" into P10 (the runtime adapters `nexus_runtime_claude/_gemini/_shell` already exist and pass tests; the work is *selection + cutover*, not construction).
- **Added** P3 as a first-class program: the readiness review's H3 proves flag/shadow/gateway is absent, and every migration stage after Stage 1 is blocked without it. It was implicit in the prompt's "Scheduler integration / Production migration"; evidence promotes it to explicit.
- **Removed** a standalone "Durable Memory" *and* "Scheduler" program split — Scheduler is one epic inside P9/P3 (v1 already has `nexus/scheduling/`), not a program.

---

## 3–4. Programs → Epics → Work Packages

> Each program lists its epics; each epic lists work packages with all nine fields. Acceptance criteria are **measurable**; no subjective "done."

---

### P0 — Decision Closure & Enabling ADRs  `★ gate`

*Meets readiness conditions C1–C6 and closes hidden decisions H1–H11. Produces documents only. No code. This program exists because building on H1/H2 (persistence authority) wrong is the one irreversible mistake.*

#### Epic P0.E1 — Persistence Authority Decision (C1)
**WP-P0.1 — Rewrite ADR-007 (sync/async boundary + event-log authority)**
- **Purpose:** Close H1 (sync spine vs. async v1 persistence) and H2 (CRUD-authoritative vs. event-sourced authority) so INV-13/14 cannot be violated by implementation drift.
- **Scope:** ADR document only: decide where the async boundary sits, how the sync event-sourced spine reaches async durable storage, and which store is the source of truth. Explicitly rule on projection rebuild.
- **Inputs:** `interfaces.py` (sync), v1 `nexus/memory/*` (async CRUD + audit_log), INV-13/14/17, Blueprint ADR Roadmap 005–010.
- **Outputs:** `docs/v2/adr/ADR-007-persistence-authority.md` (status: Accepted).
- **Dependencies:** none — this is the root gate. `⟶` P1 entirely.
- **Acceptance Criteria:** ADR states (a) the authoritative store, (b) sync↔async crossing mechanism, (c) rebuild-from-events guarantee, (d) explicit list of which INV it satisfies and how; reviewed and marked Accepted; no open questions remain in an "Unresolved" section.
- **Tests Required:** N/A (document). Guardrail test *specified* (not written) for P1 to enforce the ADR.
- **Risks:** Wrong call forces a full P1 rebuild (R-critical). Mitigate by requiring an executable spike reference (WP-P1.1) before marking Accepted.
- **Rollback:** ADR is versioned; supersede-not-edit. No runtime impact.

**WP-P0.2 — Determinism-seam recording rules (INV-17) for persisted values**
- **Purpose:** Specify how non-deterministic values are recorded-not-recomputed across the durable boundary.
- **Scope:** Section within ADR-007 or a companion note enumerating value classes (timestamps, IDs, model outputs) and their record points.
- **Inputs:** INV-17, `event` + `observation` contracts.
- **Outputs:** Ratified recording-rules table.
- **Dependencies:** `⊣` WP-P0.1.
- **Acceptance Criteria:** Every non-deterministic value class has a named record point; replay determinism is asserted as a testable property for P1.
- **Tests Required:** Replay-determinism test *specified* for P1.
- **Risks:** Missed value class → non-deterministic replay. Mitigate: cross-check against all 18 contracts' non-deterministic fields.
- **Rollback:** Document-only.

#### Epic P0.E2 — Flag/Shadow Mechanism Decision (C2)
**WP-P0.3 — Complete ADR-008 (feature-flag + shadow-mode mechanism)**
- **Purpose:** Close H3 (no flag/shadow infra) so Strangler cutover is possible and INV-39 (cross-subsystem interaction is a correlated event) holds across the seam.
- **Scope:** ADR defining flag store, evaluation point, shadow-execution comparison protocol, and correlation-event schema. Names required contract additions (does not freeze them).
- **Inputs:** Blueprint Integration Strategy (shadow→canary→default), INV-39, `event` contract.
- **Outputs:** `ADR-008-flag-shadow-mechanism.md` (Accepted).
- **Dependencies:** none. `⟶` P3.
- **Acceptance Criteria:** ADR specifies flag lifecycle, shadow diff semantics ("equivalent" defined measurably), and the correlation-event shape; no unresolved section.
- **Tests Required:** Shadow-equivalence harness *specified* for P3.
- **Risks:** Under-specified "equivalence" → false cutover confidence. Mitigate: require a concrete diff metric.
- **Rollback:** Document-only.

#### Epic P0.E3 — Estimation Model & Contract Freeze (C3)
**WP-P0.4 — Estimation model spec + freeze `engineering_strategy`/`estimation` contract**
- **Purpose:** Close H4 (Estimation void) and give P8 a frozen target.
- **Scope:** Model spec (inputs, output ranges, calibration approach) + contract freeze proposal for the estimation/engineering_strategy contract.
- **Inputs:** Intelligence Model table (Estimation reasons via INV-17 seam), existing 18 contracts as freeze template.
- **Outputs:** Estimation model doc + frozen contract file in `contracts/`.
- **Dependencies:** none. `⟶` P8.
- **Acceptance Criteria:** Contract added to `contracts/` following the existing 18-contract format; model spec has measurable calibration criterion.
- **Tests Required:** Contract-shape guardrail test *specified*.
- **Risks:** Over-specifying a model before data exists. Mitigate: spec the *seam*, defer coefficients to P8.
- **Rollback:** Contract versioned; unfreeze requires new ADR.

#### Epic P0.E4 — Operations Design (C4)
**WP-P0.5 — Operations plane design doc**
- **Purpose:** Close H5 (Operations undesigned); give P9 a blueprint.
- **Scope:** Design doc: metrics taxonomy, briefing generation, liveness, mapped onto v1 `metrics.py`/`briefing.py`.
- **Inputs:** Blueprint void→v1 mapping, Constitution Operate capability.
- **Outputs:** `docs/v2/engineering/operations-design.md`.
- **Dependencies:** none. `⟶` P9.
- **Acceptance Criteria:** Every Operate responsibility from the Constitution maps to a named component and a v1 source to converge from.
- **Tests Required:** none (design).
- **Risks:** Scope creep into observability platform. Mitigate: constrain to constitutional Operate responsibilities only.
- **Rollback:** Document-only.

#### Epic P0.E5 — Contract Freezes (C5) & Sequencing (C6)
**WP-P0.6 — Freeze `repository_understanding`, `interaction`, `environment` contracts**
- **Purpose:** Close H-cluster on grounding/interaction; unblock P4/P5/P6.
- **Scope:** Author + freeze the three remaining subsystem contracts.
- **Inputs:** Readiness "Contract Readiness: 5 subsystems need new frozen contracts," existing contracts.
- **Outputs:** three new files in `contracts/`.
- **Dependencies:** `∥` WP-P0.4. `⟶` P4/P5/P6.
- **Acceptance Criteria:** three contracts added in existing format; each cites its owning capability and invariants.
- **Tests Required:** contract-shape guardrail *specified*.
- **Risks:** Premature freeze. Mitigate: each freeze cites a prototype (`repo_profile`, `human_approval`) as evidence of shape.
- **Rollback:** versioned; unfreeze via ADR.

**WP-P0.7 — Ratify ADR roadmap ordering (Policy + ADR-007/008 to front)**
- **Purpose:** Encode C6 sequencing decision as the authoritative build order.
- **Scope:** One ADR fixing program order P0→P1→P2→P3 as front-loaded.
- **Inputs:** Readiness sequencing change; this document.
- **Outputs:** `ADR-006-program-sequencing.md`.
- **Dependencies:** `⊣` WP-P0.1, WP-P0.3.
- **Acceptance Criteria:** Order ratified; deviations require superseding ADR.
- **Tests Required:** none.
- **Risks:** Ordering ossifies before spikes. Mitigate: allow parallel bands explicitly.
- **Rollback:** supersede.

> **P0 Definition of Done:** ADR-006/007/008 Accepted; Estimation + Operations designs published; `repository_understanding`/`interaction`/`environment`/`estimation` contracts frozen. **No open "Unresolved" section anywhere.** Zero code changes.

---

### P1 — Durable Foundation  `★`

*Turns the void (Durable Memory) into a concrete event-sourced durable store obeying ADR-007. Converges v1's async persistence rather than reinventing it.*

#### Epic P1.E1 — Durable Event Store
**WP-P1.1 — Durable `EventStore` behind the frozen sync interface (spike-first)**
- **Purpose:** Provide append/read_stream/read_all backed by durable storage without changing `interfaces.py` shape.
- **Scope:** One concrete durable `EventStore` impl in `nexus_infra`, honoring ADR-007's sync↔async crossing. Includes the executable spike that validated ADR-007.
- **Inputs:** `interfaces.py` `EventStore`, ADR-007, v1 `audit_log` schema as reference.
- **Outputs:** durable event store module + spike report appended to WP-P0.1.
- **Dependencies:** `⊣` WP-P0.1/P0.2. `⟶` all persistence-consuming spine capabilities.
- **Acceptance Criteria:** append-then-read round-trips across process restart; `read_all` reconstructs identical ordering; passes the INV-17 replay-determinism test from P0.2; **the existing `InMemoryEventStore` test suite passes unchanged against the durable impl** (interface parity).
- **Tests Required:** unit (append/read), integration (restart survival), replay-determinism, interface-parity (same tests, both impls), architecture guardrail (no `nexus.` import).
- **Risks:** async bleed into sync spine (INV-01/13). Mitigate: crossing isolated to `nexus_infra`; guardrail test forbids `async def` leaking into `nexus_core`.
- **Rollback:** feature-flagged (P3) — default remains `InMemoryEventStore`; flip off restores prior behavior with zero data model change.

**WP-P1.2 — Durable projections + snapshot/rebuild**
- **Purpose:** State-as-projection (INV-14) with rebuild-from-events.
- **Scope:** Durable Projection + Snapshot impls; rebuild command.
- **Inputs:** `interfaces.py` Projection/Snapshot, WP-P1.1.
- **Outputs:** projection/snapshot modules.
- **Dependencies:** `⊣` WP-P1.1.
- **Acceptance Criteria:** dropping all projections and replaying events reproduces byte-identical projected state; snapshot+tail replay equals full replay.
- **Tests Required:** replay-equivalence, snapshot-equivalence, corruption-recovery (INV-22: recover, never restart from Goal).
- **Risks:** projection/event divergence. Mitigate: rebuild is the only write path to projections.
- **Rollback:** flag to in-memory projection.

#### Epic P1.E2 — Durable Repositories & UnitOfWork
**WP-P1.3 — Durable `Repository[T]` + `UnitOfWork` (converge v1 memory)**
- **Purpose:** Durable get/add/list_all + commit/rollback matching the sync interface, converging v1 `nexus/memory/{manager,models,service}.py`.
- **Scope:** Durable repos for the already-defined registries (Goal/Plan/Artifact/Policy/Knowledge), transactional UoW.
- **Inputs:** `nexus_infra/repositories.py` (in-memory), v1 memory ORM, ADR-007.
- **Outputs:** durable repository + UoW modules.
- **Dependencies:** `⊣` WP-P1.1. `∥` WP-P1.2.
- **Acceptance Criteria:** all in-memory repository tests pass against durable impls unchanged; commit is atomic (partial-failure leaves no writes); INV-07 (one schema per object) verified by a schema-uniqueness check.
- **Tests Required:** interface-parity, atomicity/rollback, INV-07 schema guardrail, restart-survival.
- **Risks:** CRUD-authority regression violating INV-13. Mitigate: repos are projections over events per ADR-007, never independent write authority.
- **Rollback:** flag to in-memory repos.

> **P1 DoD:** Durable event store + projections + repos pass **every existing in-memory test unchanged** (parity) plus restart-survival and replay-determinism. `async def` count in `nexus_core` remains 0 (guardrail). Repository still boots on in-memory default (flag-gated). **Quality gate:** replay determinism proven. **Migration gate:** v1 memory identified as convergence source, not yet retired.

---

### P2 — Policy Engine  `★`

*Promotes Policy to sole evaluator (INV-28/29/30). Converges v1 `policy_service.py` (async CRUD) into a synchronous, event-sourced `nexus_policy` evaluation engine — the piece v2 provably lacks.*

#### Epic P2.E1 — Evaluation Engine
**WP-P2.1 — `nexus_policy` evaluation engine (fail-closed)**
- **Purpose:** Give v2 an executable policy evaluator (currently only v1 has one; v2 `PolicyResolver` explicitly never evaluates).
- **Scope:** New `nexus_policy` package: consumes frozen `policy` contract + `nexus_core/domain/policy.py`; evaluates against a decision request; fail-closed default.
- **Inputs:** `contracts/policy.md`, `20_POLICY_ENGINE.md`, v1 `policy_service.py` + `core/policy_defaults.py`, INV-28/29/30.
- **Outputs:** `nexus_policy/engine.py` + registry binding.
- **Dependencies:** `⊣` P1 (durable policy repo), `⊣` P0 (sequencing). `⟶` every governed action in P5/P6/P7/P8/P10.
- **Acceptance Criteria:** engine is the **only** component that returns allow/deny (INV-28 verified by guardrail: no other package emits a policy verdict); unknown/error input → deny (INV-30 fail-closed) proven by test; Governance authorizes but never executes (INV-29 verified — engine returns a decision object, performs no side effect).
- **Tests Required:** unit (allow/deny matrix), fail-closed (malformed/timeout/missing-policy all deny), INV-28 sole-evaluator guardrail (grep for competing verdict emitters), INV-29 no-side-effect test, regression vs. v1 policy defaults (same inputs → same verdicts).
- **Risks:** Divergence from v1 verdicts during convergence → governance regression. Mitigate: shadow v1 vs. v2 verdicts (P3) before cutover.
- **Rollback:** flag routes evaluation to v1 `policy_service`; v2 engine runs shadow-only until parity proven.

**WP-P2.2 — Policy provenance events (INV-39)**
- **Purpose:** Every evaluation is a correlated event.
- **Scope:** Emit decision events to the durable store with correlation IDs.
- **Inputs:** `event` contract, WP-P1.1, INV-39.
- **Outputs:** policy decision event type + emitter.
- **Dependencies:** `⊣` WP-P2.1, WP-P1.1.
- **Acceptance Criteria:** every evaluate() call produces exactly one durable, correlated decision event; replay reconstructs full authorization history.
- **Tests Required:** one-event-per-decision, correlation-integrity, replay-history.
- **Risks:** double-emit / missing-emit. Mitigate: emit inside the same UoW as the decision.
- **Rollback:** flag.

> **P2 DoD:** `nexus_policy` is the sole verdict source (guardrail-proven); fail-closed proven; verdict parity with v1 defaults proven; all decisions are correlated durable events. **Architecture gate:** INV-28/29/30 guardrails green.

---

### P3 — Strangler Integration Substrate  `★`

*Builds the flag/shadow/gateway machinery ADR-008 requires. Without this, no migration stage past Blueprint Stage 1 can ship. Delivers the first live seam.*

#### Epic P3.E1 — Feature Flags
**WP-P3.1 — Feature-flag store + evaluation point**
- **Purpose:** Flag-before-default (Blueprint invariant); currently zero flag infra exists.
- **Scope:** Durable flag store + single evaluation seam consumed by P1/P2 rollback flags.
- **Inputs:** ADR-008, WP-P1.1.
- **Outputs:** `nexus_infra` flag module.
- **Dependencies:** `⊣` WP-P0.3, WP-P1.1.
- **Acceptance Criteria:** flags are durable, default-off, and read at one seam (guardrail: no scattered flag reads); flipping a flag changes routing with no redeploy.
- **Tests Required:** default-off, persistence, single-seam guardrail, routing-flip integration.
- **Risks:** flag sprawl. Mitigate: single evaluation point enforced by guardrail.
- **Rollback:** remove flag → default path.

#### Epic P3.E2 — Shadow Mode & Correlation Gateway
**WP-P3.2 — Shadow-execution + equivalence harness**
- **Purpose:** Shadow-before-act; measurable equivalence per ADR-008.
- **Scope:** Run v2 path in shadow alongside v1 (starting with P2 policy verdicts), capture diffs against ADR-008's metric.
- **Inputs:** ADR-008 equivalence metric, WP-P2.1, WP-P3.1.
- **Outputs:** shadow runner + diff report.
- **Dependencies:** `⊣` WP-P3.1, WP-P2.1.
- **Acceptance Criteria:** shadow runs produce a quantified equivalence score; cutover blocked until score ≥ ADR-008 threshold for policy verdicts.
- **Tests Required:** diff-detection (injected divergence caught), equivalence-scoring, no-side-effect-in-shadow.
- **Risks:** shadow path causes side effects. Mitigate: shadow uses no-op actuation; guardrail test.
- **Rollback:** disable shadow flag.

**WP-P3.3 — Cross-boundary correlation event gateway (INV-39)**
- **Purpose:** Replace single-process `InProcessEventBus` limit with a correlated cross-subsystem gateway (currently absent).
- **Scope:** Gateway that carries correlated events across package boundaries within the process; forward-compatible with out-of-process later.
- **Inputs:** INV-39, `event` contract, `InProcessEventBus`.
- **Outputs:** new `nexus_gateway` package.
- **Dependencies:** `⊣` WP-P1.1. `∥` WP-P3.2.
- **Acceptance Criteria:** any cross-subsystem interaction emits exactly one correlated event (INV-39 guardrail); existing in-process tests pass through the gateway unchanged.
- **Tests Required:** correlation-completeness, ordering, in-process parity, INV-39 guardrail.
- **Risks:** gateway becomes a god-object (violates INV-02). Mitigate: transport only, no logic; guardrail.
- **Rollback:** route back to `InProcessEventBus`.

> **P3 DoD:** flags durable+default-off; policy verdicts run in shadow with a green equivalence score; correlation gateway carries all cross-subsystem events. **First live seam shipped.** **Operational gate:** shadow diff dashboard exists.

---

### P4 — Repository Intelligence  *(off min-path)*

*Grounding plane. Promotes `nexus_workflows/repo_profile.py` + `repo_intelligence.py` prototypes into `nexus_repository` against the frozen `repository_understanding` contract.*

#### Epic P4.E1 — Repository Profiling
**WP-P4.1 — `nexus_repository` profiler (promote prototype)**
- **Purpose:** Produce a repository_understanding artifact grounding downstream reasoning.
- **Scope:** Package the `repo_profile` prototype behind the frozen contract; event-sourced output.
- **Inputs:** `repo_profile.py`, `test_a2_repo_profile.py`, frozen `repository_understanding` contract (WP-P0.6).
- **Outputs:** `nexus_repository` package.
- **Dependencies:** `⊣` WP-P0.6, `⊣` P1. `∥` P5/P6.
- **Acceptance Criteria:** output validates against the frozen contract; existing `test_a2_repo_profile` assertions pass against the packaged form; profiling emits correlated events.
- **Tests Required:** contract-conformance, prototype-parity (a2 tests), event-correlation, replay.
- **Risks:** prototype assumptions leak past contract. Mitigate: contract-conformance gate.
- **Rollback:** flag; profiler disabled → grounding falls back to none (downstream degrades, not breaks).

> **P4 DoD:** repository_understanding produced, contract-valid, event-sourced, `test_a2` parity green.

---

### P5 — Human Interaction  *(off min-path)*

*Void → converges v1 `approvals/service.py` + `communication/discord/`. INV-23: Supervision recommends; Orchestration owns pause/resume/cancel.*

#### Epic P5.E1 — Approval Channel
**WP-P5.1 — `nexus_human_interaction` approval seam (promote `human_approval` prototype)**
- **Purpose:** Governed human-in-the-loop approvals as events, not direct control.
- **Scope:** Package `human_approval.py` behind frozen `interaction` contract; approvals are requests that Orchestration acts on (INV-23).
- **Inputs:** `human_approval.py`, `test_a1_governed_approval.py`, v1 approvals + discord, frozen `interaction` contract.
- **Outputs:** `nexus_human_interaction` package.
- **Dependencies:** `⊣` WP-P0.6, `⊣` P1, `⊣` P2 (approvals gated by policy).
- **Acceptance Criteria:** an approval never executes an action itself (INV-23 guardrail: package emits requests/decisions only); `test_a1_governed_approval` parity green; approval events correlated.
- **Tests Required:** INV-23 no-execution guardrail, a1 parity, policy-gated-approval integration, event-correlation.
- **Risks:** approval path bypasses policy. Mitigate: approval requires a P2 verdict first (integration test).
- **Rollback:** flag; falls back to v1 Discord approvals.

> **P5 DoD:** approvals are policy-gated correlated events; INV-23 guardrail green; a1 parity green.

---

### P6 — Actuation  *(off min-path)*

*Act capability. Converges v1 `execution/sandbox/` + `git_actions.py` prototype. Harness boundary INV-34/35/36/37.*

#### Epic P6.E1 — Governed Actuation
**WP-P6.1 — `nexus_actuation` sandboxed action seam (promote `git_actions`)**
- **Purpose:** Execute real actions only through the harness boundary, policy-gated.
- **Scope:** Package `git_actions.py` + v1 sandbox behind one registry (INV-35); Orchestration selects runtime (INV-36).
- **Inputs:** `git_actions.py`, v1 sandbox, runtime adapters (`nexus_runtime_claude/_gemini/_shell`), INV-34/35/36/37.
- **Outputs:** `nexus_actuation` package.
- **Dependencies:** `⊣` P2, `⊣` P1. `∥` P4/P5.
- **Acceptance Criteria:** no action executes without a prior policy verdict (guardrail + integration); one registry only (INV-35 guardrail); runtime selection owned by Orchestration (INV-36 test); every action emits a correlated event.
- **Tests Required:** policy-gate integration, INV-35 single-registry guardrail, INV-36 selection test, sandbox-isolation, event-correlation, replay.
- **Risks:** ungoverned side effect. Mitigate: actuation entrypoint hard-requires a verdict token; fail-closed.
- **Rollback:** flag; actuation → no-op/shadow.

> **P6 DoD:** all actions policy-gated + sandboxed + correlated; harness-boundary invariants green.

---

### P7 — Intent Resolution  `★`

*Understand capability — half of "Nexus thinks." Reasons via the INV-17 seam. Promotes `a0`/`a1` prototypes into `nexus_intent`.*

#### Epic P7.E1 — Understand
**WP-P7.1 — `nexus_intent` resolver (promote a0 vertical)**
- **Purpose:** Turn a raw request into a frozen `intent` artifact — the entry of the reasoning spine.
- **Scope:** Package `a0.py` behind `intent` contract; record model outputs at the INV-17 seam.
- **Inputs:** `a0.py`, `scripts/a0_run.py`, `test_a0_vertical.py`, frozen `intent` contract, INV-17.
- **Outputs:** `nexus_intent` package.
- **Dependencies:** `⊣` P1, `⊣` P2, `⊣` P3 (flagged rollout). `⟶` P8.
- **Acceptance Criteria:** produces contract-valid `intent`; non-deterministic model output recorded-not-recomputed (INV-17 replay test: same events → same intent); `test_a0_vertical` parity green.
- **Tests Required:** contract-conformance, INV-17 replay-determinism, a0 parity, event-correlation.
- **Risks:** recompute-on-replay breaks determinism. Mitigate: seam records outputs (P0.2 rules).
- **Rollback:** flag; intent resolution → shadow.

> **P7 DoD:** contract-valid intent, INV-17 replay-deterministic, a0 parity green. **Half of "Nexus thinks" online.**

---

### P8 — Engineering Intelligence + Estimation  `★`

*Reason capability + Estimation — the other half of "Nexus thinks." Reasons via INV-17. Reflection→Knowledge→future Planning only (INV-25/26).*

#### Epic P8.E1 — Engineering Intelligence (Reason)
**WP-P8.1 — `nexus_engineering` reasoner core**
- **Purpose:** Reason over intent + grounding to produce engineering strategy feeding Plan.
- **Scope:** New `nexus_engineering`; consumes `intent` (P7) + `repository_understanding` (P4, optional-degradable); emits `engineering_strategy`.
- **Inputs:** frozen `engineering_strategy`/`estimation` contracts (P0.4), INV-17/25/26.
- **Outputs:** `nexus_engineering` package.
- **Dependencies:** `⊣` P7, `⊣` P0.4. `∥` P8.E2.
- **Acceptance Criteria:** output contract-valid; reasoning outputs recorded at INV-17 seam (replay-deterministic); no direct Reflection→Planning shortcut (INV-25/26 guardrail: Reason reads Knowledge, never raw Reflection).
- **Tests Required:** contract-conformance, INV-17 replay, INV-25/26 guardrail, integration with P7 intent.
- **Risks:** reasoner couples to repository grounding as hard dep. Mitigate: grounding is optional input; degrade gracefully (tested).
- **Rollback:** flag; reason → shadow.

#### Epic P8.E2 — Estimation
**WP-P8.2 — `nexus_estimation` engine (calibrate P0.4 model)**
- **Purpose:** Estimate cost/effort/risk to score plans; the reason plane's quantitative arm.
- **Scope:** Implement the P0.4 model spec; emit `estimation` artifacts consumed by Plan-scoring.
- **Inputs:** Estimation model doc (P0.4), frozen `estimation` contract.
- **Outputs:** `nexus_estimation` package.
- **Dependencies:** `⊣` P0.4, `∥` WP-P8.1.
- **Acceptance Criteria:** output contract-valid; calibration criterion from P0.4 met on a reference set; estimates recorded at INV-17 seam.
- **Tests Required:** contract-conformance, calibration-threshold, INV-17 replay.
- **Risks:** uncalibrated estimates mislead planning. Mitigate: calibration gate blocks default-on.
- **Rollback:** flag; estimation → advisory-only.

> **P8 DoD:** Reason + Estimation produce contract-valid, replay-deterministic outputs; INV-25/26 guardrail green; calibration threshold met. **"Nexus thinks" is now true end-of-reasoning-spine.**

---

### P9 — Operations  *(off min-path)*

*Operate plane. Converges v1 `metrics.py` + `briefing.py` + `scheduling/`. Design from P0.5.*

#### Epic P9.E1 — Metrics & Briefing
**WP-P9.1 — `nexus_operations` metrics + briefing (converge v1)**
- **Purpose:** Operational visibility over the event-sourced spine.
- **Scope:** Package v1 metrics/briefing behind the Operate design; project metrics from durable events.
- **Inputs:** P0.5 design, v1 `metrics.py`/`briefing.py`, WP-P1.1.
- **Outputs:** `nexus_operations` package.
- **Dependencies:** `⊣` P0.5, `⊣` P1. `∥` P8.
- **Acceptance Criteria:** metrics derived only from events (INV-13, no independent counters — guardrail); briefing reproducible from event replay.
- **Tests Required:** metrics-from-events guardrail, briefing-replay-reproducibility, correlation.
- **Risks:** metrics become a second source of truth. Mitigate: projection-only; guardrail.
- **Rollback:** flag; briefing → v1.

**WP-P9.2 — Scheduler integration (converge v1 `scheduling/` + gateway)**
- **Purpose:** Time-driven work through the correlation gateway, not a side channel.
- **Scope:** Wire v1 scheduler to emit correlated events via `nexus_gateway`.
- **Inputs:** v1 `scheduling/`, `gateway/` (outbox), WP-P3.3.
- **Outputs:** scheduler adapter in `nexus_operations`.
- **Dependencies:** `⊣` WP-P3.3.
- **Acceptance Criteria:** scheduled triggers are correlated events (INV-39); no scheduler-direct execution bypassing policy.
- **Tests Required:** correlation, policy-gate, replay.
- **Risks:** scheduler bypass of governance. Mitigate: triggers enter the spine like any event.
- **Rollback:** flag; v1 scheduler standalone.

> **P9 DoD:** metrics/briefing projection-only + replay-reproducible; scheduler triggers are governed correlated events.

---

### P10 — Spine Convergence & Cutover  `★`

*Assembles the spine end-to-end, runs the first governed constitutional workflow, then executes Blueprint Stages 2–8 to default-cutover and retire duplicates. Runtime adapters already exist — this is selection + cutover, not construction.*

#### Epic P10.E1 — End-to-End Spine
**WP-P10.1 — First governed constitutional workflow (Understand→…→Act, shadow)**
- **Purpose:** Prove "Runtime executes. Nexus thinks." on one real workflow, in shadow.
- **Scope:** Wire P7→P8→existing Plan/Coordinate/Execute/Validate→P6 Act, policy-gated (P2), correlated (P3), durable (P1); runtime via existing adapters (Orchestration selects, INV-36).
- **Inputs:** all prior programs, `nexus_runtime_*` adapters.
- **Outputs:** one flagged, shadow end-to-end path.
- **Dependencies:** `⊣` P1,P2,P3,P6,P7,P8 (P4/P5/P9 enhance, not block).
- **Acceptance Criteria:** the workflow runs entirely on v2 in shadow; every step is a correlated durable event; full replay reproduces the run; policy gates every action; **shadow-equivalence vs. v1 meets ADR-008 threshold.**
- **Tests Required:** end-to-end replay-determinism, per-step correlation completeness, policy-gate coverage, shadow-equivalence, INV guardrail suite (full).
- **Risks:** integration reveals a contract gap. Mitigate: each upstream program already contract-conformance-tested; gap → new ADR, not a patch.
- **Rollback:** flag; shadow-only, zero user impact.

#### Epic P10.E2 — Cutover & Duplicate Retirement
**WP-P10.2 — Canary → default cutover (Blueprint Stages 2–7)**
- **Purpose:** Promote shadow to default per stage, keeping the repo releasable each stage.
- **Scope:** Per-decision flag flips (policy, then intent, then act…) gated by equivalence scores.
- **Inputs:** WP-P10.1, P3 equivalence harness.
- **Outputs:** default-on v2 seams, stage by stage.
- **Dependencies:** `⊣` WP-P10.1.
- **Acceptance Criteria:** each stage ships with green equivalence + full test suite; **repository releasable after every stage** (release-tag + smoke test per stage).
- **Tests Required:** per-stage regression, operational-validation (canary metrics), rollback drill.
- **Risks:** cutover regression. Mitigate: flag-flip rollback proven by drill before each stage.
- **Rollback:** flip flag back; prior stage is the safe state.

**WP-P10.3 — Converge-then-delete v1 duplicates (Blueprint Stage 8)**
- **Purpose:** Remove v1 implementations only after v2 owns the decision by default.
- **Scope:** Delete converged v1 modules (memory, policy_service, approvals, sandbox, metrics/briefing, scheduler) once their v2 seam is default-on and stable.
- **Inputs:** cutover state, Blueprint Tech Debt Removal.
- **Outputs:** reduced v1 surface; single entrypoint wired to v2.
- **Dependencies:** `⊣` WP-P10.2 (a module is deletable only after its seam is default-on for a full release).
- **Acceptance Criteria:** no `nexus.` import remains for a deleted module (guardrail); entrypoint launches v2 spine; deletion PR is revert-clean.
- **Tests Required:** import-guardrail, full regression, entrypoint smoke, revert drill.
- **Risks:** premature deletion of still-referenced code. Mitigate: delete only what has been default-on ≥1 release; grep-proven zero references.
- **Rollback:** revert deletion PR (kept atomic and standalone).

> **P10 DoD:** one governed constitutional workflow runs default-on, replay-deterministic, policy-gated; v1 duplicates for cutover seams retired; single entrypoint launches the v2 spine. **First principle satisfied: "Runtime executes. Nexus thinks about execution."**

---

## 5. Dependency Graph

```
P0 (gate) ─────────────────────────────────────────────────────────────
  ├─ WP-P0.1 ★ ⟶ P1(all)
  ├─ WP-P0.3 ★ ⟶ P3
  ├─ WP-P0.4   ⟶ P8.E2
  ├─ WP-P0.5   ⟶ P9
  └─ WP-P0.6   ⟶ P4,P5,P6

P1 ★ ⊣P0.1 ──────────────┐
  P1.1 ⟶ P1.2,P1.3,       │
        P2,P3,P4,P5,P6,   │
        P7,P8,P9          │
P2 ★ ⊣P1,P0 ⟶ P5,P6,P7,P8,P10
P3 ★ ⊣P0.3,P1 ⟶ P4,P5,P6,P7(rollout),P9.2,P10
      (P3.2 ⊣P2 · P3.3 ∥P3.2)

Parallel band A (⊣P0.6,P1[,P2]):   P4 ∥ P5 ∥ P6      (off min-path)
Min-path reasoning:                 P7 ★ ⊣P1,P2,P3 ⟶ P8
                                    P8 ★ ⊣P7,P0.4  (E1∥E2)
Parallel band B (⊣P0.5,P1):         P9 ∥ P8          (off min-path)

P10 ★ ⊣P1,P2,P3,P6,P7,P8
   P10.1 ⟶ P10.2 ⟶ P10.3
```

**Must-be-first:** P0 (all downstream), then P1.1 (all persistence consumers).
**Parallelizable:** {P4, P5, P6} after P0.6+P1(+P2); {P8, P9} after their gates; P3.3 ∥ P3.2.
**Blocked-by chokepoints:** WP-P0.1 (blocks P1→everything), WP-P1.1 (blocks all persistence), WP-P2.1 (blocks all governed action), WP-P3.1/3.2 (block cutover).
**Unlocks:** WP-P1.1 unlocks the most (9 programs); WP-P2.1 unlocks all governed capabilities.

---

## 6. Critical Path to "Runtime executes. Nexus thinks."

**Minimal chain (each `★`):**

```
WP-P0.1 (persistence authority ADR)
  → WP-P1.1 (durable event store) → WP-P1.3 (durable repos)
    → WP-P2.1 (policy engine) → WP-P2.2 (policy events)
      → WP-P3.1 (flags) → WP-P3.2 (shadow) → WP-P3.3 (gateway)
        → WP-P7.1 (intent / Understand)
          → WP-P8.1 (reason) ∥ WP-P8.2 (estimation)
            → WP-P10.1 (governed end-to-end, shadow)
              → WP-P10.2 (cutover to default)
```

**Already built, on-path but not new work** (verified present & tested): Plan (`nexus_planning`), Coordinate/Orchestrate (`nexus_orchestration`), Execute (`nexus_execution`), Validate (`nexus_validation`), Recover (`nexus_recovery`), Runtime adapters (`nexus_runtime_*`). These are *consumed* by WP-P10.1, not rebuilt.

**Explicitly OFF the minimal path** (required for governed autonomous production, not for the first "thinks" milestone):
- **P4 Repository Intelligence** — enriches grounding; P8 degrades gracefully without it.
- **P5 Human Interaction** — required before *unsupervised* autonomy, not before thinking.
- **P6 Actuation** — needed for *Act* on real side effects; the first end-to-end can run Act in shadow/no-op, so P6 is on the *production* path but the thinking milestone can be proven with shadow actuation. (P6 is on the min path for *governed real action*; off it for *proving cognition*.)
- **P9 Operations** — visibility, not cognition.

---

## 7. ADR Requirements (identify only — do not write)

| ADR / Contract | Program | Type | Status target |
|---|---|---|---|
| ADR-006 Program Sequencing | P0 | Decision | Accepted in P0 |
| ADR-007 Persistence Authority (sync/async + event-log truth) | P0 | Decision (rewrite) | Accepted in P0 |
| ADR-008 Flag/Shadow Mechanism | P0 | Decision (complete) | Accepted in P0 |
| ADR-009 Policy Convergence (v1→`nexus_policy`) | P2 | Migration | Required before P2 cutover |
| ADR-010 Correlation Gateway / INV-39 transport | P3 | Protocol freeze | Required before P3.3 |
| ADR-011 Actuation Harness Boundary (INV-34–37) | P6 | Decision | Required before P6 |
| ADR-012 Cutover & Duplicate Retirement Policy | P10 | Migration | Required before P10.2 |
| **Contract freezes** | | | |
| `estimation` / `engineering_strategy` | P0.4 | Contract freeze | Frozen in P0 |
| `repository_understanding` | P0.6 | Contract freeze | Frozen in P0 |
| `interaction` | P0.6 | Contract freeze | Frozen in P0 |
| `environment` | P0.6 | Contract freeze | Frozen in P0 |
| **Protocol freezes** | | | |
| Correlation-event schema (INV-39) | P3 | Protocol | Frozen with ADR-010 |
| Shadow-equivalence metric | P3 | Protocol | Frozen with ADR-008 |

*Every item above is identified as work; none is authored in this document.*

---

## 8. Testing Strategy (per epic type)

| Test class | Applies to | Definition |
|---|---|---|
| **Unit** | every WP | behavior of the module in isolation |
| **Interface-parity** | P1, P2 | the *same* existing in-memory/v1 test suite passes against the new durable/converged impl unchanged |
| **Replay-determinism (INV-17)** | P1, P2, P4, P6, P7, P8, P9, P10 | same events → identical projected state/output; non-deterministic values recorded not recomputed |
| **Integration** | P2, P5, P6, P7, P8, P10 | cross-capability wiring through the gateway |
| **Shadow-equivalence** | P3, P10 | v2 vs. v1 output diff ≤ ADR-008 threshold before cutover |
| **Architecture guardrails** | every program | executable INV checks: INV-01 one-way deps, INV-02 one responsibility, INV-07 one schema, INV-13/14 event-truth (no independent write authority / no non-event counters), INV-23 recommend-not-execute, INV-25/26 Reflection→Knowledge only, INV-28/29/30 policy sole/authorize/fail-closed, INV-35 one registry, INV-36 orchestration selects, INV-39 correlated events; plus `async def`-in-`nexus_core` = 0 and `nexus.`-import guards |
| **Regression** | P2, P10 | converged component reproduces prior verdicts/behavior |
| **Operational-validation** | P3, P9, P10 | canary metrics, shadow dashboards, rollback drills |

**Guardrails run in CI on every PR** and are the non-negotiable gate; a red guardrail blocks merge regardless of feature status.

---

## 9. Success Gates (objective; no subjective completion)

Each program passes **five gates** before it counts as done:

1. **Definition of Done** — the program's DoD line above, all bullets green.
2. **Quality Gate** — all Tests Required green; coverage of new modules ≥ existing package baseline; zero skipped tests.
3. **Architecture Gate** — all applicable INV guardrails green in CI; no new `async def` in `nexus_core`; no new cross-stratum import.
4. **Operational Gate** — feature flag exists and defaults off; rollback drill executed and recorded; where applicable, shadow dashboard live.
5. **Migration Gate** — convergence source (v1 module) identified; parity/equivalence proven before any default-on; deletion deferred to P10.

**Performance Gate (P1, P10):** durable event append + projection rebuild within a stated budget on the reference workload; regression fails the gate. (Budget set in ADR-007; measured, not asserted.)

---

## 10. Risk Register (per program, top risks)

| ID | Program | Risk | Severity | Mitigation | Owner gate |
|---|---|---|---|---|---|
| R1 | P0/P1 | Wrong persistence-authority call violates INV-13/14 irreversibly | **Critical** | Spike-first (WP-P1.1) before ADR-007 Accepted; guardrail forbids independent write authority | Arch |
| R2 | P1 | async/v1 bleed into sync spine (INV-01) | High | crossing isolated to `nexus_infra`; `async def`-in-core guardrail | Arch |
| R3 | P2 | v2 verdicts diverge from v1 → governance regression | High | shadow-equivalence before cutover; regression vs. policy_defaults | Migration |
| R4 | P3 | under-specified "equivalence" → false cutover confidence | High | ADR-008 quantified metric + injected-divergence test | Ops |
| R5 | P3 | correlation gateway accretes logic (INV-02) | Medium | transport-only guardrail | Arch |
| R6 | P4/P8 | reasoner hard-couples to grounding | Medium | grounding optional; graceful-degradation test | Quality |
| R7 | P5/P6 | approval/actuation bypasses policy | High | verdict-token required at entrypoint; fail-closed | Arch |
| R8 | P7/P8 | recompute-on-replay breaks determinism | High | INV-17 recording rules (P0.2) + replay test | Quality |
| R9 | P10 | premature v1 deletion of referenced code | High | default-on ≥1 release + grep-zero-refs before delete; atomic revert PR | Migration |
| R10 | all | flag sprawl / scattered reads | Medium | single flag-evaluation seam guardrail | Arch |
| R11 | P8 | uncalibrated estimation misleads planning | Medium | calibration threshold blocks default-on | Quality |
| R12 | P0 | contracts frozen prematurely | Medium | each freeze cites a passing prototype as shape evidence | Arch |

---

## 11. Version Roadmap

| Version | Programs | Capability unlocked | Migration progress | Risk removed |
|---|---|---|---|---|
| **v2.2 — Governed & Durable** | P0, P1, P2 | Spine persists across restart; policy is the sole, fail-closed, event-sourced evaluator | Blueprint Stage 0–1; durable foundation converged from v1 memory; policy convergence identified | R1, R2, R3 (parity proven) |
| **v2.3 — Grounded & Integrated** | P3, P4, P5 | Feature flags + shadow + correlation gateway live; repository grounding; policy-gated human approvals | Blueprint Stage 1–2; first live seams shipped, shadow equivalence measured | R4, R5, R7 (approval path) |
| **v2.4 — Understands & Acts** | P6, P7, P8-core | Governed sandboxed actuation; Intent Resolution (Understand); Reason core online | Blueprint Stage 2–4; Act/Understand seams in shadow→canary | R7 (actuation), R8 (intent replay) |
| **v2.5 — Reasons End-to-End** | P8-complete, P9 | Estimation calibrated; Operations visibility; **first governed constitutional workflow runs (shadow), "Nexus thinks" proven** | Blueprint Stage 4–6; end-to-end shadow equivalence green | R6, R8 (reason replay), R11 |
| **v3.0 — Cutover & Retirement** | P10 | Constitutional workflow default-on; single entrypoint launches v2 spine; v1 duplicates retired | Blueprint Stage 7–8 complete; **convergence done, duplicates deleted** | R9; strata-divergence risk eliminated |

**Releasability invariant:** every version above ships with the full test suite + guardrails green and every new seam flag-gated and default-safe. No milestone leaves the repository unreleasable.

---

## 12. Final Recommendation

**Build order is non-negotiable at the head: P0 before any code, then P1.1 before any persistence consumer, then P2 before any governed action.** These three chokepoints gate 9, 9, and 6 downstream programs respectively; getting P0/P1 wrong is the only irreversible mistake in the entire program (INV-13/14), which is why WP-P1.1 is a *spike-first* validation of ADR-007, not an implementation task.

**Why this unlocks future capability:**
- **P0** converts every "hidden decision" into a ratified constraint, so downstream teams build against law, not guesswork — eliminating the rework that an unresolved sync/async or CRUD/event-log question would otherwise seed into nine packages.
- **P1** makes cognition *survive* — every reasoning capability is worthless without durable, replay-deterministic memory; it also proves convergence-from-v1 works, de-risking all later convergence.
- **P2** makes autonomy *safe* — nothing governed can ship until a single fail-closed evaluator exists, and building it early lets every later capability (P5/P6/P7/P8) inherit governance for free.
- **P3** makes migration *possible and reversible* — flags + shadow + correlation are what let every subsequent seam ship default-safe and roll back on a flag, which is what keeps the repo releasable after every milestone.
- **P7+P8** are the payoff — Understand + Reason + Estimation are the literal content of "Nexus thinks," and they are cheap to build *because* P1–P3 already made the substrate durable, governed, and integrated, and because Plan/Coordinate/Execute/Validate already exist and pass tests.
- **P10** is convergence's terminal step: only *after* v2 owns each decision by default do we delete v1 — turning "two strata" from a standing risk into a single governed spine.

**Off-path but mandatory-for-production** (P4/P5/P6/P9) run in parallel bands so the critical path is never idle and the first "thinks" milestone is not held hostage to grounding, approvals, or operations breadth.

**Recommended immediate action:** execute P0 in full — no code — and gate its close on the WP-P1.1 spike report proving ADR-007 is buildable. Everything else follows from a correct persistence-authority decision.

*Optimize for a repository that remains releasable after every milestone. Every seam ships behind a flag, proven in shadow, reversible on a flip, and deleted only after it is redundant.*
