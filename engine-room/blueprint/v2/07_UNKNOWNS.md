# Nexus v2 — Open Unknowns

Status: Engineering Plan
References: `01_PHASES.md`, `02_ACTION_POINTS.md`, `03_DEPENDENCY_GRAPH.md`,
`04_IMPLEMENTATION_ORDER.md`

---

## How to Read This Catalog

This document enumerates the **decision points the target architecture
intentionally leaves open**. Each entry is a question, not an answer. The
architecture documents in `docs/v2/` either explicitly defer these items
("implementation-specific", "where feasible", "Future Evolution") or name a
responsibility without specifying its mechanism.

An **Unknown** differs from an **ADR**. An ADR is a decision that will be made
and recorded; an Unknown is the open space that precedes (and may be closed by)
that decision. Where a planned ADR closes an Unknown, the entry cross-references
it. The ADR identifiers ADR-001…ADR-004 are defined inline in the Phase 0
Action Points (`AP-001`…`AP-004`); a standalone `09_ADR_BACKLOG.md` is not yet
present in `blueprint/v2/`.

This catalog does **not** propose solutions. It records: the open decision,
where it surfaces, what depends on it, when it must be resolved, and the closing
ADR if one exists.

**Field set per Unknown.** ID · Question · Where it surfaces (doc #) · Depends
on it (AP / layer blocked) · Must-resolve-by · Closing ADR.

**Must-resolve-by scale.** A phase/AP identifier means the unknown blocks that
unit of work and cannot be carried past it. "Deferrable past v2 core" means the
v2 critical path (`AP-001 → … → AP-603`) can complete with a provisional answer
or without the item.

---

## 1. Persistence & Storage

The infrastructure documents (23, 24, 25, 17, 10) repeatedly state that the
architecture must not depend on a storage technology. The technology choices
are therefore open; the *contract* they must satisfy is fixed by ADR-001.

### U-01 — Source-of-truth persistence model
- **Question.** Is operational state event-sourced (derived from the event
  log), independently stored, or hybrid (stored state + event log + checkpoints
  as materialized snapshots)? Which store is authoritative for "where is this
  execution now"?
- **Where.** Docs 23 (Event), 24 (State — silent on event-sourcing), 25
  (Checkpoint).
- **Depends on it.** AP-101, AP-112, AP-201, AP-203, AP-204 (the deepest root in
  the dependency graph). All of Phase 2 substrate.
- **Must-resolve-by.** AP-001 (Phase 0). Hard blocker — must not enter Phase 1.
- **Closing ADR.** **ADR-001** (AP-001).

### U-02 — Message bus / event store technology
- **Question.** What concrete transport and durable store back the event bus and
  event store?
- **Where.** Doc 23 (explicitly defers).
- **Depends on it.** AP-201, AP-202; transitively every event-driven layer.
- **Must-resolve-by.** AP-201 (Phase 2). The *contract* (ordering, replay, DLQ,
  schema versioning) is fixed earlier; the technology selection is an AP-201
  implementation decision.
- **Closing ADR.** None (constrained by ADR-001; technology choice deferred to
  AP-201).

### U-03 — State store technology
- **Question.** What backs the state machine's persistence, given the U-01
  model?
- **Where.** Doc 24.
- **Depends on it.** AP-203.
- **Must-resolve-by.** AP-203 (Phase 2).
- **Closing ADR.** Governed by ADR-001; store choice deferred to AP-203.

### U-04 — Checkpoint storage backend
- **Question.** Filesystem, database, object store, or distributed store for
  checkpoints? Are checkpoints derived from the event log or independent?
- **Where.** Doc 25 (explicitly open).
- **Depends on it.** AP-204; Recovery (AP-503) restoration path.
- **Must-resolve-by.** AP-204 (Phase 2). The derived-vs-independent relationship
  is fixed by ADR-001; the backend is an AP-204 decision.
- **Closing ADR.** Relationship to event log: **ADR-001** (AP-001). Backend:
  none (AP-204).

### U-05 — Knowledge graph storage
- **Question.** What store backs the operational knowledge graph?
- **Where.** Doc 10.
- **Depends on it.** AP-602; AP-603 retrieval.
- **Must-resolve-by.** AP-602 (Phase 6). Deferrable past v2-core entry; required
  before the learning loop closes.
- **Closing ADR.** None.

### U-06 — Artifact storage backend
- **Question.** Filesystem, Git, object store, database, or document store for
  immutable artifacts?
- **Where.** Doc 17 (open).
- **Depends on it.** AP-206; AP-111 lineage; Validation/Knowledge reference
  resolution.
- **Must-resolve-by.** AP-206 (Phase 2). Behind the storage-backend abstraction
  named in AP-206.
- **Closing ADR.** None.

### U-07 — Context Package persistence
- **Question.** Is the Context Package persisted independently, embedded only in
  Work Packages, or both? No persistence is stated.
- **Where.** Doc 03 (none stated).
- **Depends on it.** AP-103 (schema embeddability), AP-303 (production), AP-309
  (embedding in WP).
- **Must-resolve-by.** AP-103 (Phase 1) for the embeddability decision; the
  standalone-persistence question is deferrable past v2 core.
- **Closing ADR.** None.

### U-08 — Registry storage (Policy · Capability · Resource · Harness)
- **Question.** What backs the policy, capability, resource, and harness
  registries? No backend specified.
- **Where.** Docs 20, 21, 22, 11.
- **Depends on it.** AP-205 (policy registry), AP-207 (harness registry), AP-304
  (capability/resource lookup).
- **Must-resolve-by.** AP-205 / AP-207 (Phase 2). Field ownership is fixed by
  ADR-002; storage is per-AP.
- **Closing ADR.** Field ownership: **ADR-002** (AP-002). Storage: none.

---

## 2. Serialization & Transport

### U-09 — Object serialization / wire format
- **Question.** What is the single serialization format and wire encoding for
  all architectural objects? None is specified anywhere.
- **Where.** Not specified in any doc; named as a deliverable of AP-101.
- **Depends on it.** AP-101 gates all of Phase 1; every object schema and every
  contract test.
- **Must-resolve-by.** AP-101 (Phase 1). Hard blocker for the object model.
- **Closing ADR.** Choice is constrained by ADR-001 (per AP-101 description); the
  format decision itself is made in AP-101, not a separate ADR.

### U-10 — Event payload schema format & schema registry
- **Question.** What schema format governs event payloads, and what mechanism is
  the schema registry for payload versioning/compatibility?
- **Where.** Doc 23.
- **Depends on it.** AP-112 (Event schema), AP-201 (schema-versioned payloads).
- **Must-resolve-by.** AP-201 (Phase 2); the object-level Event schema is fixed
  at AP-112.
- **Closing ADR.** None (downstream of the AP-101 serialization decision).

---

## 3. Delivery & Consistency

### U-11 — Exactly-once feasibility
- **Question.** Where is exactly-once delivery feasible, and where does the
  platform settle for at-least-once + idempotency? The architecture says "where
  feasible" without delimiting it.
- **Where.** Doc 23.
- **Depends on it.** AP-201, AP-202; correctness assumptions in AP-203 and
  AP-401.
- **Must-resolve-by.** AP-202 (Phase 2).
- **Closing ADR.** None.

### U-12 — Event ordering mechanism
- **Question.** Is ordering guaranteed per-correlation only, or globally? The
  substrate commits to "causal within an execution" but the mechanism is open.
- **Where.** Doc 23; AP-201 (ordering: causal within an execution).
- **Depends on it.** AP-201; replay determinism; AP-401 replayable decisions.
- **Must-resolve-by.** AP-201 (Phase 2).
- **Closing ADR.** None.

### U-13 — Idempotency key strategy
- **Question.** How are idempotency keys derived and propagated so all consumers
  dedupe uniformly? The architecture requires consumer idempotency but specifies
  no mechanism.
- **Where.** Doc 23; AP-202.
- **Depends on it.** AP-202; every event consumer (State, Orchestration).
- **Must-resolve-by.** AP-202 (Phase 2). Hard blocker for safe at-least-once.
- **Closing ADR.** None (an AP-202 deliverable).

---

## 4. Core Algorithms

These are named as layer responsibilities but undefined. Several AP entries flag
them explicitly (e.g. AP-303, AP-306, AP-501) and direct a heuristic start.

### U-14 — Context discovery / selection / ranking / dedup
- **Question.** By what algorithm does Context Engineering discover, select,
  rank, and deduplicate context?
- **Where.** Doc 03.
- **Depends on it.** AP-303; quality of every downstream Plan.
- **Must-resolve-by.** AP-303 (Phase 3). A provisional algorithm unblocks the
  phase; refinement is deferrable.
- **Closing ADR.** None.

### U-15 — "Minimal complete context" sufficiency metric
- **Question.** What metric decides that a Context Package is sufficient/complete
  enough to certify? No sufficiency metric exists (flagged in AP-303).
- **Where.** Doc 03.
- **Depends on it.** AP-303 validation-status determination; Planning's refusal
  gate (AP-306).
- **Must-resolve-by.** AP-303 (Phase 3) needs an operational proxy; a principled
  metric is deferrable past v2 core.
- **Closing ADR.** None.

### U-16 — Goal-decomposition algorithm
- **Question.** By what method does Planning decompose a Goal into Work
  Packages?
- **Where.** Doc 04.
- **Depends on it.** AP-306 (XL/Critical, on the critical path).
- **Must-resolve-by.** AP-306 (Phase 3). Heuristic start sanctioned by AP-306;
  refinement deferrable.
- **Closing ADR.** None.

### U-17 — Complexity / cost / duration estimation methodology & cost units
- **Question.** What methodology estimates complexity, cost, and duration, and in
  what units is cost expressed? Unspecified (flagged in AP-306).
- **Where.** Doc 04.
- **Depends on it.** AP-306; Execution Strategy generation (AP-308).
- **Must-resolve-by.** AP-306 (Phase 3) with a heuristic; a calibrated
  methodology is deferrable past v2 core.
- **Closing ADR.** None.

### U-18 — Capability resolution algorithm
- **Question.** How does a required capability resolve to a candidate provider
  set?
- **Where.** Doc 21.
- **Depends on it.** AP-304; Skill selection (AP-305); Orchestration assignment.
- **Must-resolve-by.** AP-304 (Phase 3). Field ownership governed by ADR-002.
- **Closing ADR.** Field ownership: **ADR-002** (AP-002). Algorithm: none.

### U-19 — Runtime selection / assignment algorithm
- **Question.** Given candidate providers, how does Orchestration select and
  assign a runtime? Resolution produces candidates (AP-304); selection is
  Orchestration's, but the selection function is undefined.
- **Where.** Docs 07, 22.
- **Depends on it.** AP-401 (Critical, on the critical path); AP-402.
- **Must-resolve-by.** AP-401 (Phase 4).
- **Closing ADR.** None.

### U-20 — Skill version-compatibility resolution rule
- **Question.** What rule resolves skill version compatibility during selection
  and composition? AP-107 carries the field but defers the rule to Phase 3.
- **Where.** Doc 06.
- **Depends on it.** AP-305 (composition + version conflicts).
- **Must-resolve-by.** AP-305 (Phase 3).
- **Closing ADR.** None.

### U-21 — Policy condition / constraint expression language
- **Question.** Is the policy condition/constraint mechanism data-driven rules or
  an embedded DSL?
- **Where.** Docs 12, 13, 20.
- **Depends on it.** AP-205 (Policy Engine); Execution Graph conditions; AP-406.
- **Must-resolve-by.** AP-004 (Phase 0) — chosen before the Policy Engine is
  built. Hard blocker for AP-205.
- **Closing ADR.** **ADR-004** (AP-004).

### U-22 — "Specificity" computation for conflict resolution
- **Question.** How is "Specificity" computed in the deterministic conflict-
  resolution order (Specificity → Priority → Version → Default)?
- **Where.** Doc 20; AP-004, AP-205.
- **Depends on it.** AP-205 determinism guarantee; AP-406 governance decisions.
- **Must-resolve-by.** AP-004 (Phase 0) — a defined, testable rule is an AP-004
  acceptance criterion.
- **Closing ADR.** **ADR-004** (AP-004).

### U-23 — Execution Graph condition expression language
- **Question.** What language expresses conditional edges and node conditions in
  the Execution Graph? Must yield deterministic evaluation.
- **Where.** Doc 18; AP-104, AP-307.
- **Depends on it.** AP-104 (schema), AP-307 (builder), AP-401 (evaluation).
- **Must-resolve-by.** AP-104 (Phase 1) for the schema; likely shares the AP-004
  policy-language decision.
- **Closing ADR.** Potentially **ADR-004** (AP-004) if unified with policy
  conditions; otherwise none.

### U-24 — Iterative-loop termination semantics
- **Question.** What governs termination of explicit loops in the Execution
  Graph (the only permitted cycles)?
- **Where.** Doc 18.
- **Depends on it.** AP-307 (acyclic-except-explicit-loops); AP-401 execution.
- **Must-resolve-by.** AP-307 (Phase 3).
- **Closing ADR.** None.

### U-25 — Supervision health-derivation function
- **Question.** How do event patterns / health indicators map to health states
  (Healthy/Waiting/Paused/Degraded/Stalled/Failed/Completed)? What thresholds?
  Unspecified (flagged in AP-501).
- **Where.** Doc 09.
- **Depends on it.** AP-501; AP-503 (failure detection → recovery); AP-604.
- **Must-resolve-by.** AP-501 (Phase 5).
- **Closing ADR.** None.

### U-26 — Knowledge retrieval algorithm
- **Question.** Is retrieval semantic, graph-traversal, keyword, or a
  combination?
- **Where.** Doc 10.
- **Depends on it.** AP-603 (closes the learning loop); usefulness of feedback
  into AP-303/AP-306.
- **Must-resolve-by.** AP-603 (Phase 6).
- **Closing ADR.** None.

### U-27 — Recovery failure-category → strategy mapping
- **Question.** What deterministic function maps a failure category
  (Runtime/Resource/Context/Governance/Validation/Dependency) to a recovery
  strategy (Continue/Retry/Resume/Rollback/Checkpoint Restore/Switch Runtime/
  Request Context/Human Review/Abort)? How are pre-declared recovery edges
  reconciled with runtime selection?
- **Where.** Doc 19.
- **Depends on it.** AP-503 (Critical, on the critical path).
- **Must-resolve-by.** AP-503 (Phase 5). Pre-declared-vs-runtime reconciliation
  is an AP-503 acceptance item.
- **Closing ADR.** None.

### U-28 — Retry / backoff parameters & escalation timeout
- **Question.** What concrete retry counts, backoff schedule, and escalation
  timeout bound recovery? "Bounded" is asserted without values.
- **Where.** Doc 19; AP-503, AP-406 (approval-stall timeout flagged).
- **Depends on it.** AP-503; AP-406 governance approval stalls.
- **Must-resolve-by.** AP-503 (Phase 5). Values are configurable via Execution
  Strategy (AP-106) — defaults are an AP-503 decision.
- **Closing ADR.** None.

---

## 5. Scoring & Confidence

All confidence/scoring schemes are deferred to "Future Evolution"; the objects
carry a Confidence field with no defined scale.

### U-29 — Confidence scale & scoring rule (cross-object)
- **Question.** What scale and scoring rule govern the Confidence field shared by
  Context Package, Validation Report, Knowledge Entry, and Reflection? No scale
  is defined.
- **Where.** Docs 03, 14, 10, 26.
- **Depends on it.** AP-103, AP-112 (Validation Report / Knowledge Entry),
  AP-303, AP-502, AP-601, AP-602.
- **Must-resolve-by.** Per-object schemas (AP-103/AP-112, Phase 1) must reserve
  the field; a shared, calibrated scoring rule is **deferrable past v2 core**.
- **Closing ADR.** None.

### U-30 — Confidence ladder scoring rule (Knowledge / Reflection)
- **Question.** What rule places an entry on the shared ladder
  (Experimental/Observed/Validated/Proven)? The ladder exists; the scoring rule
  does not.
- **Where.** Docs 10, 26.
- **Depends on it.** AP-601 (confidence laddering), AP-602 (ingestion gating),
  AP-603 (prefer higher-confidence).
- **Must-resolve-by.** AP-601 (Phase 6).
- **Closing ADR.** None.

---

## 6. Identity, Security & Trust

### U-31 — Operator identity & authentication
- **Question.** How is the operator identified and authenticated?
- **Where.** Doc 16 (Intent Resolution); doc 12 (Governance).
- **Depends on it.** AP-301 (request attribution); AP-406 (approval routing);
  AP-604 audit attribution.
- **Must-resolve-by.** AP-406 (Phase 4) for governance attribution; a minimal
  identity is needed at AP-301 (Phase 3).
- **Closing ADR.** None.

### U-32 — Approval routing & transport
- **Question.** How are approval requests routed to and returned from approvers
  (transport, addressing)?
- **Where.** Docs 12, 13.
- **Depends on it.** AP-406 (approval workflow); Human Operator harness (AP-404);
  AP-503 escalation.
- **Must-resolve-by.** AP-406 (Phase 4).
- **Closing ADR.** Approval *vocabulary* unified by **ADR-004** (AP-004);
  routing/transport: none.

### U-33 — Access / permission model for external context sources
- **Question.** What authorization model governs read access to external sources
  (Email, Slack, Drive, repositories)?
- **Where.** Doc 03; doc 11 (Harness authentication).
- **Depends on it.** AP-302 (Context Harnesses, auth-denied path), AP-303.
- **Must-resolve-by.** AP-302 (Phase 3).
- **Closing ADR.** None.

### U-34 — Runtime authentication model
- **Question.** How does the platform authenticate to runtimes, and runtimes to
  the platform, through the Harness boundary?
- **Where.** Doc 11 (Harness Authentication field), doc 15.
- **Depends on it.** AP-207 (Harness SDK), AP-403/AP-404 (runtime adapters).
- **Must-resolve-by.** AP-207 (Phase 2) for the contract; per-adapter at
  AP-403/404.
- **Closing ADR.** None.

### U-35 — Capability / runtime trust & verification
- **Question.** How are self-reported capabilities verified? Today they are
  self-reported with no verification (flagged in AP-404 as capability
  over-claiming).
- **Where.** Docs 11, 15, 21.
- **Depends on it.** AP-404 (multiple adapters), AP-304 (resolution trusts
  advertisements).
- **Must-resolve-by.** **Deferrable past v2 core** — AP-404 documents the gap;
  no trust model is required to close the v2 critical path.
- **Closing ADR.** None.

---

## 7. Governance & Policy

### U-36 — Risk-level computation
- **Question.** How is a risk level (Low/Medium/High) computed to drive approval
  tiers?
- **Where.** Docs 12, 20.
- **Depends on it.** AP-406 (which actions require approval); AP-308 (strategy
  approval policy).
- **Must-resolve-by.** AP-406 (Phase 4).
- **Closing ADR.** Approval vocabulary: **ADR-004** (AP-004); the risk-scoring
  function: none.

### U-37 — Audit store & tamper-evidence mechanism
- **Question.** What backs the immutable audit log, and what makes it
  tamper-evident? "Immutable audit" is asserted; the mechanism is open.
- **Where.** Doc 12; AP-406, AP-604.
- **Depends on it.** AP-406 (immutable audit records), AP-604 (audit
  completeness).
- **Must-resolve-by.** AP-406 (Phase 4) for the write path; tamper-evidence
  hardening can extend into AP-604 (Phase 6).
- **Closing ADR.** None.

---

## 8. Deferred Scope (Future Evolution)

Items the architecture explicitly assigns to "Future Evolution." None is on the
v2 critical path; all are **deferrable past v2 core** by definition. Listed so
the v2 schemas and interfaces do not foreclose them.

### U-38 — Advanced Skill models
- **Question.** Will nested, parameterized, hierarchical, learned, or
  marketplace Skills be supported, and do the v2 Skill schema/registry leave room
  for them?
- **Where.** Doc 06.
- **Depends on it.** AP-107 schema extensibility; AP-305.
- **Must-resolve-by.** Deferrable past v2 core; AP-107 should not foreclose.
- **Closing ADR.** None.

### U-39 — Advanced execution models
- **Question.** Distributed, collaborative, or streaming execution — supported in
  v2 or deferred?
- **Where.** Docs 07, 08, 15.
- **Depends on it.** AP-401, AP-405 (v2 assumes non-distributed execution).
- **Must-resolve-by.** Deferrable past v2 core.
- **Closing ADR.** None.

### U-40 — Adaptive / predictive planning
- **Question.** Will Planning become adaptive or predictive (vs. static
  upfront)?
- **Where.** Doc 04; doc 18 (static graph vs. dynamic expansion, flagged in
  AP-307).
- **Depends on it.** AP-306, AP-307 (static graph assumption).
- **Must-resolve-by.** Deferrable past v2 core.
- **Closing ADR.** None.

### U-41 — Distributed orchestration
- **Question.** Will orchestration be distributed across nodes?
- **Where.** Doc 07.
- **Depends on it.** AP-401 (single-coordinator assumption).
- **Must-resolve-by.** Deferrable past v2 core.
- **Closing ADR.** None.

### U-42 — Org-wide registries
- **Question.** Will Capability/Resource/Skill/Policy registries become org-wide
  / shared rather than instance-local?
- **Where.** Docs 20, 21, 22, 06.
- **Depends on it.** AP-205, AP-207, AP-304 (registry scope).
- **Must-resolve-by.** Deferrable past v2 core.
- **Closing ADR.** None.

### U-43 — Semantic operational graphs
- **Question.** Will the knowledge/operational graph gain semantic-graph
  capabilities beyond v2?
- **Where.** Doc 10.
- **Depends on it.** AP-602, AP-603 (graph model).
- **Must-resolve-by.** Deferrable past v2 core.
- **Closing ADR.** None.

### U-44 — Rollback applicability per domain
- **Question.** In which domains is rollback applicable, given non-rollbackable
  side effects (emails, external mutations — flagged in AP-503)?
- **Where.** Doc 19.
- **Depends on it.** AP-503 (Rollback / Checkpoint Restore strategies).
- **Must-resolve-by.** AP-503 (Phase 5) must bound rollback to where it is safe;
  full per-domain treatment is deferrable past v2 core.
- **Closing ADR.** None.

---

## 9. Program / Migration

### U-45 — Relationship to Nexus v1 (incremental vs. greenfield)
- **Question.** Is v2 an incremental evolution of Nexus v1 or a greenfield
  rebuild? Determines whether v1 data, integrations, and operators migrate.
- **Where.** Program-level; not addressed in `docs/v2/` or `blueprint/v2/`.
- **Depends on it.** AP-005 (repo/scaffold layout), and the migration scope of
  every layer that has a v1 counterpart.
- **Must-resolve-by.** AP-005 (Phase 0) for repo strategy; a full migration plan
  is a program decision that can run alongside the build.
- **Closing ADR.** None (program-level; no AP-bound ADR exists).

---

## 10. Critical-Path Impact Summary

The global critical path is `AP-001 → AP-101 → AP-105 → AP-201 → AP-203 →
AP-303 → AP-306 → AP-307 → AP-401 → AP-405 → AP-502 → AP-503 → AP-601 → AP-602 →
AP-603`. An unknown **blocks the critical path** when its resolving AP sits on
that chain and no provisional answer is sanctioned.

| Unknowns that BLOCK the critical path | Resolving AP (on path) | Closing ADR |
|---------------------------------------|------------------------|-------------|
| U-01 Persistence model | AP-001 | ADR-001 |
| U-09 Object serialization format | AP-101 | (in AP-101) |
| U-02 Message bus / event store tech | AP-201 | — |
| U-10 Event payload schema / registry | AP-201 | — |
| U-11 Exactly-once feasibility | AP-202→AP-201 | — |
| U-12 Event ordering mechanism | AP-201 | — |
| U-13 Idempotency key strategy | AP-202 | — |
| U-03 State store technology | AP-203 | (ADR-001) |
| U-23 Execution Graph condition language | AP-104 / AP-307 | ADR-004 (maybe) |
| U-24 Iterative-loop termination | AP-307 | — |
| U-19 Runtime selection algorithm | AP-401 | — |
| U-27 Recovery category→strategy map | AP-503 | — |
| U-26 Knowledge retrieval algorithm | AP-603 | — |

> U-14/U-15 (context), U-16/U-17 (planning), U-28 (retry params), U-25
> (health derivation) sit on or beside the critical path but are explicitly
> sanctioned to start heuristic (AP-303, AP-306, AP-501, AP-503). They gate
> *quality*, not the *existence* of the deliverable, and so are listed below as
> deferrable in their principled form.

| Unknowns safely deferrable (provisional or off critical path) | Earliest needed | Closing ADR |
|---------------------------------------------------------------|-----------------|-------------|
| U-04 Checkpoint backend | AP-204 | (ADR-001 / —) |
| U-05 Knowledge graph storage | AP-602 | — |
| U-06 Artifact storage backend | AP-206 | — |
| U-07 Context Package persistence | AP-103 | — |
| U-08 Registry storage | AP-205 / AP-207 | (ADR-002 / —) |
| U-14 Context discovery/ranking (provisional) | AP-303 | — |
| U-15 Context sufficiency metric (provisional) | AP-303 | — |
| U-16 Goal-decomposition (heuristic start) | AP-306 | — |
| U-17 Estimation methodology (heuristic start) | AP-306 | — |
| U-18 Capability resolution algorithm | AP-304 | ADR-002 (ownership) |
| U-20 Skill version-compatibility rule | AP-305 | — |
| U-21 Policy condition language | AP-004 | ADR-004 |
| U-22 Specificity computation | AP-004 | ADR-004 |
| U-25 Health-derivation (provisional) | AP-501 | — |
| U-28 Retry/backoff/escalation params | AP-503 | — |
| U-29 Cross-object confidence scale | AP-103/AP-112 | — |
| U-30 Confidence ladder scoring rule | AP-601 | — |
| U-31 Operator identity & auth | AP-301 / AP-406 | — |
| U-32 Approval routing & transport | AP-406 | ADR-004 (vocab) |
| U-33 External-source access model | AP-302 | — |
| U-34 Runtime authentication model | AP-207 | — |
| U-35 Capability/runtime trust & verification | (deferred, AP-404 flags) | — |
| U-36 Risk-level computation | AP-406 | ADR-004 (vocab) |
| U-37 Audit store & tamper-evidence | AP-406 / AP-604 | — |
| U-38…U-44 Future-Evolution scope | deferred | — |
| U-45 v1↔v2 migration | AP-005 (program) | — |

> Note: U-21 and U-22 close at AP-004 in Phase 0 and so are resolved before the
> critical path reaches the Policy Engine; they are listed as "deferrable" only
> in the sense that they do not block Phase 0 *entry*. AP-004 is a P0 gate.
