# Nexus v2 — Testing Strategy

Status: Engineering Plan
Scope: The **test types** Nexus v2 uses and the **per-subsystem coverage** that
evolves with implementation. This document defines *what to test and how*.

Companion: `10_VALIDATION_STRATEGY.md` defines the per-phase **gates** that
consume these tests as acceptance evidence. This document supplies the test
types; it does not redefine the gate process.

---

## 1. The Nexus Test Pyramid

The pyramid is **contract-centred**: contract tests at every seam are the
backbone, because the platform's value is that 13 stages and the substrate
share one object language (`00_IMPLEMENTATION_OVERVIEW.md`). If objects drift,
the pipeline cannot integrate. Test types, from base to apex:

1. **Unit.** Pure logic of a single component: schema invariants, state-guard
   logic, graph algorithms, classification rules. Fast, no I/O. Largest count.
2. **Contract (backbone).** Producer-output-validates-against-consumer-input at
   **every seam**, via the contract-test harness (**AP-006**) and shared schema
   fixtures. A producer or consumer drifting from a schema fails with a clear
   diff. This is the dominant test category in Nexus.
3. **Integration.** Two or more real subsystems wired through a seam, no stubs:
   e.g. State engine + idempotency, Orchestration + Governance, Execution +
   Supervision.
4. **System / Scenario.** End-to-end pipeline runs over representative goals:
   Goal → Context → Plan → Graph → Execution → Validation → Knowledge (subset
   per phase). These are the end-of-phase scenarios.
5. **Failure-injection.** Forced faults: poison events, duplicate delivery,
   runtime crash, missing artifact, insufficient evidence, policy violation.
   Proves the platform *degrades correctly* (pause-not-crash, reject-not-pass).
6. **Recovery.** Restore-from-checkpoint-and-resume, retry bounding, no-evidence-
   loss — the recover-not-restart invariant.
7. **Governance / Policy.** Deterministic policy evaluation, conflict-resolution
   truth tables, deny/approval paths, immutable-audit assertions, validated-only
   ingestion gates.
8. **Determinism / Replay.** Same input → same output for policy and intent
   boundaries; replay a recorded event stream → identical downstream state;
   replayable orchestration decisions.
9. **Performance / Load.** Throughput, latency on hot paths (policy eval, event
   bus), soak/backpressure, recoverability under load.
10. **Observability / Audit-coverage.** Every layer emits traces/metrics; every
    decision is auditable; audit is immutable and complete (no gaps).

---

## 2. Shared Conventions

- **One harness for all seams.** Every Contract row below is realized through
  **AP-006** with shared fixtures (§6). New seams register here, never ad hoc.
- **Architecture-fitness is continuous.** The dependency-direction test (AP-005)
  runs every build, not per-subsystem (see `10`, §3).
- **Negative tests are first-class.** "Refuses / rejects / does-not-complete /
  denies" cases carry equal weight to happy paths; several invariants are only
  provable by a negative test (invalid context refusal, insufficient-evidence
  non-completion, illegal-transition rejection, overwrite rejection).
- **Tie to AP Suggested Tests.** Each row's failure/recovery and invariant
  columns trace to the owning AP's *Suggested Tests* in `02_ACTION_POINTS.md`.

---

## 3. Per-Subsystem Coverage — Pipeline Stages

For each subsystem: **what to unit-test · key contract seam(s) · critical
failure/recovery test · invariant it must prove.** AP IDs cited.

