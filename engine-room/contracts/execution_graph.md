# Execution Graph — Canonical Logical Contract

Status: Frozen (Phase 0 contract freeze)
Primary source: `docs/v2/18_EXECUTION_GRAPH.md`
Binding: ADR-003 (§3.3 sibling artifact referenced by Plan; dependencies are
edges; no separate Dependency Graph), ADR-001 (state is projection; resumable
from graph state)

> Logical specification only. No serialization, storage, API, or code. Fields are
> logical (name + meaning + required/optional).

---

## 1. Purpose

The **Execution Graph** is the authoritative representation of operational
topology for a Plan: the relationships between Work Packages, their execution
dependencies, synchronization points, approvals, conditions, checkpoints, and
recovery paths. It is the operational blueprint that Orchestration executes,
Supervision observes, Recovery restores, Validation completes, and Knowledge
learns from.

Per ADR-003 §3.3 the Execution Graph is a **separate, stateful sibling artifact
referenced by the Plan by id — never nested inside it** (INV-10). It has its own
lifecycle because it is stateful and evolves independently of the Plan's
authoring lifecycle. Crucially, **dependencies are edges in this graph**; the
separate "Dependency Graph" object is eliminated.

The graph describes operational behavior and flow; it never performs execution
(doc 18 boundaries).

---

## 2. Ownership

- **Produced by:** Planning. Planning constructs the graph; it never executes it
  (INV-03).
- **State owned by:** The graph is the stateful coordination artifact. Its
  *state transitions* during execution are driven by Orchestration (enacting the
  topology) and Recovery (restoring topology), with each transition recorded as
  an Event on the authoritative log (ADR-001). The graph's current state is a
  **projection** of that log, never an independent store (INV-14).
- **Consumed by:** Orchestration (derives execution order from graph state),
  Supervision (observes progression — stalled nodes, unhealthy branches, blocked
  dependencies), Recovery (restores graph state; never reconstructs the graph),
  Validation (completes nodes from Evidence), Knowledge (mines completed graphs).
- **Boundary:** The graph never validates Evidence, creates context, or performs
  planning (doc 18 boundaries).

---

## 3. Lifecycle

State is a projection of the Event Log (ADR-001, INV-13/INV-14); every transition
emits exactly one Event (INV-15). Each node maintains its own state; the graph
exposes aggregate state. Resumption is from graph state + event replay, never
from operator intent (INV-18).

| State | Meaning |
|-------|---------|
| `Created` | Planning has constructed the topology; not yet cleared to run. |
| `Ready` | Eligible for orchestration; entry nodes' dependencies satisfiable. |
| `Executing` | One or more nodes are executing. |
| `Paused` | Orchestration has suspended progression. |
| `Waiting` | Progression is blocked on a synchronization point or approval. |
| `Blocked` | A dependency/resource condition prevents progression. |
| `Recovering` | Recovery is restoring graph state / traversing recovery paths. |
| `Completed` | The completion flow has been reached; all required nodes completed per Evidence. |
| `Failed` | The graph cannot complete and recovery does not continue it. |
| `Cancelled` | Terminated by Orchestration/Governance before completion. |

```
Created → Ready → Executing → Completed
Executing → Paused | Waiting | Blocked | Recovering | Failed | Cancelled
Paused | Waiting | Blocked | Recovering → Executing
Recovering → Failed | Cancelled
```

---

## 4. Required Fields

| Field | Meaning |
|-------|---------|
| `identity` | Stable unique id; participates in correlation/trace lineage. The Plan references the graph by this id. |
| `parent_goal` | Reference (by id) to the Goal. |
| `parent_plan` | Reference (by id) to the owning Plan (the graph is its sibling artifact). |
| `version` | Graph version (supports replanning / topology evolution). |
| `nodes` | The executable units of topology. Each Node **references a Work Package** (by id) and may reference its Execution Strategy, required Skills, required Context, and constraints. Nodes never perform execution. |
| `edges` | The typed relationships between nodes (see Edge Types below). **Dependencies are edges** — there is no separate Dependency Graph (INV-10). |
| `conditions` | Deterministic predicates that gate Conditional edges and branching. Conditions must be deterministic (no non-deterministic evaluation on replay, ADR-001 §3.6). |
| `checkpoints` | Node-level checkpoints (e.g. Planning Complete, Context Ready, Execution Started, Validation Complete). Each is a derived snapshot tied to a log position; enables graph restoration (INV-18). |
| `policies` | Graph-level coordination/approval/recovery policy bindings (reference the governing `execution_strategy.md` and `policy.md`); govern enactment without duplicating Strategy. |
| `state` | The projected aggregate graph state plus per-node states (§3). A projection of the Event Log, never authoritative on its own. |
| `metadata` | Identifier, Goal, Plan, version, created time, execution state, progress, and node tallies (active/completed/pending/failed). |

