# Nexus v2 — Implementation Overview

Status: Engineering Plan (authoritative)
Source architecture: `docs/v2/` (00–26 + README)
Workspace: `blueprint/v2/`

---

## What This Blueprint Is

`blueprint/v2/` is the engineering program for implementing the Nexus v2 target
architecture. It is a planning artifact, not code. It translates 27
architecture documents into ordered phases, independently verifiable Action
Points, an explicit dependency graph, a ranked risk register, an ADR backlog,
and validation/testing strategies.

A new engineer should be able to read this directory and understand the
architecture, the implementation order, every dependency, every risk, every
milestone, and begin building without architectural ambiguity.

This blueprint does **not** modify the existing `blueprint/` content. It is a
parallel v2 planning space.

---

## The Architecture in One Page

Nexus v2 is an **Operational Intelligence Platform**: it transforms operator
goals into governed, observed, recoverable, continuously-improving execution.
Execution is one replaceable capability among many. The platform's value is
understanding work *before* execution begins.

**The pipeline (one-way dependency flow):**

```
Operator
  │
  ▼
Intent Resolution      request → normalized Goal           (= "Executive Intelligence")
  ▼
Context Engineering    Goal → validated Context Package
  ▼
Planning               Goal + Context → Plan + Work Packages + Execution Graph
  ▼
Execution Strategy     declarative coordination behavior
  ▼
Skill Selection        capabilities → reusable procedures
  ▼
Work Packaging         execution-ready Work Packages
  ▼
Orchestration          coordinate: gate, assign runtime, sequence
  ▼
Execution              perform work; emit artifacts + evidence candidates
  ▼
Supervision            observe; derive health; recommend intervention
  ▼
Validation             determine completion by evidence (never self-report)
  ▼
Recovery               classify failure; restore; resume (don't restart)
  ▼
Reflection             validated outcomes → knowledge candidates
  ▼
Knowledge              persist understanding; feed future planning
```

**Cross-cutting infrastructure** every layer rides on: Object Model, Event
Model, State Model, Checkpoint Model, Policy Engine, Capability Model, Resource
Model, Runtime Model, Artifact Model, Governance, and the **Harness** (the
single integration boundary for all external systems — Runtime, Context,
Knowledge, Validation, Communication, Governance, Observability harnesses).

**Architectural invariants** (from `01_ARCHITECTURE.md`): one responsibility
per layer; one-way dependency flow; completion by evidence not runtime
confidence; goals describe outcomes not procedures; skills describe capability
not runtime; every execution observable; every decision explainable; recover
from state, never from operator intent.

---

## The Six Engineering Phases

| Phase | Name | Produces |
|-------|------|----------|
| 0 | Foundation & Architectural Decisions | ratified ADRs, reconciled object model, scaffold + contract-test harness |
| 1 | Core Object Model & Contracts | one authoritative schema per object; seam contract tests |
| 2 | Infrastructure Substrate | Event, State, Checkpoint, Policy, Artifact, Harness SDK |
| 3 | Understanding Pipeline | Goal → validated Context → Plan → Execution Graph of Work Packages (no execution) |
| 4 | Execution Coordination | Orchestration, Runtime/Harness adapters, Resources, Execution, Governance gate |
| 5 | Supervision, Validation & Recovery | observe, verify by evidence, recover from failure |
| 6 | Knowledge, Reflection & Maturity | learn from validated outcomes; feed planning; operational hardening |

Full definitions and per-phase validation gates: `01_PHASES.md`.

---

## Action Points at a Glance

The Action Point catalog (`02_ACTION_POINTS.md`) is the unit of implementation
work. Identifiers are stable and phase-scoped (`AP-PNN`).

- **Phase 0:** AP-001…AP-007 — persistence decision, registry unification,
  object reconciliation, policy/approval model, scaffold, contract harness,
  glossary.
- **Phase 1:** AP-101…AP-112 — schema format + one schema per object family.
- **Phase 2:** AP-201…AP-207 — event bus/store, idempotency, state engine,
  checkpoint store, policy engine, artifact store, Harness SDK.
- **Phase 3:** AP-301…AP-309 — intent, context (+harnesses), capability
  resolution, skills, planning, graph builder, strategy, work packaging.
- **Phase 4:** AP-401…AP-406 — orchestration, resources, runtime adapters,
  execution, governance gate.
- **Phase 5:** AP-501…AP-503 — supervision, validation, recovery.
- **Phase 6:** AP-601…AP-604 — reflection, knowledge, retrieval/feedback,
  operational maturity.

---

## The Decisions That Gate Everything

Five Phase-0 decisions block downstream work. They are the reason Phase 0
exists (full list in `09_ADR_BACKLOG.md`):

1. **Persistence / event-sourcing model** (ADR-001) — the single source of
   truth across Event + State + Checkpoint. Everything in Phase 2 depends on it.
2. **Registration/capability contract unification** (ADR-002) — collapse the
   four overlapping registries (Harness · Runtime · Resource · Capability).
3. **Object-model reconciliation** (ADR-003) — one Work Package schema;
   Execution Graph containment; Observation ownership; Intent Resolution rename.
4. **Policy language + approval taxonomy + determinism boundaries** (ADR-004).
5. **Event bus / store technology + delivery + idempotency** (folded into
   ADR-001 / Phase 2).

---

## Architecture Health at Authoring Time

The source architecture is now **structurally complete**. During absorption,
three documents were found empty/duplicated and have since been authored:
`09_SUPERVISION` (now resolves the pause/resume/escalate ownership question —
Supervision *recommends*, Orchestration *acts*), `11_HARNESS` (now a real
generalized integration-boundary spec), and `26_REFLECTION` (clean separation
from Knowledge and Planning). What remains is **reconciliation**, not missing
subsystems — captured as Phase-0 APs and in `08_ARCHITECTURE_GAPS.md`.

---

## How to Use This Directory

- Start here, then read `01_PHASES.md` and `02_ACTION_POINTS.md` (the spine).
- Use `03_DEPENDENCY_GRAPH.md` and `04_IMPLEMENTATION_ORDER.md` to sequence work.
- Consult `05_RISKS.md`, `07_UNKNOWNS.md`, `08_ARCHITECTURE_GAPS.md`, and
  `09_ADR_BACKLOG.md` before starting any AP they reference.
- `10_VALIDATION_STRATEGY.md` and `11_TESTING_STRATEGY.md` define the gates each
  phase must pass. `12_ROADMAP.md` sequences the phases into a delivery arc.
- `06_TECHNICAL_DEBT.md` tracks deliberate shortcuts to repay.

Full index: `README.md`.
