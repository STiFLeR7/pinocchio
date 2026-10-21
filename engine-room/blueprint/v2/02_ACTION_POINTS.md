# Nexus v2 — Action Points

Status: Engineering Plan
Scope: The authoritative Action Point (AP) catalog for implementing Nexus v2.

---

## How to Read This Catalog

An **Action Point** is the smallest independently plan, build, and verify unit
of implementation work. Every AP belongs to exactly one phase
(`01_PHASES.md`), declares its dependencies, and ends with explicit acceptance
criteria and a validation strategy.

AP identifiers are stable. They are referenced by `03_DEPENDENCY_GRAPH.md`,
`04_IMPLEMENTATION_ORDER.md`, `05_RISKS.md`, `10_VALIDATION_STRATEGY.md`,
`11_TESTING_STRATEGY.md`, and `12_ROADMAP.md`. Do not renumber an AP; deprecate
and supersede instead.

**ID scheme.** `AP-PNN` where `P` is the phase digit and `NN` is a sequence
number (e.g. `AP-301` is the first AP of Phase 3).

**Field set per AP.** Purpose · Description · Dependencies · Inputs · Outputs ·
Acceptance Criteria · Risks · Complexity · Effort · Priority · Suggested Tests ·
Validation Strategy.

**Scales.** Complexity: Low / Medium / High / Critical. Effort: S (≤2d) / M
(≤1w) / L (≤2w) / XL (>2w). Priority: P0 (blocking) / P1 (core) / P2
(important) / P3 (deferred-eligible).

> Source-document status note (2026-06-26): `09_SUPERVISION`, `11_HARNESS`, and
> `26_REFLECTION` are now specified. The catalog reflects the complete 13-stage
> pipeline. Phase 0 contains **reconciliation** work, not missing-spec authoring.

---

# Phase 0 — Foundation & Architectural Decisions

### AP-001 — Ratify the Persistence & Event-Sourcing Model
- **Purpose.** Decide the single source of operational truth across Event (23),
  State (24), and Checkpoint (25). This is the most consequential unmade
  decision in the architecture.
- **Description.** Choose between event-sourced state (state derived from the
  event log), independently stored state, or a hybrid (stored state + event log
  for audit/replay + checkpoints as materialized snapshots). Define how
  Checkpoints relate to the event log (derived vs. independent), how state is
  reconstructed on recovery, and the durability/consistency guarantees.
- **Dependencies.** None.
- **Inputs.** Docs 23, 24, 25, 19, 18.
- **Outputs.** Accepted ADR-001; a one-page "persistence contract" all Phase 2
  APs implement.
- **Acceptance Criteria.** A ratified ADR stating the model; a worked example
  tracing one Work Package's state, events, and checkpoints through a failure
  and recovery; explicit statement of which store is authoritative for "where
  is this execution now."
- **Risks.** Wrong choice forces rework of all of Phase 2. Event-sourcing
  complexity vs. stored-state divergence.
- **Complexity.** Critical. **Effort.** M. **Priority.** P0.
- **Suggested Tests.** Decision rehearsal: model the recovery example on paper
  and against a throwaway spike.
- **Validation Strategy.** Architecture review sign-off; spike demonstrating
  state reconstruction under the chosen model.

### AP-002 — Unify the Registration/Capability Contract (Harness · Runtime · Resource · Capability)
- **Purpose.** Resolve the four near-identical registration contracts now
  present in docs 11, 15, 21, 22 into one layered model.
- **Description.** The Harness common contract (Identity, Capabilities,
  Availability, Health, Configuration, Authentication, Operations, Events,
  Errors, Metrics, Version) overlaps the Runtime Registration, Resource
  Registry, and Capability Registry field sets. Define the canonical hierarchy:
  Capability = abstract *what*; Harness = integration boundary exposing
  capabilities; Resource = allocatable instance; Runtime = a Runtime-category
  Harness. Decide where Provider/Availability/Health live to eliminate dual
  sources of truth.
- **Dependencies.** None.
- **Inputs.** Docs 11, 15, 21, 22.
- **Outputs.** ADR-002; a single registration/capability contract spec.
- **Acceptance Criteria.** One authoritative field-ownership table; no field
  (Provider/Availability/Health/Version) has two owning registries; Runtime
  Model expressed as a Harness specialization.
- **Risks.** Over-merging collapses useful distinctions; under-merging keeps the
  drift.
- **Complexity.** High. **Effort.** M. **Priority.** P0.
- **Suggested Tests.** Cross-walk every field in all four docs to exactly one
  owner.
- **Validation Strategy.** Architecture review; the Phase 1 Capability/Resource
  schemas (AP-108/109) must derive from this table.

### AP-003 — Reconcile the Object Model Contradictions
- **Purpose.** Remove the cross-document object inconsistencies that would
  fracture the Phase 1 schemas.
- **Description.** Decide and record: (a) the single **Work Package** schema
  (docs 04, 05 differ); (b) **Execution Graph** containment — nested in Plan
  (02) vs. sibling output (01/04/18), and whether the separate **Dependency
  Graph** (04) is redundant; (c) **Observation** ownership — Execution emits raw
  Execution Events (08), Supervision derives/owns Observation (02/09);
  (d) **Intent Resolution (16) == Executive Intelligence (01/02)** rename, and
  where the richer Goal metadata (confidence/domain/priority) lives.
- **Dependencies.** None.
- **Inputs.** Docs 01, 02, 04, 05, 08, 09, 16, 18.
- **Outputs.** ADR-003 (object reconciliation); updated Object Model addendum.
- **Acceptance Criteria.** Each contested object has exactly one defined
  structure and one owning layer; the architecture index reflects Intent
  Resolution; no "defined twice" objects remain.
- **Risks.** Touching the Object Model ripples into every layer; must be done
  before Phase 1, never during.
- **Complexity.** High. **Effort.** M. **Priority.** P0.
- **Suggested Tests.** Traceability matrix object → owning layer → producing/
  consuming seams.
- **Validation Strategy.** Architecture review; Phase 1 schemas cite this ADR.