| Subsystem | Unit-test | Key contract seam(s) | Critical failure/recovery test | Invariant proven |
|-----------|-----------|----------------------|--------------------------------|------------------|
| **Intent Resolution** (AP-301) | Paraphrase→one canonical Goal; ambiguity scoring; no plan/runtime leakage | Intent → Context Engineering | Low-confidence input ⇒ clarification request, not assumed Goal | Goals are outcomes, not procedures; bounded determinism at LLM boundary (AP-004) |
| **Context Engineering** (AP-303) | Validation dimensions (completeness/consistency/freshness/auth); known-unknowns | Context Engineering → Planning | Incomplete sources ⇒ refuses to certify; marks validation status | Exactly one validated Context Package per Goal; no certification of incomplete context |
| **Context Harnesses** (AP-302) | Connector contract conformance; freshness | Connector → Context Engineering (atop AP-207) | Auth-denied source surfaces as a harness failure, not silent gap | Read access is authorized; failures surface as harness failures |
| **Planning** (AP-306) | Decomposition into WPs; acyclic dependency analysis; rationale presence | Planning → Execution Graph builder | **Invalid Context Package ⇒ hard refusal** (no plan produced) | Planning refuses invalid Context; every decision explainable |
| **Execution Strategy** (AP-308) | Runtime-agnosticism; policy completeness/precedence | Strategy → Orchestration + Recovery | Missing required policy field ⇒ strategy rejected | Declarative, runtime-agnostic coordination; approval vocab matches Governance |
| **Capability Resolution** (AP-304) | Capability→provider matching; field-ownership conformance | Resolution → Strategy/Orchestration | Unavailable provider path returns candidates honestly, selects nothing | Resolution produces candidates; selection/allocation is Orchestration's |
| **Skill Selection** (AP-305) | Selection ignores runtime; composition resolution; version conflict rule | Skill registry → Work Packaging | Composition version conflict ⇒ defined-rule resolution, not crash | Skills describe capability, not runtime |
| **Work Packaging** (AP-309) | WP self-containment; reference validity | Work Package → Orchestration/Execution (binds AP-105) | Raw-operator-request leak attempt ⇒ rejected | **No raw operator request reaches a Work Package** |
| **Orchestration** (AP-401) | Dependency/constraint ordering; gate logic | Graph/Strategy → Orchestration; Orchestration → Runtime | Forced runtime failure ⇒ pause (not crash); decisions replayable from log | No execution before gates pass; replayable decisions; **single owner of control** |
| **Execution** (AP-405) | Emits evidence *candidates*; exposes (not decides) failure | Execution → Supervision + Validation (AP-110) | Runtime "success" ⇒ candidates only, **never self-completes** | Completion-by-evidence: execution never self-validates |
| **Runtime / Harness** (AP-403/404) | Adapter conformance; cancel + failure paths | Runtime Interface ↔ Orchestration (atop AP-207) | Same WP run unmodified across ≥2 adapters incl. Human Operator | **Capability-first runtime independence** |
| **Supervision** (AP-501) | Health derivation (indicators→thresholds); observation aggregation | Events → Supervision; Supervision → Orchestration (recommendations) | Stall/degrade detected from evidence; recommendation routed to Orchestration only | **Supervision recommends; Orchestration acts** — never controls directly |
| **Validation** (AP-502) | Four-valued result; evidence collection; validator dispatch | Evidence candidates → Validation → Knowledge gate | **Insufficient evidence ⇒ not Passed**; runtime self-report ignored | Completion by evidence, never runtime confidence |
| **Recovery** (AP-503) | Failure classification; deterministic strategy selection; retry counter | Failure/checkpoint → Recovery → Orchestration | Restore from latest valid checkpoint + resume; retries bounded; validated evidence retained | **Recover-from-checkpoint-not-restart**; bounded retries; never bypass Governance/override Validation |
| **Reflection** (AP-601) | Reject unvalidated input; confidence laddering | Validated outcomes → Reflection → Knowledge ingestion | Unvalidated execution as input ⇒ rejected | Reflections evidence-sourced; outputs are advisory candidates, not direct writes |
| **Knowledge** (AP-602/603) | Freshness/supersession lifecycle; reference (not copy) | Reflection → Knowledge; Knowledge → Context/Planning | Deprecated/stale knowledge excluded from retrieval; second-run reuse measured | **Only validated outcomes enter Knowledge**; reuse demonstrable |

---

## 4. Per-Subsystem Coverage — Substrate

