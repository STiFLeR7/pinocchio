# Nexus v2 — Implementation Phases

Status: Engineering Plan
Scope: Translates the target architecture in `docs/v2/` into ordered engineering phases.

---

## Purpose

This document defines the **engineering phases** for implementing Nexus v2.

Phases are not release versions. They are units of architectural progress. Each
phase produces executable software, validated contracts, and a measurable
capability increment. A phase is complete only when its **validation gate**
passes.

The phase order follows the platform's one-way dependency flow: lower layers
(objects, infrastructure) are built before the layers that depend on them, and
the operational pipeline is built understanding-first, execution-second,
learning-last.

---

## Phase Map

```
Phase 0  Foundation & Architectural Decisions
   │       resolve gaps, ratify ADRs, scaffold, decide persistence model
   ▼
Phase 1  Core Object Model & Contracts
   │       one canonical schema per architectural object; contract tests
   ▼
Phase 2  Infrastructure Substrate
   │       Event, State, Checkpoint, Policy, Artifact — the cross-cutting spine
   ▼
Phase 3  Understanding Pipeline (Intent → Context → Plan → Strategy)
   │       turn a Goal into an Execution Graph; no execution yet
   ▼
Phase 4  Execution Coordination
   │       Orchestration, Runtime/Harness, Resources, Execution, Governance gate
   ▼
Phase 5  Supervision, Validation & Recovery
   │       close the loop: observe, verify by evidence, recover from failure
   ▼
Phase 6  Knowledge, Reflection & Operational Maturity
           learn from outcomes; feed knowledge back into planning
```

Each phase depends only on phases above it. No phase introduces a circular
dependency on a later phase. Cross-cutting infrastructure (Phase 2) is built
before the pipeline (Phases 3–6) consumes it.

---

## Phase 0 — Foundation & Architectural Decisions

**Objective.** Remove the architectural ambiguity that currently blocks
implementation. Resolve the empty/duplicated specifications, ratify the
decisions that every later phase depends on, and stand up the engineering
substrate (repo layout, CI, contract-test harness).

**Why first.** Three core specifications are missing or wrong (`09_SUPERVISION`
empty, `11_HARNESS` a duplicate of Knowledge, Reflection absent). The single
most consequential architectural decision — the persistence/event-sourcing
model — is deferred in every infrastructure document. Building objects or
infrastructure before these are settled guarantees rework.

**Scope.**
- Author the three missing specifications (Supervision, Harness, Reflection).
- Ratify foundational ADRs (see `09_ADR_BACKLOG.md`), above all the
  persistence model (event-sourced vs. stored-state vs. hybrid) that unifies
  Event, State, and Checkpoint.
- Reconcile naming and ownership contradictions (Intent Resolution vs.
  Executive Intelligence; single Work Package schema; Execution Graph
  containment; Observation ownership).
- Stand up the monorepo/package layout, CI, linting, typing, and a
  **contract-test harness** that later phases extend.
- Produce a canonical glossary and fix the stale `docs/v2/README.md` index.

**Prerequisites.** None.

**Deliverables.**
- `docs/v2/09_SUPERVISION.md`, `docs/v2/11_HARNESS.md` (rewritten), and a
  Reflection specification — all non-empty and reconciled with their consumers.
- Ratified ADR set (decisions recorded, not merely proposed).
- Project scaffold: package boundaries, CI pipeline, test harness, schema
  validation tooling.
- Canonical glossary; corrected architecture index.

**Validation gate.** Architecture review confirms: no empty/duplicate specs
remain; every cross-cutting persistence decision is recorded as an accepted
ADR; CI runs green on an empty skeleton; the contract-test harness can load and
assert against a schema fixture.

---

## Phase 1 — Core Object Model & Contracts

**Objective.** Define exactly one authoritative, runtime-independent schema for
every architectural object in `02_OBJECT_MODEL.md` (and the model docs 15, 17,
18, 21, 22, 23, 24, 25), with contract tests. No behavior — data contracts only.

**Why second.** Every subsystem in Nexus "must consume and produce these
objects" (Architecture, Object Model). The objects are the shared language; if
they drift, the pipeline cannot integrate. Three documents define `Work
Package` differently — this phase collapses that into one schema.

**Scope.**
- One schema per object: Goal, Context Package, Plan, Work Package, Execution
  Graph, Execution Strategy, Skill, Capability, Resource, Constraint, Execution
  Session, Observation, Evidence, Artifact, Checkpoint, Event, Policy,
  Validation Report, Reflection, Knowledge Entry.
- Object relationships and lineage (`Goal → … → Artifact → Knowledge`).
- A single serialization format and versioning convention for all objects.
- Contract tests asserting producer/consumer compatibility for each seam.