### AP-004 — Define the Policy Condition Language & Determinism Model
- **Purpose.** Make the asserted "deterministic policy evaluation" real and
  reconcile the approval taxonomy.
- **Description.** Choose the policy condition/constraint expression mechanism
  (data-driven rules vs. embedded DSL), define how "Specificity" in conflict
  resolution is computed, and unify the **approval taxonomy** (Governance:
  Automatic/Human Review/Explicit; Execution Strategy: Automatic/Human/
  Multi-stage/Deferred) into one vocabulary. Define determinism boundaries for
  inherently non-deterministic steps (LLM intent, human approval).
- **Dependencies.** None.
- **Inputs.** Docs 12, 13, 20.
- **Outputs.** ADR-004; canonical approval vocabulary; policy-language decision.
- **Acceptance Criteria.** One approval vocabulary used by Governance and
  Execution Strategy; a defined, testable specificity rule; an explicit
  statement of where determinism is and is not guaranteed.
- **Risks.** Choosing a heavy DSL adds an interpreter to maintain; choosing weak
  rules pushes logic back into code.
- **Complexity.** High. **Effort.** M. **Priority.** P0.
- **Suggested Tests.** Conflict-resolution truth table; same-input/same-output
  determinism cases.
- **Validation Strategy.** Architecture review; feeds AP-205 (Policy Engine).

### AP-005 — Engineering Substrate: Repo, CI, Quality Gates
- **Purpose.** Stand up the buildable skeleton and quality enforcement.
- **Description.** Package/module boundaries mirroring the layer architecture;
  CI pipeline (lint, type-check, test); coverage and dependency-direction
  enforcement (no lower layer importing a higher layer); pre-commit hooks;
  reproducible dev environment.
- **Dependencies.** None.
- **Inputs.** `01_ARCHITECTURE.md` dependency rules.
- **Outputs.** Green CI on an empty skeleton; enforced layer boundaries.
- **Acceptance Criteria.** CI runs lint+type+test; an architecture-fitness test
  fails when a dependency points the wrong way; one-command environment setup.
- **Risks.** Under-enforced boundaries erode the architecture over time.
- **Complexity.** Medium. **Effort.** M. **Priority.** P0.
- **Suggested Tests.** Architecture-fitness/dependency test; CI smoke.
- **Validation Strategy.** CI green; deliberately-wrong import fails the build.

### AP-006 — Contract-Test Harness
- **Purpose.** Provide the mechanism every later phase uses to prove
  producer/consumer compatibility at each seam.
- **Description.** A reusable harness that loads object schemas and asserts that
  a producer's output validates against the consumer's expected input schema,
  with shared fixtures. Foundation for all seam tests.
- **Dependencies.** AP-005.
- **Inputs.** Phase 1 schema format (AP-101).
- **Outputs.** Contract-test framework + fixture conventions.
- **Acceptance Criteria.** A sample producer/consumer pair passes; an
  intentional schema drift fails with a clear diff.
- **Risks.** If too rigid, slows iteration; if too loose, misses drift.
- **Complexity.** Medium. **Effort.** M. **Priority.** P0.
- **Suggested Tests.** Self-test on a fixture pair.
- **Validation Strategy.** Used by every Phase 1+ seam AP.

### AP-007 — Canonical Glossary & Architecture Index Repair
- **Purpose.** One vocabulary; a correct map of the doc set.
- **Description.** Author a glossary (Goal, Context Package, Plan, Work Package,
  Skill, Capability, Resource, Harness, Execution Strategy, Execution Graph,
  Execution Session, Observation, Evidence, Artifact, Checkpoint, Event, Policy,
  Validation Report, Reflection, Knowledge). Fix the stale `docs/v2/README.md`
  index to list 00–26 with correct titles, and record the `13_EXECUTION_MODEL`
  vs. "Execution Strategy" naming resolution.
- **Dependencies.** AP-002, AP-003, AP-004.
- **Inputs.** All `docs/v2/` files.
- **Outputs.** `GLOSSARY.md`; corrected index; naming ADR note.
- **Acceptance Criteria.** Every architectural term defined once; index matches
  files on disk; one canonical name for doc 13.
- **Risks.** Low.
- **Complexity.** Low. **Effort.** S. **Priority.** P1.
- **Suggested Tests.** Link-check the index against the filesystem.
- **Validation Strategy.** Documentation review.

---

# Phase 1 — Core Object Model & Contracts

### AP-101 — Object Schema Format, Identity & Versioning Convention
- **Purpose.** One serialization + identity + versioning convention for all
  objects.
- **Description.** Choose schema/serialization (per the persistence ADR),
  identifier scheme (namespacing across Goal/Plan/WP/Artifact/Event/etc.), and
  object versioning rules (immutability-by-default for Artifacts/Checkpoints).
- **Dependencies.** AP-001, AP-003.
- **Inputs.** Object Model + all model docs.
- **Outputs.** Schema/serialization library; identity + version conventions.
- **Acceptance Criteria.** Round-trip serialize/deserialize for a sample of
  each object family; stable identifiers; version bump rules tested.
- **Risks.** Format lock-in.
- **Complexity.** Medium. **Effort.** M. **Priority.** P0.
- **Suggested Tests.** Round-trip + identity-collision tests.
- **Validation Strategy.** Feeds every other Phase 1 AP.

### AP-102 — Goal & Goal Metadata Schema
- **Purpose.** Define the universal pipeline input that is referenced everywhere
  but structurally defined nowhere.
- **Description.** Goal (outcome, never procedure) + metadata (domain, scope
  included/excluded, priority, confidence, constraints, clarification state) per
  Intent Resolution (16).
- **Dependencies.** AP-101, AP-003.
- **Inputs.** Docs 02, 16.
- **Outputs.** Goal schema + contract tests.
- **Acceptance Criteria.** Goal carries no execution/procedure fields; metadata
  covers Intent Resolution outputs; consumed cleanly by Context Engineering.
- **Risks.** Leaking procedure into Goal (violates Rule 7).
- **Complexity.** Medium. **Effort.** S. **Priority.** P0.
- **Suggested Tests.** Negative test rejecting procedural fields.
- **Validation Strategy.** Contract test against Context Engineering input.

