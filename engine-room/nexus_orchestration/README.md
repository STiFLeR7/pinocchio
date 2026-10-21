# `nexus_orchestration` — Nexus v2 Orchestration Layer (Phase 5)

The Orchestrator **coordinates** execution; it never performs it. Given a validated
Plan — its **Execution Graph** and **Execution Strategy** — it deterministically
decides what becomes executable, when dependencies are satisfied, when approvals are
required, what is waiting, and what has completed, then produces the
runtime-independent **Harness Requests** and **Runtime Requests** the next phase will
act on.

```
… → Planning → Execution Strategy → Orchestration → (Harness → Runtime)
```

> The Orchestrator prepares execution. Harnesses execute. This phase ends before
> execution begins.

It never executes work, edits repositories, plans, builds context, validates
outcomes, performs recovery, updates Knowledge, or invokes an LLM (doc 07
*Architectural Boundaries*). Runtime **allocation** is deferred to a later phase —
the Orchestrator produces runtime *requirements* and harness *candidates* only
(INV-37). Dependency direction is one-way: `nexus_orchestration → {nexus_infra,
nexus_core}`; it never imports `nexus_planning` or `nexus_context` (it consumes
their outputs by value/reference).

---

## No AI — deterministic by construction

Phase 5 contains **no** AI reasoning, prompts, or LLM calls and no randomness. The
work decomposition arrives as the immutable Execution Graph + Strategy; the
Orchestrator coordinates them mechanically. Every identifier is a pure function of
the bound Goal/Plan identities and node keys, so:

> **Identical Goal / Context Package / Plan / Execution Graph / Strategy produce
> byte-identical Execution Sessions, dependency state, queues, approvals, Harness
> Requests, Runtime Requests, and event streams.**

## Layout (built in the mandated order)

```
nexus_orchestration/
├── vocabulary.py            orchestration enums + canonical Reference target types
├── ids.py                   deterministic identifier derivation
├── events.py                orchestration event builders + injectable TimestampSource
├── execution_session.py     1 — Execution Session (immutable bound instance)
├── dependency_tracker.py    2 — Dependency Tracker (readiness only)
├── queue.py                 3 — Execution Queue (deterministic scheduling)
├── approvals.py             4 — Approval Coordinator (ADR-004 taxonomy)
├── harness_requests.py      5 — Harness Request Builder
├── runtime_requests.py      6 — Runtime Request Builder (candidates only)
├── registry.py              reference InMemoryHarnessRegistry (frozen Protocol)
├── validators.py            fail-fast orchestration validation
├── requests.py              OrchestrationRequest / OrchestrationResult
├── orchestrator.py          OrchestrationService (pipeline, persist, emit)
└── composition.py           dependency-injection wiring over the infrastructure
```

## Pipeline (OrchestrationService.orchestrate)

```
OrchestrationRequest (Execution Graph + Strategy [+ progress])
   → validate request + validate acyclic
   → bind Execution Session (Goal/Context/Plan/Graph/Strategy by reference)
   → coordinate approvals (taxonomy → granted/requested/rejected)
   → track dependencies (satisfied / pending / blocked; readiness only)
   → build execution queue (ready / waiting / blocked / paused / completed; topological)
   → build Harness Requests (one per ready node; runtime-independent)
   → build Runtime Requests (requirements + harness candidates; never allocation)
   → validate outputs (internally consistent)
   → persist (Phase 2 repositories)
   → emit SessionCreated / Approval* / DependencySatisfied / WorkPackageReady /
     ExecutionQueued / HarnessRequestCreated / RuntimeRequestCreated / Completed
   ↳ on failure: emit orchestration.failed and raise
```

## Architecture compliance

- **Coordination, not execution** (doc 07) — nothing here runs work or assigns a
  provider; runtime allocation is a later phase.
- **INV-37** Runtime/harness resolution returns *candidates* only (via the frozen
  `HarnessRegistry` Protocol); selection/allocation is deferred.
- **INV-10** Dependencies are Execution Graph edges; the Orchestrator reads them,
  never inventing a separate dependency graph.
- **ADR-004** Approval uses the single platform taxonomy carried on the Execution
  Strategy; Planning identifies approvals, Orchestration enforces them.
- **INV-05** The Strategy declares coordination; the Orchestrator enacts it and
  never invents coordination not declared.

## Using it

```python
from nexus_infra import build_infrastructure
from nexus_planning import build_planning, PlanningRequest, WorkItemSpec
from nexus_orchestration import build_orchestration, OrchestrationRequest

infra = build_infrastructure()
planning = build_planning(infra)
orchestration = build_orchestration(infra)        # reuses infra repos + emitter

plan = planning.service.plan(goal, PlanningRequest(work_items=(
    WorkItemSpec(key="research", objective="Investigate"),
    WorkItemSpec(key="build", objective="Implement", depends_on=("research",)),
)))
result = orchestration.service.orchestrate(OrchestrationRequest(
    execution_graph=plan.execution_graph,
    execution_strategy=plan.execution_strategy,
))
result.queue_state.ready          # nodes ready to execute
result.harness_requests           # one per ready node
result.runtime_requests           # requirements + candidates (no allocation)
```

## What is intentionally absent (later phases)

Harness execution, Runtime execution/allocation, AI providers, Claude/Gemini
integration, shell/Git operations, repository editing, Recovery, Knowledge,
Reflection, and APIs. The Orchestrator's outputs are the *inputs* to the Harness
layer that follows.

## Verification

```bash
.venv/Scripts/python.exe -m ruff check nexus_orchestration/ tests/unit/nexus_orchestration/
.venv/Scripts/python.exe -m mypy nexus_orchestration/
.venv/Scripts/python.exe -m pytest tests/unit/nexus_orchestration/ -q
# or the whole gate (all five layers):  make check
```