**Prerequisites.** Phase 0 (the WP-schema and Observation-ownership decisions,
the persistence/serialization decision).

**Deliverables.** A versioned object-contract package; a schema registry;
contract-test suites that fail when a producer or consumer drifts from a schema.

**Validation gate.** Every object has one schema and a round-trip
serialization test. Every documented seam (e.g., Context Engineering →
Planning, Planning → Orchestration, Execution → Validation) has a passing
contract test built from real schema fixtures.

---

## Phase 2 — Infrastructure Substrate

**Objective.** Build the cross-cutting infrastructure the pipeline rides on:
Event Model, State Model, Checkpoint Model, Policy Engine, Artifact Model.

**Why third.** Orchestration is event-driven; State transitions emit events;
Recovery restores from checkpoints; Governance and several layers call the
Policy Engine; Execution emits artifacts. None of the pipeline layers can be
correctly built until this substrate exists and honors the Phase 0 persistence
decision.

**Scope.**
- **Event Model:** event bus, event store, delivery guarantees (at-least-once +
  idempotency keys), correlation/trace identifiers, dead-letter handling,
  replay, schema versioning.
- **State Model:** the unified state machine, transition guards, illegal-
  transition rejection, exactly-one-event-per-transition, state persistence
  consistent with the persistence ADR.
- **Checkpoint Model:** reference-not-copy snapshots, checkpoint store,
  pre-restore validation (integrity, artifact availability, policy
  compatibility), versioning/parent linkage.
- **Policy Engine:** declarative policy evaluation runtime, condition language,
  deterministic conflict resolution, policy registry, versioned evaluation
  records, simulation.
- **Artifact Model:** immutable-by-default artifact store, lineage, versioning,
  reference resolution.

**Prerequisites.** Phase 1 (Event, Policy, Checkpoint, Artifact, State are all
defined objects).

**Deliverables.** Running event bus + store; state-machine engine; checkpoint
store; policy evaluation service; artifact store. Each observable and replayable.

**Validation gate.** A synthetic object can be driven through its state machine,
emitting exactly one replayable event per transition; a checkpoint can be
written and restored with reference validation; a policy can be registered,
versioned, evaluated deterministically, and simulated; an artifact can be
produced, versioned, and referenced without duplication. Idempotency under
duplicate event delivery is proven by test.

---

## Phase 3 — Understanding Pipeline (Intent → Context → Plan → Strategy)

**Objective.** Implement the "understand work before executing it" half of the
platform. Given an operator request, produce a normalized Goal, a validated
Context Package, a Plan, an Execution Graph, an Execution Strategy, selected
Skills, resolved required Capabilities, and Work Packages — **without executing
anything.**

**Why fourth.** This is the platform's differentiator and it has no dependency
on runtimes or execution. It can be built and validated entirely on the object
model and infrastructure substrate. Its output (an Execution Graph of Work
Packages) is the precondition for Phase 4.

**Scope.**
- **Intent Resolution:** request → normalized Goal + metadata (domain,
  priority, confidence, clarifications).
- **Context Engineering:** discover → collect → validate → enrich → organize →
  package; a context-source connector framework (read-only first).
- **Planning Engine:** goal analysis, decomposition into Work Packages,
  dependency analysis, Execution Graph construction.
- **Execution Strategy generation:** coordination/approval/retry/timeout/
  validation/recovery/checkpoint policies (declarative, runtime-agnostic).
- **Capability Model:** capability registry + capability resolution.
- **Skill System:** skill registry, selection, composition.
- **Work Packaging:** assemble execution-ready Work Packages.

**Prerequisites.** Phases 1–2.

**Deliverables.** A pipeline that converts a Goal into a persisted Execution
Graph of Work Packages with an attached Execution Strategy and resolved
capabilities/skills. Fully observable; no runtime invoked.

**Validation gate.** For a representative goal set spanning multiple domains,
the pipeline produces a valid, acyclic Execution Graph whose nodes reference
well-formed Work Packages, each with required capabilities, skills, constraints,
validation requirements, and completion criteria. Planning refuses to proceed on
an invalid Context Package. Every decision is explainable (rationale persisted).

---

## Phase 4 — Execution Coordination

**Objective.** Execute Work Packages. Implement Orchestration, the Runtime
Model + Harness (adapters), the Resource Model, the Execution layer, and the
Governance enforcement gate.

**Why fifth.** Execution is "the smallest and most replaceable" layer and is
deliberately built after the understanding pipeline. It consumes the Execution
Graph from Phase 3 and the substrate from Phase 2.

**Scope.**
- **Orchestration:** dependency/constraint/approval/resource gating, runtime
  assignment, execution-session management, event-driven coordination,
  checkpoint coordination, replayable decisions.