### AP-103 — Context Package Schema
- **Purpose.** The understanding→planning interface object.
- **Description.** The 8 Context Categories, Constraints, Resources, Supporting
  Artifacts, References, Confidence, Known Unknowns, Validation Status.
- **Dependencies.** AP-101, AP-102.
- **Inputs.** Doc 03.
- **Outputs.** Context Package schema + contract tests.
- **Acceptance Criteria.** Flattening vs. categories ambiguity resolved;
  validation-status field present; embeddable inside a Work Package.
- **Risks.** Field/category duplication (flagged in doc 03).
- **Complexity.** Medium. **Effort.** M. **Priority.** P0.
- **Suggested Tests.** Round-trip; embed-in-WP test.
- **Validation Strategy.** Contract test Context Engineering → Planning.

### AP-104 — Plan & Execution Graph Schema
- **Purpose.** The planning output topology.
- **Description.** Plan (milestones, dependencies, priorities, work packages,
  rationale) and Execution Graph (Nodes, Edge types: Execution/Data/Approval/
  Recovery/Conditional/Synchronization, Conditions, Checkpoints, Policies,
  State, Metadata, Metrics). Implements the AP-003 containment decision.
- **Dependencies.** AP-101, AP-003.
- **Inputs.** Docs 02, 04, 18.
- **Outputs.** Plan + Execution Graph schemas; acyclicity validator.
- **Acceptance Criteria.** Graph is a DAG (explicit loops only); nodes reference
  Work Packages; containment matches ADR-003; no separate redundant Dependency
  Graph unless ADR keeps it.
- **Risks.** Graph as single source of truth → schema must be airtight.
- **Complexity.** High. **Effort.** L. **Priority.** P0.
- **Suggested Tests.** Cycle-detection; edge-type validity; node→WP reference.
- **Validation Strategy.** Contract test Planning → Orchestration.

### AP-105 — Work Package Schema (Unified)
- **Purpose.** The single universal runtime contract; collapse the three
  divergent definitions.
- **Description.** Identity, Objective, Context (embedded Context Package),
  Constraints, Resources, Skills, Inputs, Outputs, Evidence, Completion
  Criteria, Status machine (Created→Ready→Executing→Paused→Completed +
  Blocked/Cancelled/Failed/Expired), Checkpoints, Observability fields.
- **Dependencies.** AP-101, AP-103, AP-003.
- **Inputs.** Docs 04, 05.
- **Outputs.** Work Package schema + state machine + contract tests.
- **Acceptance Criteria.** One schema reconciling docs 04+05; status machine
  matches State Model; completion criteria never reference runtime confidence.
- **Risks.** Highest contract-drift risk in the platform if not unified.
- **Complexity.** High. **Effort.** L. **Priority.** P0.
- **Suggested Tests.** State-transition tests; producer(Planning)/consumer
  (Execution) contract test.
- **Validation Strategy.** Multi-seam contract test (Planning, Orchestration,
  Execution, Validation all bind to this schema).

### AP-106 — Execution Strategy Schema
- **Purpose.** Declarative, runtime-agnostic coordination behavior.
- **Description.** Coordination, Runtime Policy, Approval Policy (per AP-004
  vocabulary), Retry Policy, Timeout Policy, Validation Policy, Recovery Policy,
  Checkpoint Policy.
- **Dependencies.** AP-101, AP-004.
- **Inputs.** Doc 13.
- **Outputs.** Execution Strategy schema + contract tests.
- **Acceptance Criteria.** No runtime-specific references; approval vocabulary
  matches Governance; policy fields consumable by Orchestration and Recovery.
- **Risks.** Overlapping policy types without precedence.
- **Complexity.** Medium. **Effort.** M. **Priority.** P0.
- **Suggested Tests.** Reject runtime-specific fields; policy-precedence test.
- **Validation Strategy.** Contract test → Orchestration + Recovery.

### AP-107 — Skill Schema & Registry Contract
- **Purpose.** Runtime-independent capability procedures.
- **Description.** Identity/version, Purpose, Inputs, Outputs, Required Context,
  Constraints, Procedure, Validation Strategy, Recovery Strategy; registry
  metadata + versioning + composition references.
- **Dependencies.** AP-101.
- **Inputs.** Doc 06.
- **Outputs.** Skill schema; registry contract.
- **Acceptance Criteria.** No runtime references; composition chains
  expressible; version-compatibility field present (resolution rule deferred to
  Phase 3).
- **Risks.** Dual ownership of recovery/validation strategy (Skill vs Strategy).
- **Complexity.** Medium. **Effort.** M. **Priority.** P1.
- **Suggested Tests.** Composition-reference resolution; schema validation.
- **Validation Strategy.** Contract test → Skill Selection (Phase 3).

### AP-108 — Capability Schema & Registry Contract
- **Purpose.** Abstract "what can be done" reasoning unit.
- **Description.** Identifier, Name, Description, Version, Category, Inputs,
  Outputs, Constraints, Dependencies, Metadata — per the AP-002 field-ownership
  table (no provider/health state here).
- **Dependencies.** AP-101, AP-002.
- **Inputs.** Doc 21.
- **Outputs.** Capability schema + registry contract.
- **Acceptance Criteria.** Carries no concrete provider/availability/health
  (those live on Resource/Harness); I/O typed enough for composition checks.
- **Risks.** Registry field duplication if AP-002 not honored.
- **Complexity.** Medium. **Effort.** M. **Priority.** P1.
- **Suggested Tests.** Field-ownership conformance to AP-002.
- **Validation Strategy.** Contract test with Resource/Harness schemas.

### AP-109 — Resource & Harness Schemas
- **Purpose.** Allocatable instances and the integration boundary contract.
- **Description.** Resource (Identity, Type, Capabilities, Status, Availability,
  Owner, Configuration, Constraints, Health, Version, Metadata) and the Harness
  common contract (Identity, Capabilities, Availability, Health, Configuration,
  Authentication, Operations, Events, Errors, Metrics, Version) + lifecycle.
  Resolves the Resource-availability vs. State-Model contradiction per AP-002/003.
