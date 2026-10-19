# Plan — Canonical Logical Contract

Status: Frozen (Phase 0 contract freeze)
Primary source: `docs/v2/02_OBJECT_MODEL.md`, `docs/v2/04_PLANNING.md`
Binding: ADR-003 (§3.3 Plan/Execution Graph separation), ADR-001 (state is projection)

> Logical specification only. No serialization, storage, API, or code. Fields are
> logical (name + meaning + required/optional).

---

## 1. Purpose

A **Plan** is the abstract operational approach for achieving a single Goal. It
records *how the Goal will be approached at the strategic level* — its
milestones, priorities, a summary of dependencies, and the rationale for the
chosen approach — and it points to the concrete operational topology (the
Execution Graph) and the executable units (Work Packages) without containing
their stateful machinery.

The Plan answers "what is the overall approach, and why" while deferring "in what
exact order, under what conditions" to its Execution Graph and "what each unit of
work is" to its Work Packages. It is the bridge object between operational
understanding and executable work.

The Plan is descriptive, not stateful-by-execution: it is authored once per
planning cycle and is not the live record of execution progress. Execution
progress lives in the Execution Graph state (see `execution_graph.md`), itself a
projection of the Event Log.

---

## 2. Ownership

- **Produced by:** Planning. Planning is the sole producer of Plans (INV-03 —
  Planning decides what work happens and never performs it).
- **State owned by:** Planning. A Plan's lifecycle transitions (drafting,
  finalization, supersession) are owned by Planning.
- **Consumed by:** Orchestration (reads the approach and dereferences the
  Execution Graph), Governance (evaluates the Plan-level constraints/approach
  against policy), Supervision and Recovery (read for context; never mutate),
  Knowledge (mines completed Plans).
- **Not owned by:** No execution, runtime, or harness layer ever produces or
  mutates a Plan. Per ADR-001, the Plan's *current state* is a projection of the
  Event Log; Planning emits the transition events.

---

## 3. Lifecycle

State is a projection of the Event Log (ADR-001, INV-13/INV-14); the states below
are the projected lifecycle, and every transition emits exactly one Event
(INV-15).

| State | Meaning |
|-------|---------|
| `Draft` | Plan under construction by Planning; approach not yet finalized. |
| `Ready` | Plan finalized; Execution Graph reference and Work Packages exist; consumable by Orchestration. |
| `Active` | At least one referenced Work Package / Execution Graph node is executing. |
| `Superseded` | Replaced by a newer Plan version for the same Goal (replanning). |
| `Completed` | The Goal's outcome has been achieved per validated Evidence across the Plan's Work Packages. |
| `Cancelled` | Planning or Governance terminated the Plan before completion. |
| `Failed` | The approach is no longer achievable and no recovery/replan continues it. |

Allowed transitions:

```
Draft → Ready → Active → Completed
Draft → Cancelled
Ready → Active | Superseded | Cancelled
Active → Completed | Failed | Superseded | Cancelled
```

Notes:
- A Plan is never resumed "from intent." Resumption is driven from Execution
  Graph state plus event replay (INV-18); the Plan is re-read, not reconstructed.
- `Superseded` is the replanning path: a new Plan version is authored; the prior
  version is retained immutably (Versioning Rules §8).

---

## 4. Required Fields

| Field | Meaning |
|-------|---------|
| `identity` | Stable, unique identifier of this Plan; participates in correlation/trace lineage. |
| `parent_goal` | Reference (by id) to the Goal this Plan serves. Exactly one Goal per Plan. |
| `version` | Monotonic version of the approach for this Goal (supports supersession). |
| `approach_summary` | Declarative description of the chosen strategic approach and why it was selected. |
| `milestones` | Ordered set of measurable progress markers (each: identifier, meaning, the completion condition that marks it reached). |
| `priorities` | The relative priority ordering Planning assigned across the work (informs scheduling, never selects runtimes). |
| `dependency_summary` | A human-readable / abstract summary of the principal dependencies. Authoritative dependencies are **edges in the Execution Graph**, not a field here (INV-10); this is a summary, not a graph. |
| `work_package_refs` | References (by id) to the Work Packages composing this Plan. The Plan owns its Work Packages; Work Packages never own Plans. |
| `execution_graph_ref` | Reference (by id) to this Plan's Execution Graph. The graph is a **sibling artifact**, referenced, never nested (ADR-003 §3.3, INV-10). |
| `rationale` | The explainable basis for the approach: why this work, why this order, why these dependencies, why these capabilities. |
| `status` | The projected lifecycle state (§3). |

