# Nexus v2 — Architecture Decision Record (ADR) Backlog

Status: Engineering Plan
Scope: The architectural decisions that must be recorded for Nexus v2 — both the
foundational decisions that gate implementation and the "why" decisions that
capture the rationale of the target architecture.

---

## How to Read This Backlog

This backlog distinguishes **ratified-in-Phase-0** decisions (which resolve open
gaps and block downstream phases) from **rationale ADRs** (which record *why* the
architecture is shaped as it is, so the shape is not silently eroded) and from
**deferred infrastructure-selection ADRs** (technology choices presented as
options, with no answer invented here).

Only **architectural** decisions appear. Implementation choices (library
selection within an already-decided boundary, naming conventions, formatting)
are out of scope and belong in code review, not here.

**Status values.**
- **Accepted (Phase 0)** — must be ratified before Phase 1 begins. Carried as
  "must be Accepted in Phase 0."
- **Accepted** — records an already-settled architectural stance (a "why" ADR);
  recorded to prevent regression.
- **Proposed** — a decision still requiring a worked option analysis.
- **Deferred** — an infrastructure-selection decision whose options are
  enumerated but not chosen; selection scheduled with the consuming phase.

Each ADR cites its motivating gaps (`G#`, see `08_ARCHITECTURE_GAPS.md`) and the
Action Points it gates or is gated by (`AP-###`, see `02_ACTION_POINTS.md`). The
closing table maps every ADR to its gaps and blocking APs.

---

## Foundational ADRs (Must Be Accepted in Phase 0)

### ADR-001 — Persistence & Event-Sourcing Model
- **Status.** Accepted (Phase 0) — must be ratified before any Phase 2 work.
- **Context.** Three candidate sources of operational truth coexist across the
  Event (23), State (24), and Checkpoint (25) models. The architecture never
  states which store is authoritative for "where is this execution now," nor how
  Checkpoints relate to the event log. Every Phase 2 component depends on this
  answer. (G1)
- **Decision drivers.** Replayability and audit; recovery correctness
  (reconstruct state after failure); consistency guarantees; operational
  complexity; latency on the orchestration hot path; idempotency under
  at-least-once delivery.
- **Options under consideration.**
  1. **Event-sourced** — state is a projection of the immutable event log;
     checkpoints are materialized snapshots of projections.
  2. **Stored-state** — state is the authority; events are an audit/notification
     side-channel; checkpoints copy stored state.
  3. **Hybrid** — stored state is authoritative for "now," the event log
     provides audit/replay, and checkpoints are materialized snapshots
     referencing (not copying) external objects.
- **Decision.** Selected in Phase 0 (the hybrid option is the leading candidate
  given the reference-not-copy checkpoint requirement and hot-path latency, but
  the choice is ratified by spike, not assumed here).
- **Consequences.** Fixes the consistency model for the Event Bus/Store
  (`AP-201`), Idempotency framework (`AP-202`), State Engine (`AP-203`), and
  Checkpoint Store (`AP-204`). Wrong choice forces rework of all of Phase 2.
  Produces a one-page persistence contract every Phase 2 AP implements.
- **Related gaps.** G1.
- **Related APs.** AP-001 (owner); AP-101, AP-112, AP-201, AP-202, AP-203,
  AP-204 (consumers).

### ADR-002 — Registration & Capability Contract Unification
- **Status.** Accepted (Phase 0) — must be ratified before the Phase 1
  Capability/Resource/Harness schemas.
- **Context.** Four registries (Harness 11, Runtime 15, Capability 21, Resource
  22) share near-identical fields; Provider/Availability/Health live in two
  registries; capability resolution has no owner. (G2, and the Resource
  state-machine half of G10)
- **Decision drivers.** Single source of truth per field; a clean hierarchy
  (abstract vs. allocatable vs. boundary); avoiding both over-merge (collapsing
  useful distinctions) and under-merge (preserving drift).
- **Options under consideration.** Layered model where **Capability** =
  abstract *what*; **Harness** = integration boundary exposing capabilities;
  **Resource** = allocatable instance; **Runtime** = a Runtime-category Harness.
  Alternatives differ in where Provider/Availability/Health are owned (on
  Resource+Harness only, vs. partly on Capability).