- **Dependencies.** AP-101, AP-002, AP-003.
- **Inputs.** Docs 11, 15, 22.
- **Outputs.** Resource + Harness schemas; harness lifecycle state machine.
- **Acceptance Criteria.** One state model for resource availability (reconciled
  with State Model); Runtime expressed as a Harness category.
- **Risks.** Dual state machines if reconciliation skipped.
- **Complexity.** High. **Effort.** L. **Priority.** P1.
- **Suggested Tests.** State-machine conformance; capability-advertisement test.
- **Validation Strategy.** Contract test with Capability + Orchestration.

### AP-110 — Execution Session, Observation & Evidence Schemas
- **Purpose.** The execution-time and verification-input objects.
- **Description.** Execution Session (runtime, progress, checkpoints,
  observations, outputs, artifacts); Observation (descriptive, Supervision-
  owned); Evidence (Observable/Repeatable/Independent/Traceable/Auditable) and
  Evidence Candidate (Execution-produced).
- **Dependencies.** AP-101, AP-003.
- **Inputs.** Docs 02, 08, 09, 14.
- **Outputs.** Three schemas + contract tests.
- **Acceptance Criteria.** Observation is descriptive-only; Evidence vs Evidence
  Candidate distinction explicit; Execution produces candidates, Validation
  produces Evidence.
- **Risks.** Observation ownership ambiguity (mitigated by AP-003).
- **Complexity.** Medium. **Effort.** M. **Priority.** P1.
- **Suggested Tests.** Candidate→Evidence promotion contract.
- **Validation Strategy.** Contract test Execution → Supervision → Validation.

### AP-111 — Artifact Schema, Lineage & Versioning
- **Purpose.** The shared output representation across all subsystems.
- **Description.** Identity, Type, Owner, Producer, timestamps, Version, Status,
  Workspace, Metadata, Lineage, Evidence ref, References; immutable-by-default;
  lineage chain Goal→Plan→WP→Execution→Artifact→Knowledge. Resolve the
  Status-vs-Lifecycle dual vocabulary (doc 17).
- **Dependencies.** AP-101.
- **Inputs.** Docs 02, 17.
- **Outputs.** Artifact schema; lineage model.
- **Acceptance Criteria.** Single status vocabulary; new-version-never-overwrite
  enforced; Knowledge references (never copies) artifacts.
- **Risks.** Storage growth (addressed in Phase 2).
- **Complexity.** Medium. **Effort.** M. **Priority.** P1.
- **Suggested Tests.** Immutability test (overwrite rejected); lineage walk.
- **Validation Strategy.** Contract test with Validation + Knowledge.

### AP-112 — Event, Policy, Checkpoint, Validation Report & Knowledge Entry Schemas
- **Purpose.** Remaining infrastructure object contracts.
- **Description.** Event (Identifier, Type, Version, Timestamp, Producer,
  Correlation/Execution IDs, Payload, Metadata, Source); Policy (Identity,
  Version, Conditions, Constraints, Actions, Priority, Owner, Lifecycle);
  Checkpoint (contents + metadata + versioning + parent linkage); Validation
  Report (Summary, Evidence, Satisfied/Failed Requirements, Recommendations,
  Validator, Confidence); Knowledge Entry (object types + confidence +
  freshness).
- **Dependencies.** AP-101, AP-001, AP-004.
- **Inputs.** Docs 20, 23, 24, 25, 14, 10.
- **Outputs.** Five schemas + contract tests.
- **Acceptance Criteria.** Validation result/state enum drift resolved; event
  carries correlation+trace; checkpoint references (not copies) external objects.
- **Risks.** Enum drift (doc 14); event versioning.
- **Complexity.** Medium. **Effort.** L. **Priority.** P1.
- **Suggested Tests.** Enum-consistency; event schema-version compat.
- **Validation Strategy.** Contract tests feeding all Phase 2 substrate APs.

---

# Phase 2 — Infrastructure Substrate

### AP-201 — Event Bus & Event Store
- **Purpose.** The event-driven communication backbone.
- **Description.** Publish/subscribe routing, ordering (causal within an
  execution), persistence, replay, dead-letter handling, schema-versioned
  payloads. Honors AP-001.
- **Dependencies.** AP-112, AP-001.
- **Inputs.** Doc 23.
- **Outputs.** Running bus + durable store with replay.
- **Acceptance Criteria.** At-least-once delivery; causal ordering per
  correlation id; replay reproduces a stream; dead-letter on poison events.
- **Risks.** Ordering under distributed delivery; replay correctness.
- **Complexity.** Critical. **Effort.** XL. **Priority.** P0.
- **Suggested Tests.** Replay determinism; out-of-order + dedup; DLQ.
- **Validation Strategy.** Replay a recorded stream → identical downstream state.

### AP-202 — Idempotency & Correlation Framework
- **Purpose.** Make at-least-once safe.
- **Description.** Shared idempotency-key + correlation/trace propagation so all
  consumers dedupe uniformly (the architecture *requires* consumer idempotency
  but specifies no mechanism).
- **Dependencies.** AP-201.
- **Inputs.** Doc 23.
- **Outputs.** Idempotency library + conventions.
- **Acceptance Criteria.** Duplicate event delivery causes no duplicate state
  change in a reference consumer.
- **Risks.** Per-subsystem reinvention if not centralized.
- **Complexity.** High. **Effort.** M. **Priority.** P0.
- **Suggested Tests.** Duplicate-delivery property test.
- **Validation Strategy.** Used by State Model + Orchestration.

### AP-203 — State Machine Engine & State Persistence
- **Purpose.** The unified operational lifecycle.
- **Description.** Core states + transition guards, illegal-transition
  rejection, exactly-one-event-per-transition, persistence per AP-001. Reconcile
  "Active" vs "Executing" naming; resolve Resource state per AP-002.