| Substrate | Unit-test | Key contract seam(s) | Critical failure/recovery test | Invariant proven |
|-----------|-----------|----------------------|--------------------------------|------------------|
| **Event** (AP-201/202) | Causal ordering per correlation id; DLQ routing | Event payload schema (AP-112) ↔ every producer/consumer | **Duplicate delivery ⇒ no duplicate state change**; replay → identical state | At-least-once + consumer idempotency; replayable streams |
| **State** (AP-203) | Transition guards; "Active"/"Executing" naming | State schema ↔ State engine; idempotency (AP-202) | Illegal-transition matrix all rejected | **Exactly one event per transition**; illegal transitions rejected |
| **Checkpoint** (AP-204) | Reference-not-copy; parent linkage; pre-restore validation | Checkpoint schema ↔ Recovery (AP-503) | Missing-artifact / policy-incompatibility ⇒ restore rejected pre-restore | Recover-from-checkpoint by reference; no silent broken restore |
| **Policy** (AP-205) | Condition language; specificity computation | Policy schema ↔ Governance/Validation/Recovery/Planning | Conflict-resolution truth table; simulation never mutates production | **Deterministic** policy evaluation; side-effect-free simulation |
| **Artifact** (AP-206/111) | Immutability; lineage walk; reference resolution | Artifact schema ↔ Validation + Knowledge | **Overwrite rejected**; version chain preserved | Immutable artifacts; new-version-never-overwrite; referenced not copied |
| **Harness** (AP-207) | Common-contract lifecycle; capability discovery | Harness contract ↔ Runtime/Context/Validation/Comm harnesses | Mock harness register→advertise→health→event→discover-by-capability | Single integration boundary; capability-based discovery |
| **Governance** (AP-406) | Authorization decision set; approval workflow | Governance gate ↔ Orchestration boundary | **Policy-violating action denied + immutably audited**; approval blocks until approved | Authority over autonomy; immutable audit |

---

## 5. Cross-Cutting Test Suites

These run across many subsystems and are not owned by one row above:

- **Replay/Determinism suite.** Records a canonical event stream (AP-201) and a
  set of policy/intent inputs; asserts replay → identical downstream state and
  same-input→same-output at deterministic boundaries (AP-205, AP-401). Bounds
  the documented non-deterministic boundaries (LLM intent, human approval) per
  AP-004 rather than asserting determinism there.
- **Idempotency property suite.** Duplicate-delivers every event type to a
  reference consumer and asserts no duplicate state change (AP-202).
- **Failure-injection suite.** Catalogued faults: poison event, duplicate
  delivery, runtime crash mid-WP, missing artifact at restore, insufficient
  evidence at validation, policy violation at the gate. Each asserts the correct
  degraded behaviour (pause-not-crash / reject-not-pass / deny-and-audit).
- **Recovery suite.** End-to-end fail→detect→classify→restore→retry(bounded)→
  recover-or-escalate, asserting no context/evidence loss (AP-501/502/503,
  AP-204).
- **Governance/audit suite.** Deny path, approval-blocks-until-approved, audit
  immutability and completeness, validated-only Knowledge ingestion
  (AP-406, AP-602).
- **Observability/audit-coverage suite.** Asserts every layer emits traces and
  metrics and every decision is auditable; fails on a coverage gap (AP-604).
- **Performance/load suite.** Hot-path latency (policy eval, event bus),
  soak/backpressure, recoverability under load against stated targets (AP-604).

---

## 6. Test Data & Fixtures

Shared, versioned fixtures are the substrate of the contract backbone. They live
beside the object-contract package (Phase 1) and are versioned with the schemas.

- **Shared schema fixtures.** One canonical valid instance (and curated invalid
  instances for negative tests) per object family — Goal, Context Package, Plan,
  Work Package, Execution Graph, Execution Strategy, Skill, Capability, Resource,
  Harness, Execution Session, Observation, Evidence/Candidate, Artifact, Event,
  Policy, Checkpoint, Validation Report, Knowledge Entry. Every Contract test in
  §3/§4 draws from these. Invalid fixtures include the planted drift used to
  prove the harness fails with a clear diff (AP-006) and the procedural-field
  Goal used to prove AP-102's negative case.
