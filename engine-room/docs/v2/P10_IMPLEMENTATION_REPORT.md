# P10 Implementation Report — Constitutional Planning Evolution (grounded planning)

- **Date:** 2026-07-17
- **Program:** P10 (Planning) as briefed — the constitutional **Plan** capability, made grounding-aware
- **Governing decisions:** ARCHITECTURE_CONSTITUTION (capability #5 *Plan*; INV-01/03/07/10; Article IV
  determinism seam), the frozen `contracts/plan.md`, `contracts/execution_graph.md`,
  `contracts/work_package.md`, `contracts/execution_strategy.md`, ADR-001 (event authority), ADR-003
  (§3.3 Plan/Graph separation — dependencies are edges), ADR-004, ADR-007 (durable persistence),
  ADR-008 (shadow-adjudicable)
- **Rule observed:** implementation only — no architecture redesign, no protocol/contract/invariant/ADR
  edits, no engine redesign, no commit. **Two constitutional conflicts were surfaced and adjudicated
  with the operator before any code** (see §1) rather than silently reconciled.

---

## 1. Executive Summary

Planning is the constitutional owner of converting a grounded engineering objective into an executable
topology. The incumbent `nexus_planning` **already** produces the frozen **Plan**, **Work Packages**,
**Execution Graph**, and **Execution Strategy** (the `PlanningResult` bundle), deterministically, over
the P1/P2 substrate. P10 therefore did **not** create a competing planner. It makes the incumbent
producer *grounding-aware* via a new additive submodule, **`nexus_planning/grounded/`**, that consumes
the three canonical inputs — **Goal**, **EngineeringStrategy** (P5), and **ContextPackage** (P9), all
**by value** — drives the incumbent planner, computes a deterministic **coordination view** over the
resulting graph, and assembles one immutable **`ExecutionPlan`**, durably event-sourced for replay.

**Two constitutional conflicts were discovered and adjudicated before implementation:**

- **"Dependency Graph" as a distinct object contradicts INV-10.** `execution_graph.md:90,127` and
  `plan.md:120`: *"Dependencies are edges; there is **no separate Dependency Graph object** (INV-10)."*
  The incumbent correctly encodes dependencies as `EdgeType.EXECUTION` edges. **Resolution
  (operator-approved):** the "Dependency Graph" is the Execution Graph's dependency **edges** plus a
  deterministic dependency **view** (`CoordinationView.dependency_edges`) — never a separate authoritative
  object.
- **"ExecutionPlan" as a new object contradicts INV-07.** `plan.md:123`: *"Exactly one Plan schema; no
  subsystem introduces an alternative Plan representation."* **Resolution (operator-approved):** the P10
  `ExecutionPlan` **is** the frozen `Plan` (which references its sibling Execution Graph by id and owns
  its Work Packages) bundled with the Execution Strategy, capabilities, coordination view, and context
  references as a frozen **value** — not a new `DomainObject`. Exactly the P9 precedent (ExecutionContext
  = ContextPackage).

**Genuine additive value P10 delivers** (all constitutional): the **ContextPackage becomes a first-class
Planning input** (the incumbent only took a `context_ref` Reference — never the ContextPackage; its
operative constraints now flow onto the work packages); a **unified immutable ExecutionPlan that is
event-sourced for replay** (the incumbent's `plan.*` events carry summaries only — replay could not
reconstruct the plan; P10 embeds the full ExecutionPlan in a `planning.execution_plan_assembled` fact);
and a deterministic **coordination view** (parallel/sequential groups, fan-out/merge boundaries,
checkpoint/approval/recovery boundaries, dependency edges) over the frozen graph.

**New surface — `nexus_planning/grounded/`** (4 modules + `__init__`): `model` (`PlanningInputs`,
`CoordinationView`, `ExecutionPlan`), `coordination` (`analyze_coordination` — the deterministic graph
analysis), `assembler` (`GroundedPlanner` + the `planning.execution_plan_assembled` fact + observability),
`composition` (`build_grounded_planning`). The graph/work-package/strategy construction, validation,
persistence, and core `plan.*` events are **delegated to the incumbent** (single producer of the Plan).
**No** engine, protocol, contract, or invariant was changed; the incumbent `nexus_planning` is
byte-for-byte unmodified.

