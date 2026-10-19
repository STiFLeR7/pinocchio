# Nexus v2 — Validation Strategy

Status: Engineering Plan
Scope: The per-**phase validation gates** that authorize moving from one phase to
the next. This document defines the *process and acceptance* of each gate.

Companion: `11_TESTING_STRATEGY.md` defines the *test types* each gate consumes.
This document references those types; it does not redefine them.

---

## 1. What a Gate Is

A phase is a unit of architectural progress (`01_PHASES.md`). A phase is complete
only when its **validation gate** passes. The gate is a fixed sequence of
activities that produce concrete acceptance evidence and an explicit sign-off.

Every phase ends with the same gate sequence (`01_PHASES.md`):

```
Contracts Complete → Architecture Review → Integration Review →
Smoke / Scenario Tests → Documentation Review → Gate Pass → Next Phase
```

A gate authorizes the *next* phase. It is not a release sign-off; phases are
not release versions. The gate proves that the architectural invariants the
phase is responsible for are now enforced in running software and contracts,
not merely described.

---

## 2. Gate Activities (definitions used by every phase)

The five activities below recur in every phase gate. Each phase section states
what each activity inspects *for that phase*.

- **Contracts Complete.** Every object/seam contract the phase produces is
  defined, versioned, and has a passing contract test (`11`, §Contract). No
  consumer in the phase binds to an undefined or drifted schema.
- **Architecture Review.** Manual review against the architectural invariants
  (`§7` invariant table). Confirms responsibility boundaries, dependency
  direction, and ownership decisions for the phase's subsystems.
- **Integration Review.** Confirms every seam the phase introduces has a real
  producer and a real consumer wired through the contract-test harness
  (**AP-006**) — no stubbed seam ships as "done."
- **Smoke / Scenario Tests.** The phase's end-of-phase scenario(s) run green
  (`11`, §System/Scenario). For substrate phases this is the substrate
  smoke run; for pipeline phases it is an end-to-end pipeline scenario.
- **Documentation Review.** The phase's specs, ADRs, and the architecture index
  are current and consistent with what shipped; the glossary (**AP-007**) covers
  every new term.

---

## 3. Architecture-Fitness Checks That Run Every Phase

Two automated checks run in CI on every phase from Phase 0 onward and are a
hard precondition of every gate. They are not phase-specific; a regression in
either blocks the gate regardless of phase.

- **Dependency-direction test (AP-005).** An architecture-fitness test asserts
  the one-way dependency flow: no lower layer imports a higher layer. A
  deliberately-wrong import must fail the build. This proves the
  *one-way-dependency-flow* invariant continuously.
- **Contract-test harness (AP-006).** The seam harness loads producer output and
  asserts it validates against the consumer's expected input schema, from shared
  fixtures. From Phase 1 on, every seam introduced by a phase must be registered
  in this harness. An intentional schema drift must fail with a clear diff.

Both checks are themselves validated at the Phase 0 gate (the harness self-tests
on a fixture pair; the fitness test fails on a planted wrong-way import).

---

## 4. Gate Policy (non-negotiable)

- **A gate cannot be skipped.** Implementation never begins a later phase before
  the prior phase's gate has passed (`01_PHASES.md`). Phase-0 ADRs that gate
  everything (ADR-001…004) must be *ratified*, not merely proposed, before any
  Phase 1 schema work starts.
- **A failed gate is remediated before later work.** A phase that fails its gate
  is fixed in place; no later-phase AP may be started against the failed phase's
  outputs. Remediation re-runs the full gate sequence, not only the failed
  activity.
- **Evidence is concrete.** "Gate Pass" requires the named acceptance
  artifacts (test reports, ADR records, scenario run logs, audit excerpts) to
  exist and be linked from the gate record — not a verbal assurance.
- **Architecture-fitness is a standing precondition.** Both §3 checks must be
  green at the moment of every gate, in every phase.
- **Sign-off is explicit.** Each gate names the role(s) that sign. A gate with
  an unsatisfied invariant in its §7 row cannot be signed.