- **Dependencies.** AP-112, AP-201, AP-202, AP-001.
- **Inputs.** Doc 24.
- **Outputs.** State engine + store.
- **Acceptance Criteria.** Illegal transitions rejected; each transition emits
  exactly one event; state reconstructable per persistence ADR.
- **Risks.** Two sources of truth if event-sourcing vs stored-state unclear.
- **Complexity.** High. **Effort.** L. **Priority.** P0.
- **Suggested Tests.** Illegal-transition matrix; transition→event invariant.
- **Validation Strategy.** Drive a synthetic object through its full lifecycle.

### AP-204 — Checkpoint Store & Restoration
- **Purpose.** Resume long-running work without repetition.
- **Description.** Reference-not-copy snapshots; pre-restore validation
  (integrity, artifact availability, context validity, graph compatibility,
  policy compatibility); versioning + parent linkage.
- **Dependencies.** AP-111, AP-112, AP-203, AP-001.
- **Inputs.** Doc 25.
- **Outputs.** Checkpoint store + restore path.
- **Acceptance Criteria.** Write+restore round-trip; dangling reference detected
  pre-restore; policy-version pinning honored.
- **Risks.** Dangling references; policy incompatibility silently breaking
  restore.
- **Complexity.** High. **Effort.** L. **Priority.** P0.
- **Suggested Tests.** Restore-after-failure; missing-artifact rejection.
- **Validation Strategy.** Recovery scenario (Phase 5) depends on this.

### AP-205 — Policy Engine Runtime & Registry
- **Purpose.** Centralized deterministic policy evaluation.
- **Description.** Condition language (AP-004), deterministic conflict
  resolution (Specificity→Priority→Version→Default), registry, versioned
  evaluation records, simulation (side-effect free).
- **Dependencies.** AP-112, AP-004, AP-201.
- **Inputs.** Doc 20.
- **Outputs.** Policy evaluation service + registry + simulator.
- **Acceptance Criteria.** Same input+policies → same decision; versioned
  evaluation logged; simulation never mutates production.
- **Risks.** Latency on hot path; specificity ambiguity.
- **Complexity.** High. **Effort.** L. **Priority.** P0.
- **Suggested Tests.** Determinism; conflict-resolution truth table; sim
  isolation.
- **Validation Strategy.** Used by Governance, Validation, Recovery, Planning.

### AP-206 — Artifact Store
- **Purpose.** Durable, immutable, referenceable outputs.
- **Description.** Immutable-by-default storage with versioning + lineage +
  reference resolution; storage-backend abstraction.
- **Dependencies.** AP-111, AP-201.
- **Inputs.** Doc 17.
- **Outputs.** Artifact store + reference resolver.
- **Acceptance Criteria.** Overwrite rejected; version chain preserved;
  references resolve and are validated.
- **Risks.** Unbounded growth/GC.
- **Complexity.** Medium. **Effort.** M. **Priority.** P1.
- **Suggested Tests.** Immutability + lineage walk.
- **Validation Strategy.** Validation + Knowledge consume references.

### AP-207 — Harness SDK & Registry
- **Purpose.** The single integration boundary all external systems implement.
- **Description.** Implement the Harness common contract + lifecycle + health +
  failure model + registration + capability discovery (Need→Capability→Search
  Registry→Available Harnesses). The base SDK every category harness extends.
- **Dependencies.** AP-109, AP-108, AP-002, AP-201.
- **Inputs.** Doc 11.
- **Outputs.** Harness base SDK + registry + discovery.
- **Acceptance Criteria.** A reference harness registers, advertises
  capabilities, reports health, emits events to Supervision; discovery returns
  it by capability.
- **Risks.** Leaky abstraction across very different external systems.
- **Complexity.** High. **Effort.** L. **Priority.** P0.
- **Suggested Tests.** Mock-harness registration + discovery + health/event.
- **Validation Strategy.** Runtime/Context/Validation/Comm harnesses (Phases
  3–5) extend this.

---

# Phase 3 — Understanding Pipeline (Intent → Context → Plan → Strategy)

### AP-301 — Intent Resolution Engine
- **Purpose.** Operator request → normalized Goal.
- **Description.** Intent detection, ambiguity analysis, scope resolution,
  constraint discovery, goal normalization; emit Goal + metadata + clarification
  requests + confidence. Clarification-before-assumption default.
- **Dependencies.** AP-102, AP-205.
- **Inputs.** Operator request; doc 16.
- **Outputs.** Goal (+ metadata).
- **Acceptance Criteria.** Many phrasings → one canonical Goal; low confidence
  triggers clarification per policy; no plan/runtime leakage.
- **Risks.** Determinism claim vs LLM reality (bounded per AP-004).
- **Complexity.** High. **Effort.** L. **Priority.** P0.
- **Suggested Tests.** Paraphrase-normalization set; ambiguity → clarification.
- **Validation Strategy.** Contract test → Context Engineering.

### AP-302 — Context Source Connector Framework (Context Harnesses)
- **Purpose.** Pluggable read access to context sources via Harnesses.
- **Description.** Context Harness category atop AP-207; read-only connectors
  first (repository, filesystem, docs); authorization boundary; freshness.
- **Dependencies.** AP-207.
- **Inputs.** Doc 03 sources; doc 11.
- **Outputs.** Context Harness SDK + initial connectors.
- **Acceptance Criteria.** At least two real read-only sources behind one
  contract; access is authorized; failures surface as harness failures.
- **Risks.** Connector sprawl; auth/security on external data.
- **Complexity.** High. **Effort.** L. **Priority.** P1.
- **Suggested Tests.** Connector contract conformance; auth-denied path.
- **Validation Strategy.** Feeds AP-303.

### AP-303 — Context Engineering Engine
- **Purpose.** Goal → validated Context Package.
- **Description.** Discover→collect→validate→enrich→organize→package; validation
  dimensions (completeness/consistency/availability/freshness/authorization/
  quality); confidence + known-unknowns. Consumes Knowledge (read) when present.
- **Dependencies.** AP-103, AP-301, AP-302.
- **Inputs.** Goal; context sources; doc 03.
- **Outputs.** Context Package (validated).
- **Acceptance Criteria.** Produces exactly one Context Package per Goal; marks
  validation status; refuses to certify incomplete context.