- **Decision.** Adopt the layered hierarchy; Provider/Availability/Health are
  owned by Resource/Harness, never by Capability; capability **resolution**
  produces candidates (a Phase-3 concern), **selection/allocation** is
  Orchestration's.
- **Consequences.** One authoritative field-ownership table drives `AP-108`
  (Capability), `AP-109` (Resource/Harness), and `AP-207` (Harness SDK). Runtime
  Model is expressed as a Harness specialization, eliminating a parallel
  registration contract.
- **Related gaps.** G2, G10 (resource-registry half).
- **Related APs.** AP-002 (owner); AP-108, AP-109, AP-207, AP-304.

### ADR-003 — Object Model Reconciliation
- **Status.** Accepted (Phase 0) — must be ratified before any Phase 1 schema.
- **Context.** Multiple objects are defined twice or owned twice: Work Package
  (G3), Execution Graph containment + redundant Dependency Graph (G4),
  Observation ownership (G5), the Intent Resolution / Executive Intelligence
  rename and Goal-metadata location (G6, G7), and the recovery/validation
  strategy ownership split (G13). Touching the Object Model ripples into every
  layer, so it must be settled before Phase 1, never during.
- **Decision drivers.** One structure and one owning layer per object; the
  outcome-not-procedure invariant for Goal; a single source of topology truth;
  the detection-vs-emission boundary for Observation.
- **Options under consideration.** For each contested object, the candidate
  resolutions are: (a) one unified Work Package schema (the doc-05 superset,
  with embedded Context Package); (b) Execution Graph as a **sibling** output of
  Planning, with the separate Dependency Graph absorbed into its edges;
  (c) Execution emits raw Execution Events, **Supervision derives/owns**
  Observation; (d) "Intent Resolution" is the canonical name, with Goal metadata
  (confidence/domain/priority/clarification) living on the Goal object.
- **Decision.** Adopt (a)–(d) above; record a precedence note that Validation
  owns completion regardless of Skill- or Strategy-level validation strategy
  (the validation half of G13; the recovery-precedence half is shared with
  ADR-004).
- **Consequences.** Drives `AP-102` (Goal), `AP-104` (Plan + Execution Graph),
  `AP-105` (unified Work Package), `AP-107` (Skill), and `AP-110` (Execution
  Session / Observation / Evidence). The architecture index is updated to "Intent
  Resolution" (`AP-007`).
- **Related gaps.** G3, G4, G5, G6, G7, G13 (validation precedence half).
- **Related APs.** AP-003 (owner); AP-102, AP-104, AP-105, AP-107, AP-110,
  AP-007.

### ADR-004 — Policy Language, Approval Taxonomy & Determinism Boundaries
- **Status.** Accepted (Phase 0) — must be ratified before the Policy Engine.
- **Context.** Three intertwined unknowns: the policy condition/constraint
  language and the undefined "Specificity" conflict-resolution term (G12); the
  two competing approval vocabularies (Governance vs. Execution Strategy, G8);
  and asserted determinism over inherently non-deterministic steps (G14). They
  share one decision because the policy engine, approval workflow, and
  determinism contract are evaluated together.
- **Decision drivers.** Testable, deterministic conflict resolution; a single
  approval vocabulary across Governance and Execution Strategy; honest
  determinism boundaries that tests can encode; avoiding a heavy DSL interpreter
  while keeping logic out of code.
- **Options under consideration.**
  1. **Policy expression** — data-driven declarative rules vs. an embedded DSL.
  2. **Specificity** — define a computable specificity metric feeding the
     conflict-resolution order (Specificity → Priority → Version → Default).
  3. **Approval vocabulary** — one merged taxonomy spanning Automatic / Human
     Review / Explicit Approval (Governance) and Automatic / Human / Multi-stage
     / Deferred (Execution Strategy).
  4. **Determinism** — an explicit statement of where determinism is guaranteed
     (policy evaluation, state transitions, conflict resolution) and where it is
     best-effort ("attempt identical behavior": LLM intent, LLM runtimes, human
     approval/validation, recovery selection).