---

## 5. Optional Fields

| Field | Meaning |
|-------|---------|
| `operational_risks` | Risks Planning identified (missing information, unavailable resources, approval bottlenecks, external dependencies). Inputs to Supervision; advisory only. |
| `complexity_estimates` | Estimated operational complexity, effort, coordination effort, expected duration, expected resource usage. |
| `constraints_summary` | Plan-level summary of governance/deadline/budget/workspace constraints that shaped the approach (authoritative constraints live on Work Packages and Policy). |
| `assumptions` | Explicit planning assumptions whose violation would invalidate the approach. |
| `supersedes` | Reference to the prior Plan version this Plan replaces (set on replanning). |
| `correlation` | Correlation/trace identifiers tying this Plan to the originating Intent/Goal lineage. |
| `source` | Provenance metadata (e.g. planning cycle, planner identity) for audit. |

---

## 6. Invariants

- **INV-03 / INV-08:** A Plan describes approach, never procedure-as-execution
  and never an outcome redefinition. It carries no runtime, no execution step,
  and does not restate the Goal's outcome — it references the Goal.
- **INV-10:** The Execution Graph is a sibling artifact referenced by
  `execution_graph_ref`, never nested in the Plan. Dependencies are edges in that
  graph; there is **no separate Dependency Graph object** — `dependency_summary`
  is a summary, not an authoritative dependency structure.
- **INV-07:** Exactly one Plan schema; no subsystem introduces an alternative
  Plan representation.
- **INV-13 / INV-14:** The Plan's current state is a projection of the
  authoritative Event Log; it is never an independent source of truth.
- **INV-15:** Every Plan state transition emits exactly one Event.
- **One Goal per Plan; one or more Plans per Goal over time** (versioned
  supersession). A Plan never spans multiple Goals.
- **Planning-only mutation:** No execution/runtime/harness layer mutates a Plan.

---

## 7. Relationships

- **References `goal.md`** by id via `parent_goal` (consumes the Goal's outcome,
  domain, priority, constraints, scope).
- **Owns / references `work_package.md`** by id via `work_package_refs`. Plans
  own Work Packages; the inverse is forbidden.
- **References `execution_graph.md`** by id via `execution_graph_ref` (sibling
  artifact). The Execution Graph's nodes in turn reference the same Work
  Packages.
- **References `execution_strategy.md`** indirectly: Execution Strategy is
  selected during planning and is carried at the Work Package / Execution Graph
  node level; the Plan's `approach_summary`/`rationale` explain the strategic
  intent the Strategy enacts.
- **Consumes `context_package.md`** during authoring (validated Context Package
  is a precondition for planning); the Context Package itself is embedded/
  referenced at the Work Package level, not stored on the Plan.
- **Referenced by** Orchestration, Supervision, Recovery, Governance, and
  Knowledge as a read-only artifact.

---

## 8. Versioning Rules

- **Additive evolution.** New optional fields may be added without a breaking
  change. Required fields are never removed or repurposed in place.
- **Approach changes create a new Plan version**, not an in-place mutation of a
  finalized Plan. The prior version is retained immutably and marked
  `Superseded`; the new version sets `supersedes`. This preserves replay and
  audit (ADR-001) — old Plan states remain reconstructable from the log.
- **Identity is stable** across the lifecycle of a single Plan version; the
  `version` field distinguishes successive approaches for the same Goal.
- **Reference integrity over embedding.** Growth (more milestones, richer risk
  models, planning templates) extends the schema via optional fields and the
  referenced Execution Graph / Work Packages — never by nesting the graph or
  introducing a parallel Plan definition (INV-07, INV-10).