---

## 5. Per-Phase Gates

Each gate below states: **Entry criteria → Validation activities → Acceptance
evidence → Exit criteria → Sign-off.** AP IDs are cited verbatim.

### Phase 0 — Foundation & Architectural Decisions

- **Entry criteria.** None (first phase). Source architecture structurally
  complete; the empty/duplicate specs are the work, not a blocker.
- **Validation activities.**
  - *Contracts Complete.* The "persistence contract" (one page, AP-001) and the
    canonical registration/capability field-ownership table (AP-002) exist.
  - *Architecture Review.* Confirms no empty/duplicate specs remain
    (Supervision, Harness, Reflection authored); every cross-cutting persistence
    decision is an **accepted** ADR (ADR-001 via AP-001; ADR-002 via AP-002;
    ADR-003 via AP-003; ADR-004 via AP-004). Each contested object has exactly
    one owning layer (AP-003); each registry field has exactly one owner
    (AP-002).
  - *Integration Review.* The contract-test harness (AP-006) can load a schema
    fixture and assert against it; the dependency-fitness test (AP-005) is wired.
  - *Smoke / Scenario Tests.* CI runs green on an empty skeleton (AP-005); the
    harness self-test passes and a planted wrong-way import fails the build.
  - *Documentation Review.* Glossary authored and architecture index repaired
    (AP-007); doc-13 naming resolution recorded.
- **Acceptance evidence.** Ratified ADR-001…004 records; AP-001 worked recovery
  example (one WP traced through failure→recovery, naming the authoritative
  store); AP-002 field-ownership table; AP-003 object→owning-layer traceability
  matrix; green CI log on empty skeleton; failing-build log for the planted
  wrong-way import; harness fixture self-test report; `GLOSSARY.md` + corrected
  index.
- **Exit criteria.** All four foundational ADRs accepted; both §3 fitness checks
  operational; no empty/duplicate spec; glossary and index correct.
- **Sign-off.** Principal Architect (ADRs + reconciliation); Engineering Lead
  (CI/scaffold/harness).

### Phase 1 — Core Object Model & Contracts

- **Entry criteria.** Phase 0 gate passed. ADR-001 (serialization/persistence),
  ADR-002 (registry ownership), ADR-003 (object reconciliation), ADR-004
  (approval vocabulary) ratified.
- **Validation activities.**
  - *Contracts Complete.* Exactly one authoritative schema per object family
    (AP-101…112); one serialization/identity/versioning convention (AP-101).
  - *Architecture Review.* Goal carries no procedure (AP-102); Work Package is a
    single unified schema (AP-105); Capability carries no provider/health, which
    live on Resource/Harness (AP-108/109); Observation is descriptive-only,
    Execution emits *candidates*, Validation produces Evidence (AP-110); single
    Artifact status vocabulary, immutable-by-default (AP-111); enum drift
    resolved (AP-112).
  - *Integration Review.* Every documented seam is registered in the AP-006
    harness with real schema fixtures (Context→Planning, Planning→Orchestration,
    Execution→Validation, etc.).
  - *Smoke / Scenario Tests.* Round-trip serialize/deserialize for a sample of
    each object family (AP-101); Execution-Graph acyclicity validator (AP-104);
    Work Package state-transition tests (AP-105).
  - *Documentation Review.* Each schema cites the ADR it derives from
    (AP-101→001, AP-105→003, AP-106/112→004, AP-108/109→002).
- **Acceptance evidence.** Versioned object-contract package; schema registry;
  per-object round-trip test reports; a passing contract test for every
  documented seam built from real fixtures; a drift test that fails when a
  producer or consumer diverges.
- **Exit criteria.** One schema per object with a round-trip test; every
  documented seam has a passing contract test from real fixtures (`01_PHASES.md`
  Phase 1 gate).
- **Sign-off.** Principal Architect (schema authority/ownership); Test Architect
  (contract coverage of seams).