- **Risks.** "Minimal complete context" has no sufficiency metric (flagged).
- **Complexity.** High. **Effort.** L. **Priority.** P0.
- **Suggested Tests.** Completeness/validation-status cases.
- **Validation Strategy.** Contract test → Planning; Planning rejects invalid
  packages.

### AP-304 — Capability Resolution
- **Purpose.** Required capability → available providers.
- **Description.** Resolve Planning's required capabilities against the
  Capability + Harness/Resource registries; ownership per AP-002 (resolution
  produces candidates; selection/allocation is Orchestration's).
- **Dependencies.** AP-108, AP-109, AP-207.
- **Inputs.** Required capabilities; doc 21.
- **Outputs.** Resolved capability→provider candidate set.
- **Acceptance Criteria.** Returns providers by capability without selecting a
  runtime; honors availability/health from the single owning registry.
- **Risks.** Resolution/selection boundary blur.
- **Complexity.** Medium. **Effort.** M. **Priority.** P1.
- **Suggested Tests.** Capability→provider matching; unavailable-provider path.
- **Validation Strategy.** Feeds Execution Strategy + Orchestration.

### AP-305 — Skill Registry, Selection & Composition
- **Purpose.** Select reusable procedures for required capabilities.
- **Description.** Registry + selection (capability/context/constraints/evidence,
  never runtime) + composition chains + version-compatibility resolution.
- **Dependencies.** AP-107, AP-304.
- **Inputs.** Doc 06.
- **Outputs.** Selected + composed Skills.
- **Acceptance Criteria.** Selection ignores runtimes; composition resolves;
  version conflicts handled by a defined rule.
- **Risks.** Combinatorial version conflicts at composition.
- **Complexity.** Medium. **Effort.** M. **Priority.** P1.
- **Suggested Tests.** Composition + version-conflict cases.
- **Validation Strategy.** Feeds Work Packaging.

### AP-306 — Planning Engine
- **Purpose.** Goal + Context → Plan + Work Packages + dependencies.
- **Description.** Goal analysis, decomposition into Work Packages, dependency
  analysis, complexity/cost/risk estimation, milestone identification; explainable
  decisions (rationale persisted). Refuses invalid Context Package.
- **Dependencies.** AP-104, AP-105, AP-303.
- **Inputs.** Goal; Context Package; doc 04.
- **Outputs.** Plan; Work Packages; dependencies; operational risks.
- **Acceptance Criteria.** Valid decomposition; dependencies acyclic; every
  decision explainable; hard refusal on invalid context.
- **Risks.** Estimation methodology unspecified (flagged) — start heuristic.
- **Complexity.** High. **Effort.** XL. **Priority.** P0.
- **Suggested Tests.** Decomposition fixtures; invalid-context refusal; rationale
  presence.
- **Validation Strategy.** Contract test → Execution Graph builder.

### AP-307 — Execution Graph Builder
- **Purpose.** Plan → executable topology.
- **Description.** Build the DAG (nodes→WPs, typed edges incl. approval/recovery,
  conditions, checkpoints, policies, state). Per AP-003 containment decision.
- **Dependencies.** AP-104, AP-306.
- **Inputs.** Plan; doc 18.
- **Outputs.** Execution Graph (persisted).
- **Acceptance Criteria.** Acyclic (explicit loops only); deterministic
  conditions; recovery edges present; resumable from graph state.
- **Risks.** Static graph vs future dynamic expansion.
- **Complexity.** High. **Effort.** L. **Priority.** P0.
- **Suggested Tests.** Cycle detection; edge-type coverage; resume-from-state.
- **Validation Strategy.** Contract test → Orchestration.

### AP-308 — Execution Strategy Generator
- **Purpose.** Attach declarative coordination behavior.
- **Description.** Produce the Execution Strategy (coordination/approval/retry/
  timeout/validation/recovery/checkpoint policies) for the Plan/graph; one
  strategy may cover many WPs.
- **Dependencies.** AP-106, AP-306, AP-304.
- **Inputs.** Plan; doc 13.
- **Outputs.** Execution Strategy.
- **Acceptance Criteria.** Runtime-agnostic; approval vocab matches Governance;
  policies consumable by Orchestration + Recovery.
- **Risks.** Planning/Strategy boundary blur.
- **Complexity.** Medium. **Effort.** M. **Priority.** P1.
- **Suggested Tests.** Runtime-agnosticism; policy completeness.
- **Validation Strategy.** Contract test → Orchestration + Recovery.

### AP-309 — Work Packaging
- **Purpose.** Assemble execution-ready Work Packages.
- **Description.** Compose WP from objective + embedded Context Package +
  constraints + resolved capabilities + selected skills + evidence + completion
  criteria; bind to graph nodes.
- **Dependencies.** AP-105, AP-303, AP-305, AP-307.
- **Inputs.** Plan/graph; Skills; Context.
- **Outputs.** Execution-ready Work Packages.
- **Acceptance Criteria.** Each WP self-contained; references valid; no raw
  operator request reaches a WP.
- **Risks.** Embedded Context Package bloat.
- **Complexity.** Medium. **Effort.** M. **Priority.** P0.
- **Suggested Tests.** Self-containment; WP→runtime contract.
- **Validation Strategy.** End-of-phase scenario: Goal → persisted graph of
  ready WPs.

---

# Phase 4 — Execution Coordination

### AP-401 — Orchestration Coordinator
- **Purpose.** Drive the graph: right WP, right time, right capability, right
  constraints.
- **Description.** Event-driven coordination; dependency/constraint/approval/
  resource gating; execution ordering; checkpoint coordination; replayable
  decisions; pause/resume/cancel control (the actuator for Supervision
  recommendations).
- **Dependencies.** AP-307, AP-308, AP-203, AP-201, AP-205.
- **Inputs.** Execution Graph; Execution Strategy; events; doc 07.
- **Outputs.** Execution Sessions; runtime assignments; checkpoints; events.
- **Acceptance Criteria.** No execution before all gates pass; every decision
  replayable from the log; pause/resume honored; exactly one owner of control.
- **Risks.** Overlap with Recovery/Supervision verbs (mitigated by AP-003/09).
- **Complexity.** Critical. **Effort.** XL. **Priority.** P0.
- **Suggested Tests.** Gate-enforcement; replay; dependency ordering.
- **Validation Strategy.** Multi-node graph runs to "waiting validation."

### AP-402 — Resource Allocation & Scheduling
- **Purpose.** Allocate resources to ready work.
- **Description.** Allocate/Reserve/Release/Reassign/Suspend/Restore; concurrency
  + availability/health from the single owning registry; Orchestration is sole
  allocator (Planning never allocates).
- **Dependencies.** AP-109, AP-401.
- **Inputs.** Doc 22.
- **Outputs.** Allocated resources.
- **Acceptance Criteria.** No execution if required resources unavailable; human
  resources modeled without unsafe scheduling assumptions.
- **Risks.** Human-as-resource nuances.
- **Complexity.** Medium. **Effort.** M. **Priority.** P1.
- **Suggested Tests.** Allocation gating; release-on-failure.
- **Validation Strategy.** Integrated with AP-401 gating.

### AP-403 — Runtime Harness Adapter SDK + First Adapter
- **Purpose.** Execute through the uniform Runtime Interface.
- **Description.** Runtime Harness category atop AP-207; the adapter SDK
  (accept WP, execute, report progress, emit events, generate artifacts, report
  failures, support cancel/recovery) + the first real adapter.
- **Dependencies.** AP-207, AP-109.
- **Inputs.** Docs 11, 15.
- **Outputs.** Runtime adapter SDK + one runtime (e.g. local shell / Nexus Agent).
- **Acceptance Criteria.** A WP executes through the adapter; events/artifacts/
  checkpoints emitted; cancellation + failure exposure work.
- **Risks.** Determinism principle vs LLM runtimes (document as "attempt").
- **Complexity.** High. **Effort.** L. **Priority.** P0.
- **Suggested Tests.** Adapter conformance; cancel + failure paths.
- **Validation Strategy.** Runs a WP end-to-end under Orchestration.

### AP-404 — Additional Runtime Adapters (Claude Code, Gemini, Human Operator)
- **Purpose.** Prove runtime independence across heterogeneous runtimes.
- **Description.** Implement ≥2 more adapters incl. a Human Operator harness
  (approval/manual-step as a runtime).
- **Dependencies.** AP-403.
- **Inputs.** Docs 11, 15.
- **Outputs.** Two+ more adapters.
- **Acceptance Criteria.** The same WP runs unmodified on multiple adapters;
  capability advertisement honored.
- **Risks.** Capability over-claiming (no trust model — flag).
- **Complexity.** High. **Effort.** L. **Priority.** P1.
- **Suggested Tests.** Same-WP-multi-runtime; capability-conformance.
- **Validation Strategy.** Runtime-independence scenario.

### AP-405 — Execution Layer
- **Purpose.** Perform assigned work; never self-validate.
- **Description.** Prepare runtime, perform WP, emit events/observations,
  produce artifacts + evidence candidates, create checkpoints; expose failure
  (reason/checkpoint/artifacts/state) without deciding recovery.
- **Dependencies.** AP-110, AP-403, AP-401.
- **Inputs.** WP; Runtime Assignment; doc 08.
- **Outputs.** Artifacts; evidence candidates; observations; checkpoints; events.
- **Acceptance Criteria.** Never declares own completion; emits evidence
  *candidates*; failure exposed not decided.
- **Risks.** Observation vs Execution Event naming (per AP-003).
- **Complexity.** High. **Effort.** L. **Priority.** P0.
- **Suggested Tests.** No-self-completion; failure-exposure contract.
- **Validation Strategy.** Output consumed by Supervision + Validation.

### AP-406 — Governance Enforcement Gate
- **Purpose.** Authority over autonomy at the execution boundary.
- **Description.** Policy-driven authorization (Allow/Deny/Require Approval/
  Delay/Escalate/Request Info), approval workflow (per AP-004 vocabulary),
  immutable audit; integrated into Orchestration gating.
- **Dependencies.** AP-205, AP-401, AP-004.
- **Inputs.** Docs 12, 20.
- **Outputs.** Authorization decisions; immutable audit records.
- **Acceptance Criteria.** Policy-violating action denied + audited;
  approval-required action blocks until approved; audit immutable.
- **Risks.** Approval stalls with no timeout (flag for Recovery).
- **Complexity.** High. **Effort.** L. **Priority.** P0.
- **Suggested Tests.** Deny path; approval gate; audit immutability.
- **Validation Strategy.** End-of-phase governance scenario.

---

# Phase 5 — Supervision, Validation & Recovery

### AP-501 — Supervision Engine
- **Purpose.** Continuous operational awareness.
- **Description.** Consume Execution/Runtime events + checkpoints + resource
  metrics; derive operational health (Healthy/Waiting/Paused/Degraded/Stalled/
  Failed/Completed) from health indicators; aggregate Observations; emit
  Intervention *Recommendations* (Orchestration acts), Alerts, Health
  Assessments. Never controls execution directly.
- **Dependencies.** AP-110, AP-201, AP-401.
- **Inputs.** Doc 09.
- **Outputs.** Observations; health assessments; intervention requests; alerts.
- **Acceptance Criteria.** Stalled/degraded detected from evidence; every
  intervention explainable; recommendations routed to Orchestration only.
- **Risks.** Health-derivation algorithm unspecified (define indicators →
  thresholds).
- **Complexity.** High. **Effort.** L. **Priority.** P0.
- **Suggested Tests.** Stall detection; recommend-not-control invariant.
- **Validation Strategy.** Drives Recovery + Orchestration in failure scenario.

### AP-502 — Validation Engine & Validator Dispatch
- **Purpose.** Evidence-based completion — never runtime confidence.
- **Description.** Evidence collection, policy evaluation, validator dispatch
  (Automated/Human/Hybrid), four-valued result (Passed/Failed/Partial/Requires
  Review), Validation Report; gate to Knowledge. Reconcile result vs state enum.
- **Dependencies.** AP-110, AP-112, AP-205, AP-405.
- **Inputs.** WP; evidence candidates; artifacts; validation policy; doc 14.
- **Outputs.** Validation Report; pass/fail/partial/review; verified evidence.
- **Acceptance Criteria.** Completion never from runtime self-report;
  insufficient evidence ⇒ not complete; human/hybrid validators supported.
- **Risks.** Determinism vs human validation (bounded).
- **Complexity.** High. **Effort.** L. **Priority.** P0.
- **Suggested Tests.** Evidence-insufficiency ⇒ not passed; validator dispatch.
- **Validation Strategy.** Only validated outcomes proceed to Knowledge.

### AP-503 — Recovery Engine
- **Purpose.** Continue work after failure; don't restart.
- **Description.** Failure classification (Runtime/Resource/Context/Governance/
  Validation/Dependency), deterministic strategy selection (Continue/Retry/
  Resume/Rollback/Checkpoint Restore/Switch Runtime/Request Context/Human Review/
  Abort), checkpoint restoration, bounded retry/failover, escalation, recovery
  audit/metrics. Reconcile pre-declared recovery edges vs runtime selection;
  never bypass Governance or override Validation.
- **Dependencies.** AP-204, AP-501, AP-401, AP-106.
- **Inputs.** Failure detections; checkpoints; recovery policy; doc 19.
- **Outputs.** Recovery decisions; restored state; escalations; metrics.
- **Acceptance Criteria.** Resume from latest valid checkpoint; retries bounded;
  validated evidence never discarded; escalation has a timeout.
- **Risks.** Non-rollbackable side effects (emails/external mutations).
- **Complexity.** Critical. **Effort.** XL. **Priority.** P0.
- **Suggested Tests.** Restore-and-resume; retry-bound; no-evidence-loss.
- **Validation Strategy.** Failure scenario recovers without restart or
  governance bypass.

---

# Phase 6 — Knowledge, Reflection & Operational Maturity

### AP-601 — Reflection Engine
- **Purpose.** Validated outcomes → actionable understanding.
- **Description.** Analyze validated outcomes (Success/Failure/Process/Strategy/
  Knowledge reflection), extract lessons/patterns/anti-patterns, generate
  Knowledge Candidates + confidence; never writes Knowledge directly; Planning
  never depends on Reflection directly.
- **Dependencies.** AP-502, AP-111, AP-201.
- **Inputs.** Validated artifacts; execution history; validation reports;
  recovery history; observations; doc 26.
- **Outputs.** Knowledge Candidates; recommendations; patterns; confidence.
- **Acceptance Criteria.** Only validated evidence analyzed; outputs are
  candidates (advisory); confidence laddered.
- **Risks.** Inferring lessons from unverified execution (forbidden — enforce).
- **Complexity.** High. **Effort.** L. **Priority.** P1.
- **Suggested Tests.** Reject-unvalidated-input; candidate-not-write invariant.
- **Validation Strategy.** Feeds Knowledge ingestion.

### AP-602 — Knowledge Graph Store & Ingestion
- **Purpose.** Persistent operational intelligence.
- **Description.** Operational knowledge graph (objects: Pattern/Decision/Lesson/
  Finding/Relationship/Strategy/…), confidence + freshness lifecycle (Current/
  Historical/Deprecated/Archived/Superseded), ingestion gated on validation;
  references (never copies) artifacts.
- **Dependencies.** AP-601, AP-206, AP-112.
- **Inputs.** Knowledge Candidates; doc 10.
- **Outputs.** Persisted, queryable knowledge graph.
- **Acceptance Criteria.** Only validated candidates persist; freshness/
  supersession enforced; references resolve.
- **Risks.** Stale knowledge poisoning planning; graph growth.
- **Complexity.** High. **Effort.** L. **Priority.** P1.
- **Suggested Tests.** Validation-gate; supersession; stale-exclusion.
- **Validation Strategy.** Retrieval feeds Context/Planning.

### AP-603 — Knowledge Retrieval into Context & Planning
- **Purpose.** Close the learning loop.
- **Description.** Retrieval answering "what understanding is relevant now?"
  consumed by Context Engineering + Planning; prefer current/higher-confidence
  knowledge.
- **Dependencies.** AP-602, AP-303, AP-306.
- **Inputs.** Knowledge graph; doc 10.
- **Outputs.** Relevant knowledge injected into context/planning.
- **Acceptance Criteria.** A second run of a goal class demonstrably reuses
  prior validated knowledge; deprecated knowledge excluded.
- **Risks.** Retrieval relevance/precision.
- **Complexity.** High. **Effort.** L. **Priority.** P1.
- **Suggested Tests.** Reuse measurement; freshness filtering.
- **Validation Strategy.** End-to-end learning scenario (the Phase 6 gate).

### AP-604 — Operational Maturity: Observability, Audit, Performance
- **Purpose.** Run continuously and safely.
- **Description.** End-to-end traces/metrics/dashboards across every layer;
  complete immutable audit; performance envelope + capacity; runbooks; backpressure.
- **Dependencies.** AP-201, AP-203, AP-406, AP-501.
- **Inputs.** Docs 09, 12, 23.
- **Outputs.** Observability stack; audit; performance baseline; runbooks.
- **Acceptance Criteria.** Every layer observable; every decision auditable;
  stated performance/recoverability targets met under load.
- **Risks.** Observability gaps for non-cooperative runtimes.
- **Complexity.** High. **Effort.** L. **Priority.** P2.
- **Suggested Tests.** Trace-coverage; load/soak; audit-completeness.
- **Validation Strategy.** Operational-readiness review.

---

## Coverage Note

This catalog covers the full 13-stage pipeline and all cross-cutting
infrastructure. APs are intentionally sized to be independently verifiable; a
small number (AP-306, AP-401, AP-503, AP-201) are XL/Critical and should be
split into sub-APs during phase planning. New APs append within their phase's
number range; superseded APs are marked deprecated, never renumbered.