- **Golden Execution Graphs.** A small library of expected acyclic Execution
  Graphs for the representative multi-domain goal set, used by the Phase 3
  scenario and as stable inputs to Phase 4 Orchestration tests (so execution
  tests do not depend on Planning's internals). Each golden graph carries
  required capabilities, skills, constraints, validation requirements, and
  completion criteria on its nodes.
- **Recorded event streams (for replay).** Canonical streams captured from
  substrate and orchestration runs, replayed to assert identical downstream
  state (AP-201) and replayable orchestration decisions (AP-401). These are the
  inputs to the Replay/Determinism suite.
- **Recorded failure traces.** Fixtures for each catalogued fault (poison event,
  runtime crash, missing artifact, insufficient evidence, policy violation),
  reused by the Failure-injection and Recovery suites.
- **Policy fixtures.** Policy sets with known conflicts for the conflict-
  resolution truth table and determinism cases (AP-205, AP-004).

Fixture governance: a schema change requires updating its fixtures in the same
change; the contract harness fails until fixtures match the schema, which keeps
fixtures honest.

---

## 7. Invariant → Test-Type Map

This is the proof side of the gate→invariant table in `10_VALIDATION_STRATEGY.md`
§7. Each architectural invariant is proven by the listed test type(s).

| Invariant | Primary test type | Suite / AP |
|-----------|-------------------|------------|
| One-way dependency flow (no lower imports higher) | Architecture-fitness (continuous) | AP-005 |
| Every seam contract holds (no schema drift) | Contract | AP-006, all Phase 1 APs |
| Goals are outcomes, not procedures | Unit (negative) + Contract | AP-102 |
| One canonical Work Package schema | Contract (multi-seam) | AP-105 |
| Completion by evidence; no runtime self-report | System/Scenario + Integration | AP-405, AP-502 |
| Insufficient evidence ⇒ not complete | Failure-injection | AP-502 |
| Exactly one event per state transition | Unit + Determinism | AP-203 |
| Illegal transitions rejected | Unit (transition matrix) | AP-203 |
| Idempotency under duplicate delivery | Failure-injection (property) | AP-202 |
| Replayable event stream / orchestration decisions | Determinism/Replay | AP-201, AP-401 |
| Recover-from-checkpoint-not-restart; no evidence loss | Recovery | AP-204, AP-503 |
| Bounded retries | Failure-injection | AP-503 |
| Deterministic policy; side-effect-free simulation | Determinism + Governance | AP-205 |
| Immutable audit; deny policy-violating action | Governance/Policy | AP-406 |
| Immutable artifacts (overwrite rejected) | Unit/Integration | AP-111, AP-206 |
| Planning refuses invalid Context Package | System/Scenario (refusal) | AP-303, AP-306 |
| No raw operator request reaches a Work Package | Integration | AP-309 |
| Execution Graph acyclic | Unit (cycle detection) | AP-104, AP-307 |
| Supervision recommends / Orchestration acts (one owner per verb) | Architecture review + Scenario | AP-501, AP-401 |
| Capability-first runtime independence | System/Scenario | AP-403, AP-404 |
| Only validated outcomes enter Knowledge | Governance + Scenario | AP-601, AP-602 |
| Knowledge reuse demonstrable; deprecated excluded | System/Scenario (reuse) | AP-603 |
| Full-layer observability + audit; targets under load | Observability + Performance | AP-604 |

---

## 8. Testing by Phase (when each test type comes online)

Test types accumulate; a type, once online, keeps running in later phases. This
maps to the gate evidence each phase's gate requires (`10`, §5).

| Phase | Test types coming online | Anchored by |
|-------|--------------------------|-------------|
| **0** | Architecture-fitness (continuous); Contract-harness self-test; CI smoke; decision-rehearsal spike | AP-005, AP-006, AP-001 |
| **1** | Unit (schema invariants, state-transition, cycle detection); Contract (every documented seam); round-trip serialization; negative schema tests | AP-101–112 |
| **2** | Integration (substrate components); Determinism/Replay; Idempotency (property); Recovery (checkpoint restore); Governance/Policy (determinism, simulation isolation); immutability tests | AP-201–207 |
| **3** | System/Scenario (Goal → persisted Execution Graph); refusal/negative scenarios (invalid context, no-raw-request); explainability/rationale checks | AP-301–309 |
| **4** | System/Scenario (multi-node graph to "waiting validation"); Failure-injection (runtime crash ⇒ pause); Replay (orchestration decisions); Governance (deny + audit); runtime-independence (same WP, ≥2 adapters) | AP-401–406 |
| **5** | Failure-injection (insufficient evidence, classified failure); Recovery (restore→retry→recover/escalate, no evidence loss); evidence-completion scenarios; recommend-not-control checks | AP-501–503 |
| **6** | System/Scenario (knowledge-reuse across two runs); validated-only ingestion; Observability/audit-coverage; Performance/Load (soak, backpressure, recoverability under load) | AP-601–604 |

---

## 9. Cross-Reference

- **Phase gates that consume these tests as acceptance evidence:**
  `10_VALIDATION_STRATEGY.md` (§5 per-phase activities; §7 gate→invariant map).
- **AP-level Suggested Tests & Validation Strategy:** `02_ACTION_POINTS.md`.
- **Phase definitions & the gate sequence:** `01_PHASES.md`.
- **Contract-test harness (the backbone):** AP-006 (`02_ACTION_POINTS.md`);
  dependency-fitness test: AP-005.
