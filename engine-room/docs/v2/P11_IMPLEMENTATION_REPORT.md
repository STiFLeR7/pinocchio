# P11 — Constitutional Execution Actuation — Implementation Report

Status: Complete (not committed — awaiting explicit release instruction)
Scope: additive `nexus_execution/actuation/` submodule; no incumbent modified.
Program position: reasoning spine → **Understand → Reason → Contextualize → Plan (P10) → Coordinate → [Actuate] → Execute/Runtime**. Planning produces *what*; Execution Actuation deterministically *drives* it through Orchestration and Runtime.

---

## Executive Summary

Execution Actuation is the missing **conductor**: the deterministic driver that walks a frozen Plan's Execution Graph wave by wave, dispatches each ready node through the existing Runtime abstraction, honors dependency/parallel/checkpoint/approval boundaries, emits durable `execution.*` events, and projects one immutable `ExecutionState` — replayable and restartable from the log alone.

The incumbents already held every *piece*: Orchestration computes a single ready wave from graph + progress; the Execution Engine performs one Work Package in one Runtime Session; the Runtime Manager prepares Ready sessions. But **nothing looped them across the whole graph** — the incumbent `nexus_workflows.WorkflowCoordinator` orchestrates exactly once and executes only the root wave, never feeding `completed_nodes` back to unlock downstream nodes. That multi-wave traversal is the P11 gap, and P11 fills it **additively**: it reuses the Orchestration coordinators, the Runtime Manager, and the Execution Engine unchanged, and adds only the traversal loop, the `execution.*` event stream, and the `ExecutionState` projection.

Two apparent constitutional tensions were surfaced before coding and resolved **within** the architecture (no contract/invariant/ADR edit), matching the P9/P10 precedent:

1. **"Execution State" as a new object contradicts INV-07/INV-14.** Resolved: `ExecutionState` is a `ValueObject` **projection** of the `execution.*` event log — never a second frozen domain schema; it is rebuildable from the log and embedded whole in `execution.completed` for exact replay.
2. **Naming collision — the roadmap reserves a top-level `nexus_actuation` for the P6 "Act" capability** (external side effects via the Harness). Resolved: P11's *Execution Actuation* is the execution-graph **traversal** driver, a distinct concept; it is hosted as the additive submodule `nexus_execution/actuation/` (the P8/P9/P10 submodule precedent), not a competing top-level package.

Validation: **23 new tests** (17 unit + 3 durable/replay/restart + 3 traversal-determinism) all green; full v2 sweep **2527 passed, 0 regressions**; MyPy strict clean (15 files); Ruff check + format clean. The incumbent `nexus_execution`, `nexus_orchestration`, and `nexus_runtime` packages are byte-for-byte unchanged.

---

## Constitutional Compliance