- **Decision.** Adopt a data-driven rule language with a defined specificity
  metric; unify the approval taxonomy into one vocabulary; publish the
  determinism boundary as a contract. Also bounds the recovery-vs-strategy
  precedence half of G13.
- **Consequences.** Drives `AP-106` (Execution Strategy approval vocabulary),
  `AP-205` (Policy Engine condition language + conflict resolution), `AP-308`
  (Strategy generator), and `AP-406` (Governance gate). Acceptance criteria
  across Phases 3–5 cite the determinism boundary instead of asserting blanket
  determinism.
- **Related gaps.** G8, G12, G14, G13 (recovery-precedence half).
- **Related APs.** AP-004 (owner); AP-106, AP-205, AP-308, AP-406; informs
  AP-301, AP-403, AP-405, AP-502, AP-503.

---

## Object-Model Reconciliation ADRs (Phase 0 → enforced in Phase 1)

These record decisions narrower than ADR-003 but still architectural: they fix a
canonical vocabulary that multiple schemas must share. They are accepted in
Phase 0 and enforced by Phase 1 schema tests.

### ADR-008 — Single Status Vocabulary for Validation Results and Artifacts
- **Status.** Accepted (Phase 0) — enforced in Phase 1.
- **Context.** Validation exposes a result set {Passed/Failed/Partial/Requires
  Review} and a state set including {…Waiting Human Review}, naming the same
  human-review condition twice (G9). The Artifact carries both a Lifecycle
  {Created/Produced/Validated/Versioned/Referenced/Archived} and a Status
  {Draft/Generated/Validated/Approved/Published/Archived}, two overlapping
  progressions, plus an Evidence field overlapping the canonical Evidence object
  (G11).
- **Decision drivers.** One term per condition; an unambiguous Knowledge gate
  filter; lineage clarity; no field competing with the canonical Evidence
  object.
- **Options under consideration.** Collapse Validation's "Requires Review" and
  "Waiting Human Review" into one term; choose one Artifact progression
  vocabulary (status vs. lifecycle) and demote the other to a derived view;
  replace the Artifact Evidence field with a reference to the canonical Evidence
  object.
- **Decision.** One validation outcome vocabulary; one Artifact progression
  vocabulary; Artifact references (never embeds) Evidence.
- **Consequences.** Drives `AP-111` (Artifact), `AP-112` (Validation Report
  enum), and `AP-502` (Validation Engine).
- **Related gaps.** G9, G11.
- **Related APs.** AP-111, AP-112, AP-502.

### ADR-009 — Single Unified State Model
- **Status.** Accepted (Phase 0) — enforced in Phase 1/2.
- **Context.** The Resource object is governed by two state machines — its own
  availability states (Available/Busy/Reserved/Offline/Maintenance/Failed/
  Unknown) and the generic lifecycle (Created/Ready/Active/…) — and the State
  Model itself drifts between "Active" and "Executing" (G10).
- **Decision drivers.** Exactly one state machine per object; consistent
  transition vocabulary so guards and illegal-transition matrices are testable.
- **Options under consideration.** Either (a) the generic lifecycle subsumes
  resource availability as substates of "Active," or (b) Resource availability
  is recognized as a distinct, registered state machine owned by the Resource
  registry per ADR-002 — but only one, never both. Resolve "Active" vs.
  "Executing" to a single term.
- **Decision.** One state machine per object, with the resource-availability
  ownership decided jointly with ADR-002; the State Model's transition
  vocabulary is normalized to a single term.
- **Consequences.** Drives `AP-109` (Resource/Harness state machine) and
  `AP-203` (State Machine Engine, illegal-transition guards).
- **Related gaps.** G10.
- **Related APs.** AP-109, AP-203; coupled to ADR-002 (AP-002).

---

## Rationale ADRs (Accepted — Record the "Why")

These record the architecture's load-bearing stances so they are not silently
eroded during implementation. They are already settled by the target
architecture; recording them prevents regression.

### ADR-005 — Event-Driven Architecture
- **Status.** Accepted.
- **Context.** Orchestration, Supervision, Recovery, and the State Model all
  coordinate through events rather than direct calls.