**Tests** — `tests/unit/nexus_planning/grounded/` (3 files, 17 tests) + `tests/integration/
test_grounded_planning_durable.py` (3 tests). **20 new tests, all green.** Full v2 sweep: **2637 passed**.
Ruff clean; MyPy strict clean (5 source files).

---

## 2. Constitutional Compliance

| Constitutional requirement | Status | How |
|---|---|---|
| Planning is the **single owner** of the Plan / Execution Graph (INV-03) | ✅ | The incumbent `nexus_planning` remains the *only* producer of `Plan`/`ExecutionGraph`/`WorkPackage`; the grounded planner drives it and produces no second authoritative object. |
| **One Plan schema** (INV-07) | ✅ | The P10 `ExecutionPlan` **bundles** the frozen `Plan` by value (guardrail: `ExecutionPlan.model_fields["plan"].annotation is Plan`); grounded models subclass `ValueObject`, never `DomainObject`. |
| **Dependencies are edges; no separate Dependency Graph** (INV-10) | ✅ | The authoritative topology is the frozen graph's `EdgeType.EXECUTION` edges; `CoordinationView.dependency_edges` is a derived *view* of them. The Plan references its sibling graph by id (`execution_graph_ref`), never nested (test asserts this). |
| Planning **reasons/estimates nothing; assembles no context** (Non-responsibilities) | ✅ | Coordination analysis is a pure function of recorded facts (topological leveling); no LLM, no scoring. The Strategy and Context are consumed by value; Planning derives nothing beyond them. |
| Planning consumes **Goal + EngineeringStrategy + ContextPackage**, by value (Inputs) | ✅ | `PlanningInputs` carries exactly these three (+ the declared work decomposition). The EngineeringStrategy and ContextPackage are read by value; Planning queries no Repository/Knowledge/History/Policy/Runtime engine. |
| Imports **no reasoning/estimation/policy/grounding engine** (INV-01) | ✅ | Guardrail proves grounded imports none of `nexus_estimation`/`nexus_policy`/`nexus_runtime`/`nexus_repository`/`nexus_intent`/`nexus_history`/`nexus_knowledge`/`nexus_context`; the only `nexus_engineering` import is `nexus_engineering.model` (the EngineeringStrategy value object) — matching the merged P6 boundary. |
| **Reason once, emit once, replay forever** (INV-17) | ✅ | The ExecutionPlan is recorded in `planning.execution_plan_assembled`; replay reconstructs it without re-planning. |
| Governance/approval/recovery **declared, not evaluated** (ADR-004, INV-05) | ✅ | The Execution Strategy declares coordination/approval/retry/validation/recovery policy (incumbent); the coordination view only *reads* the declared boundaries. Planning evaluates no policy. |
| Event Log is truth; state is a projection (INV-13/14/15) | ✅ | Planning writes its own outputs through the reused P1/P2 repositories; the ExecutionPlan is a projection anchor in the log. |
| No commit | ✅ | Nothing was committed. |

---

## 3. Planning Architecture

```
PlanningInputs (read-only, by value)          GroundedPlanner.plan
  Goal ─────────────────┐                          │
  EngineeringStrategy ───┤ (P5, by value)           │ 1. build PlanningRequest
  ContextPackage ────────┤ (P9, by value)           │    - context_ref  ← ContextPackage.identity
  work_items (declared) ─┘                          │    - constraints  ← ContextPackage.constraints
                                                    │    - default atomic item when none declared
                                                    │ 2. incumbent PlanningService.plan(goal, req, strategy)
                                                    │    - bind_strategy → postures (P6)
                                                    │    - Work Packages, Execution Graph, Execution
                                                    │      Strategy, capabilities; validate acyclic;
                                                    │      persist; emit plan.* / execution_graph.* / …
                                                    │ 3. analyze_coordination(graph, strategy)  (pure)
                                                    │ 4. assemble ExecutionPlan (frozen Plan + graph +
                                                    │    WPs + strategy + coordination + context refs)
                                                    │ 5. emit planning.execution_plan_assembled (replay)
                                                    ▼
                                        ExecutionPlan (immutable)
```

