# Phase 3 — Planning Layer: Implementation Decisions

**Status:** Implemented. **Scope:** the planning layer (`nexus_planning/`).
**Authority:** This document records *implementation decisions* only. It does not
amend any ADR, contract, or invariant — the architecture remains frozen.
Observations that might warrant future architecture review are listed in §5 with
recommendations, not applied.

Planning converts a validated Goal into a complete, deterministic execution
structure (Plan, Work Packages, Execution Graph, Execution Strategy, Capability
requirement set), persists it through Phase 2 infrastructure, and emits planning
events. It prepares work; it never performs it.

---

## 1. Component → architecture mapping

| Component (`nexus_planning/…`) | Produces / does | ADR / Invariants |
|---|---|---|
| `planner.PlanningService` | orchestrates the pipeline, persists, emits | INV-03 |
| `plan_builder.PlanBuilder` | `Plan` | ADR-003 §3.3, INV-03/08/10 |
| `work_package_generator` | `WorkPackage` (immutable) | ADR-003 §3.2, INV-09 |
| `execution_graph_builder` | `ExecutionGraph` (sibling, DAG) | ADR-003 §3.3, INV-10 |
| `strategy_assigner` | `ExecutionStrategy` (declarative) | ADR-004, INV-05 |
| `capability_resolver` | capability requirement set (candidates only) | ADR-002, INV-37 |
| `validators` | fail-fast planning validation | INV-08/10 |
| `composition` | DI wiring over `nexus_infra` | — |

## 2. Key implementation decisions

1. **Deterministic, AI-free planning.** Phase 3 forbids AI. The decomposition is
   an explicit `PlanningRequest`; Planning assembles it mechanically. Every
   identifier is a pure function of the Goal identity and item keys (`ids.py`), so
   identical inputs yield byte-identical Plans/Work Packages/graphs. The
   `DecompositionStrategy` Protocol is the seam where a future intelligent
   decomposer plugs in (only `ExplicitDecompositionStrategy` ships now).

2. **Capability resolution is candidates-only (INV-37).** The resolver consumes
   only the `CapabilityRegistry` and returns `required` / `resolved` / `missing`.
   It never touches the Harness Registry, selects a provider, or allocates a
   runtime. Required capabilities are carried as *references* on Work Package
   `skills`; `resources` is left empty (Planning declares requirements, not
   availability/selection).

3. **Reuse of the Phase 2 persistence mechanism.** Plans use the existing
   `infra.plans` repository; Work Packages, Execution Graphs, and Execution
   Strategies use instances of the same Phase 2 `InMemoryRepository` generic. No
   new persistence mechanism was created and `nexus_infra` was not modified.

4. **Deterministic coordination derivation.** The Execution Strategy's
   `CoordinationModel` is derived from the declared topology — approval ⇒
   `approval_driven`; no dependencies & >1 item ⇒ `parallel`; linear chain ⇒
   `sequential`; otherwise `hybrid` — overridable by an explicit
   `coordination_hint`. The Strategy is declarative only; it never evaluates its
   own policy (INV-05).

5. **Graph features via the contract's real fields.** Approval gates are node
   constraints + a graph approval policy; synchronization points are join nodes
   recorded in graph policy; conditional flow uses `conditional` edges + the
   `conditions` predicate list; checkpoints are declared checkpoint references.
   The graph is a sibling referenced by the Plan, never nested (INV-10), and is
   validated acyclic (Kahn's algorithm, declared loops excepted).

6. **Context by reference (ADR-003 §7).** Work Packages and graph nodes carry
   Context as a reference; Planning never builds context (that is the later
   Context Engineering phase). When no `context_ref` is supplied, a deterministic
   placeholder reference (`context-{goal}`) is used.

7. **Injected, deterministic event timestamps.** Emitted events carry a timestamp
   from an injected `TimestampSource` (fixed in tests). The produced *domain
   objects* carry no timestamp, so they stay deterministic regardless of the
   clock (INV-17).

## 3. What was deliberately NOT built (out of scope)

Context Engineering, Orchestration, Runtime/Harness selection, Skill execution,
Recovery, Knowledge updates, Reflection, AI/LLM integration, scheduling, and
APIs. Planning's outputs are inputs to those phases; it consumes the
infrastructure without modifying it.

## 4. Validation gate (all met)

| Gate criterion | Result |
|---|---|
| Goal produces a valid Plan | ✅ |
| Plan produces valid Work Packages | ✅ |
| Execution Graph is deterministic | ✅ equality across fresh runs |
| Execution Strategy assignment succeeds | ✅ topology-derived + hint override |
| Capability requirements are generated | ✅ required/resolved/missing |
| Planning events emitted | ✅ WP/graph/plan/completed, failed-on-error |
| Persistence succeeds | ✅ via Phase 2 repositories |
| Existing phases remain green | ✅ 193 + 180 unchanged |
| No architectural invariant violated | ✅ no ADR/contract/`nexus_core`/`nexus_infra` change |

Coverage: `nexus_planning` ~99% (branch), ≥95 floor. Full suite: 522 tests,
`mypy --strict` clean, `ruff` clean.

## 5. Design observations (for future architectural review — NOT applied)

- **O-3 — A Capability Registry implementation has no dedicated home yet.** Phase
  2 (infrastructure) did not build registries; Planning needs one, so a reference
  `InMemoryCapabilityRegistry` (implementing the frozen `nexus_core`
  `CapabilityRegistry` Protocol) ships in `nexus_planning`. The resolver depends
  only on the Protocol (dependency inversion), so this is swappable.
  *Recommendation:* a future **Registry phase** (or an extension of `nexus_infra`)
  should own the concrete registries (Capability/Harness/Skill/Policy); Planning
  would then consume them by injection. Low urgency.

- **O-4 — `WorkPackage.context` is required but Context Engineering is a later
  phase.** Planning satisfies the required field with a by-reference placeholder.
  *Recommendation:* none structural — this is the intended ADR-003 §7 by-reference
  model; once Context Engineering exists, the planner accepts its real context
  reference. Recorded so the placeholder is not mistaken for a gap.

Neither observation blocks Phase 3 or requires action now.