### Phase 2 — Infrastructure Substrate

- **Entry criteria.** Phase 1 gate passed (Event, Policy, Checkpoint, Artifact,
  State schemas exist and pass contract tests).
- **Validation activities.**
  - *Contracts Complete.* Substrate services expose contracts consistent with
    Phase 1 schemas (AP-201…207); each honors the AP-001 persistence contract.
  - *Architecture Review.* State engine emits exactly one event per transition
    and rejects illegal transitions (AP-203); checkpoints reference, not copy
    (AP-204); policy evaluation is deterministic with defined conflict resolution
    (AP-205); artifacts immutable-by-default (AP-206); Harness SDK is the single
    integration boundary (AP-207).
  - *Integration Review.* Idempotency framework (AP-202) is used uniformly by
    State and (later) Orchestration; a reference harness registers, advertises
    capabilities, reports health, and emits events (AP-207).
  - *Smoke / Scenario Tests.* The Phase 2 substrate scenario: drive a synthetic
    object through its full state machine emitting one replayable event per
    transition (AP-203); write+restore a checkpoint with reference validation
    (AP-204); register/version/evaluate/simulate a policy deterministically
    (AP-205); produce/version/reference an artifact without duplication (AP-206);
    prove idempotency under duplicate event delivery (AP-202).
  - *Documentation Review.* Persistence contract realized as built; replay and
    idempotency conventions documented.
- **Acceptance evidence.** Running event bus + store with a replay-determinism
  report (AP-201); illegal-transition matrix and transition→event invariant
  report (AP-203); restore-after-failure + missing-artifact-rejection report
  (AP-204); determinism + conflict-resolution truth table + simulation-isolation
  report (AP-205); immutability/lineage report (AP-206); mock-harness
  registration/discovery/health/event report (AP-207); duplicate-delivery
  property-test report (AP-202).
- **Exit criteria.** All substrate invariants proven by test per the Phase 2
  gate (`01_PHASES.md`): one-replayable-event-per-transition, reference-based
  checkpoint restore, deterministic policy, immutable referenced artifacts,
  idempotency under duplicate delivery.
- **Sign-off.** Principal Architect (substrate/persistence); Test Architect
  (determinism, replay, idempotency, recovery substrate).

### Phase 3 — Understanding Pipeline (Intent → Context → Plan → Strategy)

- **Entry criteria.** Phases 1–2 gates passed. Object schemas and substrate
  available; no runtime required.
- **Validation activities.**
  - *Contracts Complete.* Intent→Context→Planning→Graph→Strategy→Work-Packaging
    seams (AP-301…309) bound to Phase 1 schemas via the harness.
  - *Architecture Review.* Goal carries no plan/runtime leakage (AP-301);
    Context Engineering refuses to certify incomplete context (AP-303); Planning
    refuses an invalid Context Package and persists rationale (AP-306);
    Capability *resolution* produces candidates while selection/allocation is
    deferred to Orchestration (AP-304); Skill selection ignores runtime
    (AP-305); no raw operator request reaches a Work Package (AP-309).
  - *Integration Review.* Context Harnesses (AP-302) extend the AP-207 SDK with
    ≥2 read-only sources behind one contract; the full Goal→…→Work-Package chain
    is wired through real components, not stubs.
  - *Smoke / Scenario Tests.* End-of-phase scenario (AP-309): a representative,
    multi-domain goal set produces a valid acyclic Execution Graph whose nodes
    reference well-formed Work Packages with required capabilities, skills,
    constraints, validation requirements, and completion criteria; Planning hard-
    refuses an invalid Context Package; every decision is explainable.
  - *Documentation Review.* Rationale-persistence and "minimal complete context"
    sufficiency heuristic documented.
- **Acceptance evidence.** Persisted Execution Graph(s) for the goal set;
  paraphrase-normalization report (AP-301); invalid-context refusal report
  (AP-303/306); acyclicity + node→WP-reference report (AP-104/307);
  self-containment + "no raw request in WP" report (AP-309); persisted decision
  rationales.