### Edge Types (the value space of `edges`)

| Edge type | Meaning |
|-----------|---------|
| `Execution` | Execution dependency — target proceeds only after source satisfies its dependency requirement. |
| `Data` | Transfers operational artifacts/outputs from source to target. |
| `Approval` | Requires governance approval before progression; corresponds to the Strategy's approval policy. |
| `Recovery` | Defines recovery transitions (retry, alternative runtime) as explicit topology. |
| `Conditional` | Active only when its bound `condition` is satisfied (deterministic). |
| `Synchronization` | Waits for multiple source nodes to complete before the target continues. |

The graph is **directed and acyclic**; circular paths are prohibited unless
explicitly represented as iterative loops (doc 18 — "Directed").

---

## 5. Optional Fields

| Field | Meaning |
|-------|---------|
| `metrics` | Operational metrics supporting supervision: completion percentage, execution time, critical path, parallelism, retry count, recovery count, approval count, average node duration. |
| `created_time` | Construction timestamp (also surfaced via metadata). |
| `correlation` | Correlation/trace identifiers tying the graph to its Plan/Goal lineage. |
| `loops` | Explicit iterative-loop declarations where intentional cycles are represented (the only sanctioned exception to acyclicity). |
| `recovery_paths` | Named recovery sub-topologies (expressed via Recovery edges) for explicit, auditable recovery flow. |

---

## 6. Invariants

- **INV-10 / ADR-003 §3.3:** The Execution Graph is a sibling artifact referenced
  by the Plan (by id), never nested in it. **Dependencies are edges**; there is no
  separate Dependency Graph object.
- **Nodes reference Work Packages; they never embed or replace them** — one Work
  Package schema (INV-07); the node is a topology pointer plus coordination
  metadata.
- **Directed acyclic** except explicit iterative loops (doc 18); conditions are
  **deterministic** (ADR-001 §3.6 — no recomputed non-determinism on replay).
- **INV-13 / INV-14 / INV-15:** Graph state and checkpoints are projections /
  derived snapshots of the authoritative Event Log; every transition emits
  exactly one Event.
- **INV-18:** The graph is resumable from graph state + event replay; Recovery
  restores graph state and never reconstructs the graph, never resumes from
  operator intent.
- **INV-11 / INV-23:** The graph exposes state for Supervision to observe;
  Supervision recommends and Orchestration acts — the graph itself does not
  control execution.
- **INV-20 / INV-21:** Node completion derives from Evidence via Validation; the
  graph never self-declares node completion.
- **INV-03:** Planning constructs the graph and never executes it.

---

## 7. Relationships

- **Referenced by `plan.md`** via the Plan's `execution_graph_ref` (sibling, not
  nested). One graph per Plan version.
- **Nodes reference `work_package.md`** (by id) — the same Work Packages the Plan
  owns; the graph's edges express the authoritative ordering between them.
- **Nodes / policies reference `execution_strategy.md`:** the Strategy governs
  coordination/approval/retry/timeout/validation/recovery/checkpoint behavior;
  Approval edges correspond to the Strategy's approval policy.
- **References `policy.md`:** Approval edges and graph policies are evaluated by
  the Policy Engine / Governance (INV-28).
- **References `checkpoint.md`:** graph checkpoints are derived snapshots tied to
  log positions (ADR-001).
- **Observed via `observation.md`:** Supervision derives Observations of graph
  progression from exposed node/graph state.
- **Completed graphs feed `knowledge.md`:** repeated graph patterns may become
  reusable planning templates (deferred; additive).

---

## 8. Versioning Rules

- **Additive evolution.** New optional fields (metrics, adaptive/dynamic-
  expansion metadata, deferred in doc 18) extend the schema without breaking it.
  Required components are never removed or repurposed in place.
- **Stateful artifact, replay-preserving.** Because state is a projection
  (ADR-001), graph state changes are appended as events and past graph states
  remain reconstructable. Checkpoints can be regenerated from the log.
- **Topology changes create a new graph version**, not in-place mutation of a
  finalized graph; replanning produces a new graph version referenced by the new
  Plan version. Identity is stable within a version.
- **Edge-type set is closed and versioned.** New edge semantics require an ADR
  superseding ADR-003 §3.3, never an ad-hoc edge type; this preserves the
  "dependencies are edges, no separate Dependency Graph" invariant (INV-10).
- **Determinism preserved across versions:** conditions remain deterministic;
  dynamic-graph-expansion features (future) must preserve deterministic execution
  semantics and replayability.