- **Single producer preserved.** The grounded planner never builds a Plan/Graph/WorkPackage itself — it
  drives the incumbent `PlanningService`, so exactly one producer authors the frozen objects (INV-03).
- **By-value consumption.** The EngineeringStrategy is passed to the incumbent (which binds its postures
  via the merged P6 `strategy_binding`); the ContextPackage's identity → `context_ref` and its
  constraints → work-package constraints. Planning reasons about neither.
- **Absence-tolerant.** With no strategy the incumbent derives postures from topology; with no context
  the plan is still valid (no context references). With no declared decomposition Planning produces the
  **atomic single-package** plan for the Goal's objective — it never invents sub-tasks (that would be
  reasoning).

## 4. Execution Graph Model

The frozen `ExecutionGraph` (incumbent) is the authoritative topology: `GraphNode`s referencing Work
Packages, and `GraphEdge`s of the closed `EdgeType` set. P10 supports the full topology vocabulary the
brief requires, deterministically:

- **sequential / parallel** — topological levels (`sequential_levels`); a level with >1 node is a
  **parallel group**.
- **fan-out** — nodes with out-degree > 1 (`fan_out_points`).
- **fan-in / merge / synchronization** — nodes with in-degree > 1 (`merge_boundaries`; the incumbent also
  records `synchronization_points` in graph policies).
- **dependency barriers** — the boundaries between topological levels.
- **checkpoints** — checkpoint node refs (`checkpoint_boundaries`).
- **approval** — approval-gate nodes (`approval_boundaries`).

The edge set stays within the closed, frozen `EdgeType` vocabulary (no new edge type — that would require
an ADR per `execution_graph.md:181`). Graph construction is reproducible (clock-free ids; the incumbent
validates acyclicity before coordination analysis runs).

## 5. Dependency Planning

**Dependencies are edges (INV-10).** `CoordinationView.dependency_edges` is the sorted set of the graph's
`EdgeType.EXECUTION` edges (source → target) — the "Dependency Graph" expressed as edges, not a separate
object. From these edges the planner derives, deterministically (longest-path Kahn leveling): topological
levels, in/out degrees, parallel groups, fan-out points, and merge boundaries. The analysis is a pure
function of the frozen graph — identical graphs yield identical views (`test_coordination_is_deterministic`).

## 6. Coordination Strategy

The coordination model itself is authored by the incumbent `ExecutionStrategy` (derived from the bound
EngineeringStrategy or topology — P6). P10's `CoordinationView` reads the *declared* governed boundaries
without evaluating any policy:

- `coordination_model` ← `ExecutionStrategy.coordination`
- `approval_boundaries` ← the graph's declared `approval_gates`
- `checkpoint_boundaries` ← the graph's checkpoint node refs
- `recovery_boundaries` ← the checkpoint nodes (recovery resumes from checkpoints + event replay — INV-18)

Declaration ≠ evaluation (ADR-004): the view surfaces where approval/recovery apply; Governance and
Recovery own the decisions.

## 7. Persistence