- **Decision drivers.** Loose coupling across layers; replayability and audit;
  observability of every decision; the one-way dependency flow.
- **Decision.** Inter-layer coordination is event-driven; every state transition
  emits exactly one event; consumers are idempotent under at-least-once
  delivery.
- **Consequences.** Requires the Event Bus/Store (`AP-201`) and a shared
  idempotency/correlation framework (`AP-202`); makes replay the basis of audit
  and recovery.
- **Related gaps.** G1 (consistency model), G5 (Execution emits events).
- **Related APs.** AP-201, AP-202, AP-203, AP-401, AP-501.

### ADR-006 — Skills as Runtime-Independent Procedures
- **Status.** Accepted.
- **Context.** Skills describe *capability*, not *runtime*; selection must ignore
  which runtime executes them.
- **Decision drivers.** Runtime independence; reusability; composability;
  separation of "what to do" from "where it runs."
- **Decision.** A Skill carries no runtime references; selection is by
  capability/context/constraints/evidence only; composition chains are
  first-class.
- **Consequences.** Drives the Skill schema (`AP-107`) and selection/composition
  (`AP-305`); the dual ownership of recovery/validation strategy is resolved by
  ADR-003/ADR-004, not by leaking runtime into the Skill.
- **Related gaps.** G13.
- **Related APs.** AP-107, AP-305.

### ADR-007 — Work Packages as the Universal Runtime Contract
- **Status.** Accepted.
- **Context.** Every layer from Planning through Validation produces or consumes
  the Work Package; it is the busiest seam in the platform and is currently
  defined three times (G3).
- **Decision drivers.** A single self-contained execution unit; no raw operator
  request reaching a runtime; embedded context so a runtime needs nothing else.
- **Decision.** One unified Work Package schema (embedded Context Package,
  evidence, completion criteria, status machine) is the universal contract; all
  producers/consumers bind to it.
- **Consequences.** Drives `AP-105` (schema) and `AP-309` (Work Packaging); makes
  the WP the multi-seam contract-test anchor.
- **Related gaps.** G3.
- **Related APs.** AP-105, AP-309; bound by AP-104, AP-401, AP-405, AP-502.

### ADR-010 — The Harness as the Single Integration Boundary
- **Status.** Accepted.
- **Context.** Runtimes, context sources, validators, knowledge stores,
  communication, governance, and observability are all external systems; the
  architecture exposes them through one boundary contract.
- **Decision drivers.** A uniform contract (Identity, Capabilities, Availability,
  Health, Operations, Events, Errors, Metrics, Version); replaceable external
  systems; a single place for registration, discovery, and health.
- **Decision.** All external systems integrate via a Harness; Runtime, Context,
  Knowledge, Validation, Communication, Governance, and Observability harnesses
  are categories of one base contract.
- **Consequences.** Drives the Harness SDK + registry (`AP-207`); later category
  harnesses (`AP-302`, `AP-403`, `AP-404`) extend it. Reconciled with the
  registry-unification decision (ADR-002).
- **Related gaps.** G2.
- **Related APs.** AP-207, AP-302, AP-403, AP-404; coupled to AP-002.

### ADR-011 — Capability-First, Not Model-First
- **Status.** Accepted.
- **Context.** Work is reasoned about in terms of abstract capabilities, with
  concrete providers (models, runtimes, humans) resolved later.
- **Decision drivers.** Provider substitutability; planning that does not depend
  on a specific model; clean separation of resolution (candidates) from selection
  (allocation).
- **Decision.** Planning expresses required **capabilities**; Capability
  Resolution returns provider candidates; Orchestration selects/allocates. No
  provider/availability/health on the Capability object.
- **Consequences.** Drives `AP-108` (Capability schema) and `AP-304` (resolution);
  depends on the field-ownership table from ADR-002.
- **Related gaps.** G2.
- **Related APs.** AP-108, AP-304; coupled to AP-002.

### ADR-012 — Checkpoints and Recover-From-State
- **Status.** Accepted.
- **Context.** Long-running work must resume from the latest valid checkpoint
  rather than restart from the operator's intent.