- **Exit criteria.** Pipeline produces a valid acyclic Execution Graph of
  well-formed Work Packages across domains; Planning refuses invalid context;
  every decision explainable; no runtime invoked (`01_PHASES.md` Phase 3 gate).
- **Sign-off.** Principal Architect (pipeline boundaries); Test Architect
  (scenario coverage + refusal paths).

### Phase 4 — Execution Coordination

- **Entry criteria.** Phases 2–3 gates passed. Execution Graph + Execution
  Strategy available; substrate live.
- **Validation activities.**
  - *Contracts Complete.* Orchestration↔Runtime/Harness↔Execution↔Governance
    seams (AP-401…406) bound to schemas; Runtime expressed as a Harness category
    (AP-403, per AP-002).
  - *Architecture Review.* No execution before dependency/constraint/approval/
    resource gates pass (AP-401/402/406); Orchestration is the **single owner of
    control** (pause/resume/cancel) and the sole resource allocator
    (AP-401/402); Execution **never self-validates**, emits evidence *candidates*
    and exposes (not decides) failure (AP-405); Governance denies policy-
    violating actions with immutable audit (AP-406).
  - *Integration Review.* The same Work Package runs unmodified across ≥2 runtime
    adapters incl. a Human Operator harness (AP-403/404) — capability-first
    runtime independence.
  - *Smoke / Scenario Tests.* End-of-phase scenario (AP-401/406): a multi-node
    Execution Graph runs to "waiting validation" across ≥2 adapters; a forced
    runtime failure pauses (does not crash) the operation; every orchestration
    decision is replayable from the event log; the governance gate denies a
    policy-violating action and records an immutable audit entry.
  - *Documentation Review.* Runtime-determinism caveat for LLM runtimes recorded
    as "attempt" (AP-403); approval-timeout gap flagged to Recovery (AP-406).
- **Acceptance evidence.** Multi-node run logs to "waiting validation";
  gate-enforcement report (no execution pre-gate); replay report reconstructing
  orchestration decisions; same-WP-multi-runtime report (AP-404);
  no-self-completion + failure-exposure report (AP-405); governance deny-path +
  audit-immutability report (AP-406).
- **Exit criteria.** Multi-node graph executes through ≥2 runtimes under
  governance with replayable decisions, no self-declared completion, and a
  pause-not-crash on runtime failure (`01_PHASES.md` Phase 4 gate).
- **Sign-off.** Principal Architect (control ownership + runtime independence);
  Test Architect (gate-enforcement, replay, governance audit); Security/
  Governance reviewer (audit immutability, deny path).

### Phase 5 — Supervision, Validation & Recovery

- **Entry criteria.** Phases 2–4 gates passed. Execution emits events,
  observations, evidence candidates, checkpoints.
- **Validation activities.**
  - *Contracts Complete.* Supervision/Validation/Recovery consume Execution and
    substrate outputs via schemas (AP-501…503).
  - *Architecture Review.* Supervision **recommends**, never controls — routes
    intervention recommendations to Orchestration only (AP-501); Validation
    determines completion **by evidence**, never runtime self-report, and
    insufficient evidence ⇒ not complete (AP-502); Recovery resumes from the
    latest valid checkpoint (not restart), bounds retries, never discards
    validated evidence, never bypasses Governance or overrides Validation
    (AP-503). The pause/resume/escalate verbs each have **exactly one owner**.
  - *Integration Review.* Supervision→Recovery→Orchestration loop wired end to
    end; Validation gates entry to Knowledge.
  - *Smoke / Scenario Tests.* End-of-phase failure scenario (AP-501/502/503): a
    failing Work Package is detected by Supervision, classified by Recovery,
    restored from checkpoint, retried within bounds, and either recovered or
    escalated — without losing context or validated evidence; Validation
    independently passes/fails/partials from evidence alone; a runtime "success"
    with insufficient evidence does **not** complete.
  - *Documentation Review.* Health-indicator→threshold definitions (AP-501);
    pre-declared-recovery-edge vs runtime-selected-strategy reconciliation
    (AP-503); non-rollbackable side-effect handling recorded.