| Rule / Invariant | How P11 honors it |
|---|---|
| **INV-01** one-way deps | Actuation consumes the frozen Plan bundle by value (nexus_core domain objects) and drives Orchestration/Runtime/Execution **interfaces**; it imports no reasoning/estimation/context/knowledge/policy engine, no Planning/Harness producer, and no runtime provider. Proven by an AST guardrail. No incumbent imports actuation (acyclic). |
| **INV-03 / INV-04 / INV-05** planning ≠ execution; strategy declares, orchestration enacts | Actuation never plans, decomposes, or invents coordination: readiness/ordering/runtime-candidates are computed by Orchestration's own coordinators (`DependencyTracker`, `ExecutionQueueBuilder`, `ApprovalCoordinator`, `HarnessRequestBuilder`, `RuntimeRequestBuilder`). |
| **INV-07** one schema per object | `ExecutionState`/`NodeState` are `ValueObject`s, not `DomainObject`s; no second Plan/Execution-State schema. Guardrail-proven. |
| **INV-10** dependencies are edges | Readiness derives from the graph's Execution edges via the Dependency Tracker; no separate dependency structure is built. |
| **INV-11** Observation is Supervision's | `ActuationObservability` emits derived **counters** only (instrumentation, no dashboards); it produces no Observations. |
| **INV-13 / INV-14 / INV-15** log is truth; state/checkpoints derived; one event per transition | Every node/checkpoint/approval transition emits exactly one `execution.*` event; `ExecutionState` and checkpoint state are projections, embedded in `execution.completed` and rebuildable from the log. |
| **INV-16** idempotent consumers | Event ids are deterministic and node-keyed; a completed node's events are never re-emitted on restart; re-registration of the runtime is an identical (idempotent) event. |
| **INV-17 / INV-18** capture non-determinism; checkpoint-aware resume | The only captured non-deterministic value is the injected timestamp; restart resumes from recorded progress + replay, **never** from the Goal or by rebuilding the Plan. |
| **INV-20 / INV-21** execution never self-completes | `execution.completed` marks **traversal** completion (all reachable nodes driven), not a validated success verdict; per-node outcomes are recorded facts from the Runtime terminal outcome — Validation still owns completion. |
| **INV-22 / INV-23** recovery/supervision own recovery/control | On node failure Actuation records `execution.node_failed` and lets the branch halt — **no retry** (Recovery's call); at an ungranted gate it pauses (Orchestration/Governance decides). It performs no recovery, reflection, or learning. |
| **INV-37** Orchestration assigns runtimes; resolution returns candidates | Runtime candidates come from Orchestration's `RuntimeRequestBuilder`; the Runtime Manager selects/allocates. Actuation invents no runtime selection. |
| **INV-39** cross-subsystem interactions are correlated events | All traversal facts are correlated `execution.*` events on the authoritative log. |

**Non-Responsibilities audit (task list).** Actuation never: reasons · estimates · assembles context · modifies plans · evaluates policy · executes provider-specific logic · validates outputs · recovers failures · reflects · learns. Each is either delegated to its owner or simply absent; the forbidden-import guardrail proves the negative structurally.

---

## Execution Architecture

Additive submodule `nexus_execution/actuation/` (7 modules):

| Module | Responsibility |
|---|---|
| `model.py` | The immutable `ExecutionState` / `NodeState` projections, `NodeStatus` / `ActuationStatus`, `ActuationInputs` (the frozen Plan bundle, by value), `ActuationControl` (cooperative cancellation + graceful-shutdown bound), and the nine `execution.*` event-type constants. |
| `traversal.py` | `GraphWalker` (graph walker + dependency resolver) — drives Orchestration's pure coordinators to resolve the next wave; `checkpoint_nodes` reads the graph's checkpoint refs. |
| `dispatch.py` | `RuntimeDispatcher` (dispatch coordinator) — projects a node's assignment into a `RuntimeIntake`, prepares a Ready session, performs it through the Execution Engine; `DispatchOutcome`. |
| `actuator.py` | `ExecutionActuator` (execution coordinator) — the traversal loop, `execution.*` event sourcing, state projection, restart seeding, and `reconstruct_execution_state` (replay). |
| `observability.py` | `ActuationObservability` — deterministic instrumentation over the P1 sink. |
| `composition.py` | `build_execution_actuation(infrastructure, *, adapter, …)` — DI wiring over P1/P2 infrastructure. |
| `__init__.py` | Public surface. |

**Inputs (by value):** the P10 `ExecutionPlan`'s constituents — `Plan`, `ExecutionGraph`, `ExecutionStrategy`, `WorkPackage`s, context references, and any out-of-band `granted_gates`. **Output:** one immutable `ExecutionState`:

- current / completed / pending / running / blocked / waiting nodes;
- checkpoint state; approval waiting/received;
- execution lineage (completion order); runtime assignments (node → runtime);
- artifact references (by reference, never embedded — INV-12/27);
- per-node `NodeState` (status, runtime, outcome, artifacts, error).

**Placement rationale.** The driver must consume *both* Orchestration's coordination and Runtime/Execution's performance. Hosting it in `nexus_orchestration` would make a *higher* layer reach *down* to execution (an INV-01 violation and a doc-07 boundary breach: "Orchestration never performs execution"). Hosting it in `nexus_execution` is consistent with doc-08's own words — *"Execution performs Work Packages assigned by the Orchestration layer"* — and adds only a clean, acyclic `nexus_execution → nexus_orchestration` edge (Orchestration imports neither runtime nor execution, so no cycle). The incumbent Execution Engine stays minimal and replaceable; the actuator is a sibling submodule that consumes Orchestration's decisions.

---

## Traversal Engine

Deterministic, wave-by-wave, driven by Orchestration's **pure** coordinators (no re-invention):

```
build ExecutionSession (Orchestration's ExecutionSessionBuilder)
emit execution.started
loop:
  wave = GraphWalker.next_wave(graph, strategy, session, approvals,
                               completed=…, blocked_sources=failed∪rejected)
  announce execution.approval_waiting for gated-but-unreceived nodes
  ready = wave.ready − already-driven
  if not ready: break
  for node in ready (deterministic topo-rank-then-id order):
     [approval_received if gate granted] → node_started → [checkpoint_entered]
        → dispatch through Runtime → node_completed | node_failed
        → [checkpoint_completed]
     append to completed | failed
project ExecutionState ; if COMPLETED: emit execution.completed (embedding the state)
```

Supported semantics (all validated): **sequential** & **parallel** execution (a diamond's `{b,c}` are one wave), **dependency barriers** & **fan-in / merge synchronization** (`d` waits for both `b` and `c`), **fan-out**, **checkpoint pauses**, **approval pauses**, **cancellation / graceful shutdown**, and **restart continuation**.

Why not re-run the full `OrchestrationService.orchestrate()` each wave? Its event ids are `evt-{session}-{kind}-{seq}` with a *constant* session identity, so a second call would re-announce the one-shot `orchestration.execution_session_created` fact and collide (the P10 restart-bug class). Driving its *pure* coordinators is the collision-free, non-duplicating reuse — Orchestration's logic still decides every wave; Actuation only owns the loop and its own `execution.*` stream.

Determinism: node order within a wave is the queue's stable topological rank then id; ids are content-free / node-keyed; the timestamp is the sole injected non-deterministic value (a `FixedTimestampSource` in tests). Two independent runs produce equal `ExecutionState` and byte-identical event streams.

---

## Runtime Dispatch

Dispatch goes **only** through the existing Runtime abstraction; the driver never calls a provider:

```
node assignment (Orchestration RuntimeRequest: candidates, policy, coordination)
  → RuntimeIntake            (nexus_core-only integration-boundary projection; references only)
  → RuntimeManager.prepare   (Orchestration+Runtime select & allocate → Ready session; INV-37)
  → ExecutionEngine.execute  (performs the Work Package through the injected RuntimeAdapter)
  → ExecutionResult          (runtime terminal outcome + artifacts by reference)
```

The runtime adapter is **injected** (the one provider-specific choice — Runtime independence); the package imports no provider. The `RuntimeIntake` projection is a ~15-line reference-copy that deliberately duplicates `nexus_workflows.project_intake` — importing `nexus_workflows` (which imports `nexus_execution`) would create a cycle; it copies references only and lowers no requirement.

Runtime capacity is sized per run to the node count and registered every run (the Manager's registry is in-memory, so a restart over a reopened durable log must re-register); because the `runtime.registered` fact does not encode capacity, the re-emitted event is identical and idempotent (INV-16).

---

## Persistence

Rides P1/ADR-007 unchanged: the actuator emits `execution.*` events through the shared `InfrastructureContext` (durable transparently over `build_durable_infrastructure`). The nine event types exactly match the program's required set:

`execution.started` · `execution.node_started` · `execution.node_completed` · `execution.node_failed` · `execution.checkpoint_entered` · `execution.checkpoint_completed` · `execution.approval_waiting` · `execution.approval_received` · `execution.completed`.

The `execution.*` namespace was previously unused as a bus namespace (the incumbent engine emits `runtime.*`), so the addition is non-colliding. `execution.completed` embeds the full `ExecutionState` (`model_dump(mode="json")`), content-addressed in its id, so the terminal fact is self-describing and idempotent.

---

## Replay Validation

Replay reconstructs the `ExecutionState` **exactly from the log alone** (ADR-001; INV-13/14). `reconstruct_execution_state(events, session_identity=…)` reads the embedded state from `execution.completed` and `model_validate`s it back to a value-equal object.

Tests: `test_completed_event_embeds_the_full_state_for_replay` (in-memory) and `test_replay_reconstructs_state_from_the_log` (durable, reopened db) both assert `reconstructed == original`.

---

## Restart Validation

Restart resumes from recorded progress + replay — **never** rebuilding the Plan (INV-18). A fresh actuator over the same log:
- reconstructs completed/failed nodes, checkpoints, and approval history from the `execution.*` stream (`_seed`);
- skips already-driven nodes (no re-dispatch, no duplicate events);
- re-emits `execution.started` only if absent (idempotent);
- continues the traversal to completion.

Test `test_restart_resumes_without_replanning_to_an_identical_state`: run with `ActuationControl(stop_after=1)` → `PAUSED`, `completed == ("node-a",)`; a fresh actuator over the reopened durable db → `COMPLETED` all four nodes; and the resumed `ExecutionState` **equals** an uninterrupted single run's state (identical lineage, runtime assignments, artifacts).

---

## Integration Points

- **Upstream (by value):** P10 `ExecutionPlan` → `ActuationInputs` (frozen `Plan` + `ExecutionGraph` + `ExecutionStrategy` + `WorkPackage`s + context refs).
- **Orchestration (interfaces, pure):** `ExecutionSessionBuilder`, `DependencyTracker`, `ExecutionQueueBuilder`, `ApprovalCoordinator`, `HarnessRequestBuilder`, `RuntimeRequestBuilder`, `InMemoryHarnessRegistry`.
- **Runtime (abstraction):** `RuntimeManager.prepare`, `RuntimeIntake`, `PreparationRequest`, `RuntimeRegistry`.
- **Execution (incumbent engine):** `ExecutionEngine.execute`, `RuntimeAdapter` (injected).
- **Infrastructure (P1/P2):** `InfrastructureContext` as emitter + event store; `ActuationObservability` over the sink.
- **Downstream (future):** Supervision observes the `execution.*` stream; Validation consumes per-node evidence candidates (artifact references); Recovery restores from checkpoints. None are imported.

---

## Remaining Constitutional Roadmap

P11 delivers deterministic execution traversal. Still ahead (unchanged by this work):

- **Validation** completing nodes from independently-verifiable Evidence (INV-20/21) — Actuation records outcomes and evidence candidates; Validation decides completion.
- **Recovery** acting on `execution.node_failed` + checkpoints (INV-22) — retry/alternate-runtime/resume decisions; Actuation deliberately performs none.
- **Supervision** deriving Observations from the `execution.*` stream (INV-11/23) and recommending intervention; Orchestration acts.
- **Full `Checkpoint` domain-object materialization** — P11 emits checkpoint events + checkpoint state and resumes via log replay; materializing the frozen `Checkpoint` object (contracts/checkpoint.md) for the Recovery store is additive future work.
- **Multi-runtime routing** — one adapter per run today (matching the incumbent `nexus_workflows`); per-node runtime heterogeneity is additive.
- **P10/P11 release** — both remain uncommitted pending explicit instruction.

---

## Validation Summary

- **23 new tests**, all green:
  - `tests/unit/nexus_execution/actuation/test_traversal.py` (6) — dependency ordering, parallel/fan-in waves, blocked-source transitivity, determinism, checkpoint extraction.
  - `tests/unit/nexus_execution/actuation/test_actuator.py` (10) — full traversal, event stream, runtime assignments/artifacts, embedded-state replay, failure-halt (no retry), checkpoint events, approval pause + grant, graceful shutdown/pause, determinism.
  - `tests/unit/nexus_execution/actuation/test_guardrails.py` (4) — forbidden-import scan, no DomainObject, `ExecutionState` is a `ValueObject`, `execution.*` namespace owned & complete.
  - `tests/integration/test_grounded_execution_durable.py` (3) — durable + correlated, replay reconstruction, restart-to-identical-state.
- **Full v2 sweep: 2527 passed, 0 regressions** (1 opt-in skip; 1 pre-existing v1 `test_state_machines` error from the `--noconftest` fixture strip, unrelated to P11).
- **MyPy strict**: clean (15 source files). **Ruff** check + format: clean.
- **Incumbents unchanged**: `git status` shows only additions under `nexus_execution/actuation/` and `tests/…/actuation/`; no `nexus_execution`/`nexus_orchestration`/`nexus_runtime` source modified.

**Success criteria (task):** Execution Actuation is the sole constitutional owner of execution traversal ✓ · Plans remain immutable ✓ · Runtime abstractions unchanged ✓ · execution is deterministic ✓ · replay reconstructs identical state ✓ · restart resumes without replanning ✓ · all tests pass, zero regressions ✓.

Per the rules, **no commit was made**, and no engine/protocol/contract/invariant/ADR was changed.