- **Decision drivers.** No loss of validated work on failure; reference-not-copy
  snapshots; pre-restore validation (integrity, artifact availability, policy
  compatibility).
- **Decision.** Checkpoints are reference-not-copy snapshots with parent linkage;
  recovery restores from the latest valid checkpoint and never re-derives from
  operator intent.
- **Consequences.** Drives the Checkpoint Store (`AP-204`) and the Recovery
  Engine (`AP-503`); the checkpoint/event relationship is fixed by ADR-001.
- **Related gaps.** G1.
- **Related APs.** AP-204, AP-503; coupled to AP-001.

### ADR-013 — Independent Recovery Engine (Recover, Don't Restart)
- **Status.** Accepted.
- **Context.** Failure response is a distinct concern: Supervision detects,
  Orchestration acts, Recovery decides the strategy.
- **Decision drivers.** A single owner for failure classification and strategy
  selection; bounded retry/failover; no Governance bypass and no override of
  Validation.
- **Decision.** Recovery is an independent layer that classifies failures,
  deterministically selects a strategy (Continue/Retry/Resume/Rollback/Checkpoint
  Restore/Switch Runtime/Request Context/Human Review/Abort), restores, and
  resumes — reconciling pre-declared recovery edges with runtime selection.
- **Consequences.** Drives `AP-503`; the pre-declared-edge vs. runtime-selection
  precedence is fixed by ADR-003/ADR-004.
- **Related gaps.** G13, G14.
- **Related APs.** AP-503; coupled to AP-501, AP-401.

### ADR-014 — Validation Independent of Execution (Evidence Over Confidence)
- **Status.** Accepted.
- **Context.** Completion is determined by independently verifiable evidence, not
  by a runtime's self-report.
- **Decision drivers.** Trust separation (the executor never validates its own
  work); evidence properties (Observable/Repeatable/Independent/Traceable/
  Auditable); a four-valued outcome.
- **Decision.** Execution emits **evidence candidates**; Validation independently
  collects evidence and determines completion; insufficient evidence never
  completes a Work Package.
- **Consequences.** Drives `AP-110` (Evidence vs. Evidence Candidate), `AP-405`
  (no self-completion), and `AP-502` (Validation Engine); the outcome vocabulary
  is fixed by ADR-008.
- **Related gaps.** G9 (outcome vocabulary), G14 (validation determinism bound).
- **Related APs.** AP-110, AP-405, AP-502; coupled to AP-112.

### ADR-015 — Deterministic Governance with Immutable Audit
- **Status.** Accepted.
- **Context.** Authority over autonomy is enforced at the execution boundary
  with a policy-driven, auditable gate.
- **Decision drivers.** Deterministic authorization decisions; an immutable audit
  trail; integration at the orchestration boundary; a defined approval workflow.
- **Decision.** Governance evaluates policy deterministically (Allow/Deny/Require
  Approval/Delay/Escalate/Request Info), blocks approval-required actions until
  resolved, and records an immutable audit entry for every decision.
- **Consequences.** Drives `AP-406`; depends on the unified approval vocabulary
  and determinism boundary from ADR-004 and the Policy Engine (`AP-205`).
- **Related gaps.** G8, G14.
- **Related APs.** AP-406, AP-205; coupled to AP-004.

---

## Deferred Infrastructure-Selection ADRs (Options Only — No Answer Invented)

These are genuinely architectural (they fix a boundary technology), but the
selection is deferred to the consuming phase. Options are enumerated; **no final
choice is recorded here.**

### ADR-016 — Message Bus / Event Store Technology
- **Status.** Deferred — selected with Phase 2 (`AP-201`).
- **Context.** ADR-001 fixes the persistence *model*; this ADR selects the
  *technology* that provides durable, ordered, replayable events with
  at-least-once delivery and dead-letter handling.
- **Decision drivers.** Causal ordering per correlation id; durable replay;
  dead-letter support; operational footprint; consistency with the ADR-001
  model.
- **Options under consideration.** A log-structured streaming platform; a durable
  broker with an outbox/event-store table; an embedded/event-store-first
  database. (Selection deferred; no option chosen.)