- **Acceptance evidence.** Stall/degraded-detection report + recommend-not-
  control invariant report (AP-501); evidence-insufficiency⇒not-passed +
  validator-dispatch report (AP-502); restore-and-resume + retry-bound +
  no-evidence-loss report (AP-503); a verb-ownership table showing one owner per
  pause/resume/escalate.
- **Exit criteria.** Failure detected→classified→restored→retried→recovered/
  escalated with no context or evidence loss; evidence-only completion; single
  owner per control verb (`01_PHASES.md` Phase 5 gate).
- **Sign-off.** Principal Architect (recommend/act separation + recover-not-
  restart); Test Architect (failure-injection, recovery, evidence-completion).

### Phase 6 — Knowledge, Reflection & Operational Maturity

- **Entry criteria.** Phases 1–5 gates passed. Validated outcomes and complete
  operational history available.
- **Validation activities.**
  - *Contracts Complete.* Reflection→Knowledge→Retrieval seams (AP-601…603) and
    observability/audit interfaces (AP-604) bound to schemas.
  - *Architecture Review.* Reflection analyzes **only validated evidence** and
    emits advisory candidates — never writes Knowledge directly, and Planning
    never depends on Reflection directly (AP-601); only validated candidates
    persist, with freshness/supersession enforced and artifacts referenced not
    copied (AP-602); deprecated knowledge excluded from retrieval (AP-603).
  - *Integration Review.* The learning loop is closed: Knowledge retrieval feeds
    Context Engineering and Planning (AP-603); audit/observability spans every
    layer (AP-604).
  - *Smoke / Scenario Tests.* End-to-end learning scenario (AP-603): a second run
    of a previously executed goal class demonstrably reuses validated knowledge
    in planning/context; only validated outcomes enter Knowledge; reflections are
    evidence-sourced; end-to-end observability and audit cover every layer; the
    platform meets stated performance and recoverability targets under load.
  - *Documentation Review.* Runbooks, performance envelope, and capacity
    documented (AP-604).
- **Acceptance evidence.** Knowledge-reuse measurement across two runs of a goal
  class (AP-603); validation-gate + supersession + stale-exclusion report
  (AP-602); reject-unvalidated-input + candidate-not-write report (AP-601);
  trace-coverage + audit-completeness + load/soak report (AP-604).
- **Exit criteria.** Validated-only knowledge ingestion; demonstrable knowledge
  reuse in a second run; full-layer observability/audit; performance and
  recoverability targets met under load (`01_PHASES.md` Phase 6 gate).
- **Sign-off.** Principal Architect (learning-loop integrity); Test Architect
  (reuse measurement, load/soak); Operations reviewer (runbooks, performance,
  audit completeness).

---

## 6. Gate Record (what "Gate Pass" produces)

Each passed gate produces a durable record containing: the phase ID; links to
every acceptance-evidence artifact above; the green state of both §3 fitness
checks; the invariant-table rows (§7) marked proven; and the named sign-offs.
A later phase's entry criteria are satisfied only by a complete prior gate
record.

---

## 7. Phase Gate → Invariant Map

Each gate is responsible for *proving* a set of architectural invariants. The
test type that proves each is defined in `11_TESTING_STRATEGY.md`; the AP that
owns it is cited. An invariant is "proven" at a gate when its test is green and
its architecture-review row is signed.

