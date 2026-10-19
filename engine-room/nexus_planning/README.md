# `nexus_planning` — Nexus v2 Planning Layer (Phase 3)

The first **operational-intelligence** component, built on the Phase 2
infrastructure substrate. Planning converts a validated **Goal** into a complete,
immutable, deterministic execution structure and stops there.

> Planning **prepares** work; it never performs it. Future phases decide *how* and
> *where* the prepared work runs.

It produces a **Plan**, its **Work Packages**, an **Execution Graph**, an
**Execution Strategy**, and a **Capability requirement set** — then persists them
and emits planning events. It never executes, supervises, validates, selects a
runtime, allocates a provider, or recovers (INV-03, INV-37).

Dependency direction is one-way: `nexus_planning → {nexus_infra, nexus_core}`.

---

## No AI — deterministic by construction

Phase 3 contains **no** AI reasoning, prompts, or LLM calls. The *decomposition*
(which work items exist, how they depend, what capabilities they need) arrives as
an explicit, immutable `PlanningRequest`; Planning assembles it mechanically. Every
identifier is a pure function of the Goal and item keys, so:

> **Identical Goals with identical inputs produce byte-identical Plans, Work
> Packages, and Execution Graphs.**

The seam for a future intelligent decomposer is
`DecompositionStrategy` (Phase 3 ships only `ExplicitDecompositionStrategy`).

## Layout (built in the mandated order)

```
nexus_planning/
├── requests.py               PlanningRequest / WorkItemSpec / results (the input atoms)
├── ids.py                    deterministic identifier derivation
├── events.py                 planning event builders + injectable TimestampSource
├── decomposition.py          DecompositionStrategy seam (+ Explicit impl)
├── capability_resolver.py    6 — capability resolution (+ reference registry)
├── work_package_generator.py 3 — immutable Work Package generation
├── strategy_assigner.py      5 — deterministic Execution Strategy assignment
├── execution_graph_builder.py 4 — Execution Graph construction
├── plan_builder.py           2 — Plan assembly
├── planner.py                1 — PlanningService (pipeline, persist, emit)
├── validators.py             fail-fast planning validation
└── composition.py            7 — dependency-injection wiring over the infrastructure
```

## Pipeline (PlanningService.plan)

```
Goal + PlanningRequest
   → validate goal + decomposition
   → resolve capabilities (requirements/candidates only)
   → assign Execution Strategy (coordination derived from topology)
   → generate Work Packages (immutable, by-reference context/skills/deps)
   → build Execution Graph (nodes + typed edges; DAG)
   → build Plan (refs the WPs + sibling graph)
   → validate outputs (cross-references agree)
   → persist (Phase 2 repositories)
   → emit WorkPackageCreated… / ExecutionGraphCreated / PlanCreated / PlanningCompleted
   ↳ on failure: emit PlanningFailed and raise
```

## Architecture compliance

- **INV-03** Planning never executes — no runtime/harness access here.
- **INV-37** Capability resolution returns candidates only; no provider/runtime
  selection. Required capabilities are carried as *references* on Work Package
  `skills`; `resources` is left empty (availability is not Planning's concern).
- **INV-10** The Execution Graph is a *sibling* referenced by the Plan, never
  nested; dependencies are graph edges, not a separate object.
- **INV-08/03** Goals/Plans describe outcomes/approach, never procedures.
- **ADR-003 §7** Context is carried **by reference**; Planning never builds it.

## Using it

```python
from nexus_infra import build_infrastructure
from nexus_planning import build_planning, PlanningRequest, WorkItemSpec

infra = build_infrastructure()
planning = build_planning(infra)                  # reuses infra repos + emitter

request = PlanningRequest(work_items=(
    WorkItemSpec(key="research", objective="Investigate", capability_requirements=("cap.analysis",)),
    WorkItemSpec(key="build", objective="Implement", depends_on=("research",)),
))
result = planning.service.plan(goal, request)     # deterministic, persisted, announced
result.plan, result.work_packages, result.execution_graph, result.execution_strategy
```

## What is intentionally absent (later phases)

Context Engineering, Orchestration, Runtime/Harness selection, Skill execution,
Recovery, Knowledge updates, Reflection, AI providers, and APIs. Planning's
outputs are *inputs* to those phases.

## Verification

```bash
.venv/Scripts/python.exe -m ruff check nexus_planning/ tests/unit/nexus_planning/
.venv/Scripts/python.exe -m mypy nexus_planning/
.venv/Scripts/python.exe -m pytest tests/unit/nexus_planning/ -q
# or the whole gate (all three layers):  make check
```