- **Consequences.** Constrains `AP-201`, `AP-202`. Folded conceptually under
  ADR-001 in the overview but recorded separately because the technology choice
  is independent of the model choice.
- **Related gaps.** G1.
- **Related APs.** AP-201, AP-202.

### ADR-017 — Artifact / Checkpoint / Knowledge Storage Backends
- **Status.** Deferred — selected with Phases 2 and 6 (`AP-206`, `AP-204`,
  `AP-602`).
- **Context.** Immutable artifact storage, checkpoint snapshots, and the
  knowledge graph each need a durable backend; the architecture fixes their
  *contracts* (immutability, reference-not-copy, validation-gated ingestion) but
  not their *backends*.
- **Decision drivers.** Immutability and versioning; reference resolution;
  lineage; graph query for Knowledge; growth/GC; backend substitutability behind
  a storage abstraction.
- **Options under consideration.** Object/blob storage with a metadata index for
  Artifacts/Checkpoints; a property-graph or triple store vs. a relational +
  index hybrid for Knowledge. (Selection deferred; no option chosen.)
- **Consequences.** Constrains `AP-206` (Artifact Store), `AP-204` (Checkpoint
  Store), and `AP-602` (Knowledge Graph Store). Must preserve immutability and
  reference-not-copy guarantees regardless of backend.
- **Related gaps.** G1, G11.
- **Related APs.** AP-204, AP-206, AP-602.

---

## ADR → Motivating Gaps → Blocking APs

| ADR | Title | Status | Motivating Gaps | Blocking / Owned APs |
|-----|-------|--------|-----------------|----------------------|
| ADR-001 | Persistence & Event-Sourcing Model | Accepted (Phase 0) | G1 | AP-001; gates AP-201/202/203/204 |
| ADR-002 | Registration & Capability Contract Unification | Accepted (Phase 0) | G2, G10 | AP-002; gates AP-108/109/207/304 |
| ADR-003 | Object Model Reconciliation | Accepted (Phase 0) | G3, G4, G5, G6, G7, G13 | AP-003; gates AP-102/104/105/107/110 |
| ADR-004 | Policy Language + Approval Taxonomy + Determinism | Accepted (Phase 0) | G8, G12, G13, G14 | AP-004; gates AP-106/205/308/406 |
| ADR-005 | Event-Driven Architecture | Accepted | G1, G5 | AP-201/202/203/401/501 |
| ADR-006 | Skills as Runtime-Independent Procedures | Accepted | G13 | AP-107/305 |
| ADR-007 | Work Packages as Universal Runtime Contract | Accepted | G3 | AP-105/309 |
| ADR-008 | Single Status Vocabulary (Validation + Artifact) | Accepted (Phase 0) | G9, G11 | AP-111/112/502 |
| ADR-009 | Single Unified State Model | Accepted (Phase 0) | G10 | AP-109/203 |
| ADR-010 | Harness as Single Integration Boundary | Accepted | G2 | AP-207/302/403/404 |
| ADR-011 | Capability-First, Not Model-First | Accepted | G2 | AP-108/304 |
| ADR-012 | Checkpoints / Recover-From-State | Accepted | G1 | AP-204/503 |
| ADR-013 | Independent Recovery Engine | Accepted | G13, G14 | AP-503 |
| ADR-014 | Validation Independent of Execution | Accepted | G9, G14 | AP-110/405/502 |
| ADR-015 | Deterministic Governance + Immutable Audit | Accepted | G8, G14 | AP-406/205 |
| ADR-016 | Message Bus / Event Store Technology | Deferred | G1 | AP-201/202 |
| ADR-017 | Artifact/Checkpoint/Knowledge Storage Backends | Deferred | G1, G11 | AP-204/206/602 |

ADR-001 through ADR-004 (and the Phase-0 object-model ADRs ADR-008/ADR-009) must
be **Accepted before Phase 1 begins**. The rationale ADRs (ADR-005…ADR-007,
ADR-010…ADR-015) are recorded as Accepted to prevent regression. The deferred
infrastructure ADRs (ADR-016, ADR-017) enumerate options only and are resolved
with their consuming phases.