- **Runtime Model + Harness:** the uniform Runtime Interface, the adapter SDK,
  and the first adapters (Claude Code, Gemini CLI, Nexus Agent, Human Operator).
- **Resource Model:** registration, allocation/scheduling, availability/health
  (reconciled with the State Model per Phase 0).
- **Execution:** prepare runtime, perform Work Package, emit events/observations,
  produce artifacts and **evidence candidates**, create checkpoints. Never
  self-validates.
- **Governance gate:** policy-driven authorization, approval workflow,
  immutable audit, integrated at the orchestration boundary.

**Prerequisites.** Phases 2–3.

**Deliverables.** A Work Package can be orchestrated and executed end-to-end on
at least one real runtime through the Harness, under governance, producing
artifacts, evidence candidates, observations, checkpoints, and events — with no
self-declared completion.

**Validation gate.** A multi-node Execution Graph runs to "waiting validation"
across at least two runtime adapters; execution never begins until
dependency/constraint/approval/resource checks pass; a forced runtime failure
pauses (does not crash) the operation; every orchestration decision is
replayable from the event log; the governance gate denies a policy-violating
action and records an immutable audit entry.

---

## Phase 5 — Supervision, Validation & Recovery

**Objective.** Close the operational loop. Implement Supervision (observe +
derive health), Validation (evidence-based completion), and Recovery (classify
failure, select strategy, restore, resume).

**Why sixth.** These layers consume Execution's output stream and the
checkpoint/state substrate. Supervision must be specified in Phase 0 before it
can be built here. Validation determines completion; Recovery determines
continuation. Together they make the platform observable and recoverable.

**Scope.**
- **Supervision:** consume event streams, aggregate Observations, derive
  operational health, detect failures, escalate — per the Phase 0 boundary that
  separates detection (Supervision) from response (Recovery) and from
  pause/resume (Orchestration).
- **Validation:** evidence collection, policy evaluation, validator dispatch
  (automated/human/hybrid), four-valued result, Validation Report; gate to
  Knowledge.
- **Recovery:** failure classification, deterministic strategy selection,
  checkpoint restoration, retry/failover (bounded), human escalation, recovery
  audit and metrics; reconcile pre-declared recovery edges with runtime-
  selected strategy.

**Prerequisites.** Phases 2–4 (events, checkpoints, execution sessions,
governance).

**Deliverables.** Executions are continuously observed; completion is
determined only by independently verifiable evidence; failures are recovered
from the latest valid checkpoint rather than restarted.

**Validation gate.** A failing Work Package is detected by Supervision,
classified by Recovery, restored from checkpoint, retried within bounds, and
either recovered or escalated — without losing context or validated evidence.
Validation independently passes/fails/partials a Work Package from evidence
alone; a runtime "success" with insufficient evidence does **not** complete.
The pause/resume/escalate verbs have exactly one owner each.

---

## Phase 6 — Knowledge, Reflection & Operational Maturity

**Objective.** Make the platform improve. Implement Reflection and the
Knowledge graph, feed validated learning back into Context Engineering and
Planning, and harden the platform for sustained operation.

**Why last.** Learning depends on validated outcomes (Phase 5) and complete
operational history (Phases 2–5). Reflection and Knowledge are the top of the
dependency flow and consume everything below.

**Scope.**
- **Reflection:** post-execution analysis (what succeeded/failed and why),
  pattern extraction — sourced only from validated evidence.
- **Knowledge:** operational knowledge graph, confidence/freshness lifecycle,
  ingestion gated on validation, retrieval into Context Engineering and Planning.
- **Feedback loop:** knowledge improves future planning and context; recovery
  patterns may influence future Execution Strategies.
- **Operational maturity:** end-to-end observability/audit, performance
  envelope, dashboards, capacity, runbooks.

**Prerequisites.** Phases 1–5.

**Deliverables.** Completed operations contribute reflections and validated
knowledge; subsequent planning measurably reuses prior knowledge; the platform
has the observability, audit, and performance characteristics to run
continuously.

**Validation gate.** A second run of a previously executed goal class
demonstrably reuses validated knowledge in planning/context; only validated
outcomes enter Knowledge; reflections are evidence-sourced; end-to-end
observability and audit cover every layer; the platform meets its stated
performance and recoverability targets under load.

---

## Phase Validation Gate Pattern

Every phase ends with the same gate sequence before the next phase begins:

```
Contracts Complete → Architecture Review → Integration Review →
Smoke / Scenario Tests → Documentation Review → Gate Pass → Next Phase
```

Implementation never skips a gate. A phase that fails its gate is remediated
before any later-phase work begins. See `10_VALIDATION_STRATEGY.md` and
`11_TESTING_STRATEGY.md` for the gate criteria and test obligations per phase.