| Phase | Invariant proven at this gate | Owning AP(s) | Proof type (see 11) |
|-------|-------------------------------|--------------|---------------------|
| 0 | One-way dependency flow (no lower layer imports higher) | AP-005 | Architecture-fitness |
| 0 | Contract-harness can prove/deny seam compatibility | AP-006 | Contract (self-test) |
| 0 | Single authoritative persistence/source-of-truth model | AP-001 | Architecture review + spike |
| 0 | One owner per registry field; one owning layer per object | AP-002, AP-003 | Architecture review |
| 1 | Goals describe outcomes, not procedures | AP-102 | Unit (negative) + Contract |
| 1 | One canonical Work Package schema (no drift) | AP-105 | Contract (multi-seam) |
| 1 | Capability carries no provider/health (lives on Resource/Harness) | AP-108, AP-109 | Contract (field-ownership) |
| 1 | Execution emits candidates; Validation produces Evidence | AP-110 | Contract |
| 1 | Immutable artifacts (new-version-never-overwrite) | AP-111 | Unit/Contract |
| 1 | Every documented seam contract holds | AP-101–112 | Contract |
| 2 | Exactly one event per state transition | AP-203 | Unit + Determinism |
| 2 | Illegal state transitions rejected | AP-203 | Unit (transition matrix) |
| 2 | Idempotency under duplicate event delivery | AP-202 | Failure-injection (property) |
| 2 | Replayable event stream → identical downstream state | AP-201 | Determinism/Replay |
| 2 | Recover-from-checkpoint by reference, not copy/restart | AP-204 | Recovery |
| 2 | Deterministic policy evaluation; simulation side-effect-free | AP-205 | Determinism + Governance |
| 2 | Immutable, referenced (not duplicated) artifacts | AP-206 | Unit/Integration |
| 3 | Planning refuses an invalid Context Package | AP-303, AP-306 | System/Scenario (refusal) |
| 3 | No raw operator request reaches a Work Package | AP-309 | Integration |
| 3 | Execution Graph is acyclic (explicit loops only) | AP-104, AP-307 | Unit (cycle detection) |
| 3 | Every planning decision explainable (rationale persisted) | AP-306 | Scenario/Audit |
| 4 | Completion-by-evidence: no execution self-completion | AP-405 | Integration + Contract |
| 4 | No execution before all gates pass (single owner of control) | AP-401, AP-402, AP-406 | System/Scenario |
| 4 | Replayable orchestration decisions | AP-401 | Determinism/Replay |
| 4 | Capability-first runtime independence (same WP, many adapters) | AP-403, AP-404 | System/Scenario |
| 4 | Immutable audit; governance denies policy-violating action | AP-406 | Governance/Policy |
| 4 | Runtime failure pauses, never crashes | AP-401, AP-405 | Failure-injection |
| 5 | Completion by evidence, never runtime self-report | AP-502 | System/Scenario |
| 5 | Insufficient evidence ⇒ not complete | AP-502 | Failure-injection |
| 5 | Supervision recommends; Orchestration acts (one owner per verb) | AP-501, AP-401 | Architecture + Scenario |
| 5 | Recover-from-checkpoint-not-restart; no evidence loss | AP-503, AP-204 | Recovery |
| 5 | Bounded retries | AP-503 | Failure-injection |
| 6 | Only validated outcomes enter Knowledge | AP-601, AP-602 | Governance + Scenario |
| 6 | Reflections evidence-sourced; candidates advisory, not direct writes | AP-601 | Unit + Integration |
| 6 | Knowledge reuse measurable; deprecated knowledge excluded | AP-603 | System/Scenario (reuse) |
| 6 | Full-layer observability + immutable audit; targets met under load | AP-604 | Observability + Performance |

Invariants enforced *continuously across all phases* (not a single gate):
one-way dependency flow (AP-005, §3) and seam-contract integrity (AP-006, §3).
A regression in either blocks the current phase's gate.

---

## 8. Cross-Reference

- **Phase definitions & gate sequence:** `01_PHASES.md`.
- **AP acceptance criteria & validation strategy:** `02_ACTION_POINTS.md`.
- **Test types that produce gate evidence:** `11_TESTING_STRATEGY.md` (§7 maps
  each invariant to a test type; §"Testing by Phase" maps which test types come
  online per phase).
- **Sequencing of phases into delivery:** `12_ROADMAP.md`.