No new persistence. The incumbent persists the Plan / Work Packages / Execution Graph / Execution Strategy
through the reused P1/P2 repositories (durable transparently over `build_durable_infrastructure`,
ADR-007). P10 adds one `planning.execution_plan_assembled` fact through the infrastructure emitter — same
substrate, correlated to the Goal — whose payload embeds the full serialized ExecutionPlan (closing the
incumbent's "events are summaries only" replay gap).

## 8. Replay Validation

`tests/integration/test_grounded_planning_durable.py`:

- **Durable + correlated** (`test_execution_plan_fact_is_durable_and_correlated`): after assembly, a
  reopened durable infrastructure contains exactly one `planning.execution_plan_assembled` fact,
  correlated to the Goal.
- **Replay without re-planning** (`test_replay_reconstructs_plan_without_replanning`): reconstructing
  `ExecutionPlan.model_validate(event.payload["execution_plan"])` from the reopened log yields an object
  **value-equal** to the original — the full ExecutionPlan (Plan + graph + WPs + strategy + coordination)
  reconstructs from the log, no re-planning. (Round-trip verified clean — no enum/tuple coercion issues.)

## 9. Restart Validation

`test_restart_reconstruction_is_identical`: assembling the same `PlanningInputs` over a fresh set of
engines wired on the **reopened** SQLite file reproduces a **byte-identical** `ExecutionPlan`. Planning is
a pure function of its inputs (clock-free ids; deterministic coordination analysis); the injected event
timestamp is the only captured-as-data value and is never used in identity or topology.

## 10. Integration Points

- **Consumes (read-only, by value):** `nexus_core.domain.{Goal, ContextPackage, Plan, WorkPackage,
  ExecutionGraph, ExecutionStrategy}`, `nexus_engineering.model.EngineeringStrategy` (the value object —
  the merged P6 consumption boundary), the incumbent `nexus_planning` (same package), and the P1
  `InfrastructureContext`. Imports **no** reasoning/estimation/policy/grounding engine (guardrail-proven).
- **Produces:** one immutable `ExecutionPlan` per Goal, plus one `planning.execution_plan_assembled` fact.
  `build_grounded_planning(infrastructure)` is the single new DI seam.
- **Upstream/downstream unchanged:** Engineering Intelligence produces the EngineeringStrategy; Context
  Engineering produces the ContextPackage; **Planning consumes both**; **Orchestration consumes the
  ExecutionPlan** (the frozen Plan + Execution Graph it already reads). No downstream engine was changed.
- **Constitutional flow preserved:** Intent → EI Strategy → grounded Context → **grounded Planning** →
  ExecutionPlan → Orchestration.

## 11. Remaining Work After P10

Planning now assembles a durable, replayable ExecutionPlan from the three canonical inputs. Outstanding,
none blocking:

1. **Wire the grounded planner into the running spine:** connect grounded Context Engineering (P9) →
   grounded Planning (P10) → Orchestration end-to-end (a composition/cutover step). The incumbent's
   existing call sites continue to work unchanged in the meantime.
2. **Intelligent decomposition (optional, deferred):** the `DecompositionStrategy` seam remains the place
   for a future deterministic goal→WBS decomposer; P10 keeps the constitutional default (atomic
   single-package, or an explicitly declared decomposition) so Planning never reasons.
3. **Richer coordination edges (optional):** the closed `EdgeType` set already includes
   `SYNCHRONIZATION`/`APPROVAL`/`RECOVERY`/`DATA`; materializing merge/approval/recovery as explicit edges
   (rather than a derived view + policy lists) is additive and needs no new edge type.
4. **Freeze nothing new:** the ExecutionPlan is the already-frozen `Plan` (+ sibling graph); no contract
   freeze is required (INV-07/INV-10 discipline preserved).

**Verdict:** P10 is functionally complete. Planning remains the single constitutional owner of the Plan
and its executable topology; it now consumes the EngineeringStrategy (P5) and ContextPackage (P9) by
value, assembles one immutable ExecutionPlan with a deterministic coordination view, and persists it so
replay and restart reconstruct it identically — with no engineering reasoning, no context assembly, no
policy evaluation, and no change to any engine, protocol, contract, or invariant. **No commit was made.**

---

## Validation summary

| Suite | Result |
|---|---|
| `nexus_planning/grounded` unit (`test_coordination`, `test_assembler`, `test_guardrails`) | **17 passed** |
| `tests/integration/test_grounded_planning_durable.py` (durable / replay / restart) | **3 passed** |
| Incumbent `nexus_planning` suite (regression) | **green, unchanged** |
| Full v2 `nexus_*` unit + key integration sweep | **2637 passed** |
| MyPy strict on `nexus_planning/grounded` | **Success: no issues found in 5 source files** |
| Ruff check + format on new files | **clean** |

> Run with `--noconftest`: the repo-root `conftest.py` imports the v1 app (requires `discord`, absent
> here); the v1-app tests are outside the v2 sweep — exactly as in the P1–P9 reports.
