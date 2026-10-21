# `nexus_context` — Nexus v2 Context Engineering Layer (Phase 4)

The first half of the **operational-intelligence pipeline**, built on the Phase 2
infrastructure substrate. Context Engineering converts a validated **Goal** plus
available operational information into a single, immutable, validated **Context
Package** and stops there.

> Context Engineering turns incomplete operator intent into complete operational
> *understanding*. It never plans, selects a runtime, executes, validates execution,
> invokes an AI provider, or mutates Knowledge.

The pipeline becomes:

```
Goal → Context Engineering → Context Package → Planning → Work Packages → Execution Graph → Execution Strategy
```

so **Planning no longer operates on a raw Goal** — it consumes the validated
Context Package by reference (`PlanningRequest.context_ref`; see
`context_reference`). Dependency direction is one-way:
`nexus_context → {nexus_infra, nexus_core}`. It never imports `nexus_planning` —
Context Engineering is *upstream* of Planning.

---

## No AI — deterministic by construction

Phase 4 contains **no** AI reasoning, prompts, or LLM calls. The raw context arrives
as explicit, immutable `RawContextFragment` values (surfaced by injected collectors),
and the policies governing relevance and freshness arrive on an immutable
`ContextRequest`. Every identifier is a pure function of the Goal and the inputs'
stable handles, so:

> **Identical Goals with identical inputs produce byte-identical Context Packages,
> items, conflicts, and event streams.**

The seam for real source collectors (repository, Drive, calendar, knowledge base, …)
is the `ContextCollector` Protocol; Phase 4 ships only deterministic, I/O-free
reference collectors.

## Layout (built in the mandated order)

```
nexus_context/
├── categories.py            context vocabularies (8 categories, 5 sources, freshness, conflict kinds)
├── requests.py              ContextRequest / RawContextFragment / ContextItem / results
├── ids.py                   deterministic identifier derivation
├── events.py                context event builders + injectable TimestampSource
├── collectors.py            1 — Context Collectors (Protocol + reference collectors, DI)
├── normalizer.py            2 — Normalization (heterogeneous → canonical items)
├── conflict_detector.py     3 — Conflict Detection (surface, never resolve)
├── relevance.py             4 — Relevance Ranking (deterministic, explicit rules)
├── freshness.py             5 — Freshness Validation (valid/stale/expired via timestamps + policy)
├── builder.py               6 — Context Package Builder (immutable)
├── validators.py            fail-fast validation + conflict surfacing
├── service.py               ContextEngineeringService (pipeline, persist, emit)
└── composition.py           dependency-injection wiring over the infrastructure
```

## Pipeline (ContextEngineeringService.engineer)

```
Goal + ContextRequest
   → validate goal + request
   → collect (run injected collectors → raw fragments)
   → normalize (fragments → canonical, sorted ContextItem set)
   → detect conflicts (duplicate / contradiction / stale / missing dependency — surfaced)
   → rank relevance (deterministic integer rules)
   → validate freshness (valid / stale / expired against an explicit instant + policy)
   → build Context Package (8 categories, confidence, known_unknowns, validation_status)
   → validate outputs (goal_ref agrees with the Goal)
   → persist (Phase 2 repository)
   → emit ContextCollectionStarted / Collected / Validated / PackageCreated / Completed
   ↳ on failure: emit ContextEngineeringFailed and raise
```

## Architecture compliance

- **One Context Package per Goal**; `goal_ref` is single-valued (contract §6).
- **INV-06** Knowledge is consumed read-only; Context Engineering never mutates it.
- **INV-12** Evidence/artifacts are referenced by id, never embedded.
- **ADR-002** Resource entries are described capabilities by reference — no live
  provider/runtime/health state.
- **No procedural content** — the package describes *what is known and required*,
  never *how to execute* (preserves INV-03/INV-08 at the context seam).
- **Surface, don't resolve** — duplicate/contradictory/stale/missing context is
  reported in `known_unknowns` / `validation_status`, never silently corrected.

## Using it

```python
from nexus_infra import build_infrastructure
from nexus_context import (
    build_context_engineering, ContextRequest, RawContextFragment,
    ContextCategory, ContextSource, context_reference,
)

infra = build_infrastructure()
context = build_context_engineering(infra)          # reuses infra repo + emitter

request = ContextRequest(fragments=(
    RawContextFragment(source=ContextSource.WORKSPACE, category=ContextCategory.WORKSPACE,
                       key="repo", payload={"name": "nexus"}),
))
result = context.service.engineer(goal, request)    # deterministic, persisted, announced

# Feed the package into Planning by reference (no coupling between layers):
from nexus_planning import build_planning, PlanningRequest, WorkItemSpec
planning = build_planning(infra)
plan = planning.service.plan(goal, PlanningRequest(
    work_items=(WorkItemSpec(key="build", objective="Implement"),),
    context_ref=context_reference(result.package),
))
```

## What is intentionally absent (later phases)

AI reasoning, prompt engineering, Orchestration, Runtime/Harness selection, Skill
execution, Recovery, Knowledge updates, Reflection, scheduling, and APIs. Context
Engineering's output is the *input* to Planning and the phases beyond it.

## Verification

```bash
.venv/Scripts/python.exe -m ruff check nexus_context/ tests/unit/nexus_context/
.venv/Scripts/python.exe -m mypy nexus_context/
.venv/Scripts/python.exe -m pytest tests/unit/nexus_context/ -q
# or the whole gate (all four layers):  make check
```
