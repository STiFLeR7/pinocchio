# Phase 5 — Orchestration Layer: Implementation Decisions

**Status:** Implemented. **Scope:** the orchestration layer (`nexus_orchestration/`).
**Authority:** This document records *implementation decisions* only. It does not
amend any ADR, contract, or invariant — the architecture remains frozen.
Observations that might warrant future architecture review are listed in §5 with
recommendations, not applied.

Orchestration coordinates a validated Plan (its Execution Graph + Execution
Strategy) into a deterministic execution structure — an Execution Session,
dependency state, an execution queue, approval state, and Harness/Runtime requests —
persists it through Phase 2 infrastructure, and emits orchestration events. It
coordinates; it never executes. With Phase 5 the first half of the pipeline ends at
the threshold of execution:

```
… → Planning → Execution Strategy → Orchestration → (Harness → Runtime)
```

---

## 1. Component → architecture mapping

| Component (`nexus_orchestration/…`) | Produces / does | Doc 07 / Invariants |
|---|---|---|
| `orchestrator.OrchestrationService` | drives the pipeline, persists, emits | doc 07 boundaries |
| `execution_session` | immutable Execution Session (5 bound artifacts) | doc 07 *Outputs* |
| `dependency_tracker` | per-node readiness (satisfied/pending/blocked) | doc 07 *Dependency Coordination*, INV-10 |
| `queue` | deterministic execution queue (topological) | doc 07 *State Model* |
| `approvals` | approval state per gate | ADR-004, doc 07 *Approval Coordination* |
| `harness_requests` | one Harness Request per ready node | doc 07 *Runtime Assignment* |
| `runtime_requests` | runtime requirements + harness candidates | ADR-002, INV-37 |
| `registry` | reference `HarnessRegistry` (Protocol) | ADR-002, INV-36/37 |
| `validators` | fail-fast orchestration validation | INV-10 |
| `composition` | DI wiring over `nexus_infra` | — |

## 2. Key implementation decisions

1. **Deterministic, AI-free coordination.** The decomposition arrives as the
   immutable Execution Graph + Strategy; the Orchestrator coordinates them
   mechanically. Every identifier is a pure function of the bound Goal/Plan
   identities and node keys (`ids.py`), so identical inputs yield byte-identical
   sessions, queues, dependency/approval state, requests, and event streams.

2. **Pre-execution snapshot, with optional progress.** This phase ends before
   execution begins, so with no progress only *root* nodes are ready; downstream
   nodes are blocked on their dependencies. The `OrchestrationRequest` optionally
   carries `completed_nodes` / `paused_nodes` / `approved_gates` / `rejected_gates`
   (resume/progress inputs, default empty) — so the canonical case is determined
   solely by the five bound artifacts, and progression is still deterministically
   expressible.

3. **Dependencies are graph edges (INV-10).** Readiness is computed from the inbound
   ordering edges (`execution`/`data`/`conditional`/`synchronization`); approval and
   recovery edges are not ordering dependencies. The Orchestrator reads the graph; it
   never builds a separate dependency graph.

4. **Approval enforces ADR-004's single taxonomy.** Planning *identifies* gates (graph
   `approval` node constraints + `policies['approval_gates']`); Orchestration *enforces*
   them with the taxonomy on the Execution Strategy: automatic ⇒ granted; otherwise
   requested (a gated, dependency-satisfied node becomes `waiting`); an out-of-band
   rejection blocks the node and its downstream.

5. **Candidates only, never allocation (INV-37).** Runtime Requests carry the
   Strategy's capability-based `runtime_policy`, the required capabilities, and —
   via the frozen `HarnessRegistry` Protocol's `discover_by_capability` — the harness
   *candidates* that advertise them (sorted). No provider is selected, reserved, or
   allocated; allocation is a later phase.

6. **Reuse of the Phase 2 persistence mechanism.** Sessions, dependency/queue/approval
   state, and Harness/Runtime requests are persisted through instances of the same
   Phase 2 `InMemoryRepository` generic; the emitter is the infrastructure context. No
   new persistence mechanism was created and `nexus_infra` was not modified.

7. **Injected, deterministic event timestamps.** Emitted events carry a timestamp from
   an injected `TimestampSource` (fixed in tests). The produced *value objects* carry
   no timestamp, so they stay deterministic regardless of the clock (INV-17).

## 3. What was deliberately NOT built (out of scope)

Harness execution, Runtime execution/allocation, AI providers, Claude/Gemini
integration, shell/Git operations, repository editing, Recovery, Knowledge,
Reflection, scheduling, and APIs. The Orchestrator's outputs are the inputs to the
Harness layer that follows; it consumes the infrastructure without modifying it.

## 4. Validation gate (all met)

| Gate criterion | Result |
|---|---|
| Execution Session created | ✅ binds Goal/Context/Plan/Graph/Strategy by reference |
| Dependencies resolved | ✅ satisfied/pending/blocked, readiness only |
| Queue constructed | ✅ deterministic, topologically ordered |
| Approval gates respected | ✅ ADR-004 taxonomy → granted/requested/rejected |
| Harness Requests generated | ✅ one per ready node, runtime-independent |
| Runtime Requests generated | ✅ requirements + candidates (no allocation) |
| Events emitted | ✅ session/approval/dependency/ready/queued/harness/runtime/completed, failed-on-error |
| Persistence succeeds | ✅ via Phase 2 repositories |
| Existing phases remain green | ✅ 193 + 180 + 149 + 156 unchanged |
| No architectural invariant violated | ✅ no ADR/contract/`nexus_core`/`nexus_infra` change |

Coverage: `nexus_orchestration` ~98.5% (branch), ≥95 floor. Full suite: 851 tests,
`mypy --strict` clean, `ruff` clean.

## 5. Design observations (for future architectural review — NOT applied)

- **O-7 — Execution Session / Harness Request / Runtime Request have no frozen core
  contract.** Doc 07 lists Execution Sessions and Runtime Assignments as Orchestration
  *outputs*, but `nexus_core` defines no contract/domain model for them, so they ship as
  orchestration-layer value objects (as `PlanningResult` / `ContextResult` did for their
  layers). *Recommendation:* if these objects need to cross layers (e.g. the Harness
  phase consumes Harness Requests, Supervision reads sessions), a future contract-freeze
  pass should promote them to ratified contracts. Low urgency.

- **O-8 — A Harness Registry implementation has no dedicated home yet (mirrors O-3/O-6).**
  No registry phase exists, so a deterministic reference `InMemoryHarnessRegistry`
  (implementing the frozen `HarnessRegistry` Protocol) ships in `nexus_orchestration`. The
  Runtime Request Builder depends only on the Protocol (dependency inversion), so it is
  swappable. *Recommendation:* a future Registry phase (or a `nexus_infra` extension)
  should own the concrete registries; Orchestration would consume them by injection. Low
  urgency.

- **O-9 — Runtime *allocation* is intentionally deferred.** Doc 07 says Orchestration
  *assigns* runtimes; this phase stops at producing runtime *requirements + candidates*
  because the prompt defers allocation (and the Harness layer that performs it) to a later
  phase. The seam is the `candidate_harness_refs` on each Runtime Request. No action now.

Neither observation blocks Phase 5 or requires action now.
