# Autonomous Research Workflow — Implementation

`nexus_research` is a **consumer** of the Nexus control plane, not a platform extension. It
composes the existing engines into one autonomous research workflow and introduces no new
architectural layer, engine, contract, ADR, or invariant. Given a research topic it drives the
full pipeline end to end:

```
Research Goal → Context → Knowledge → Planning → Research Work Packages → Orchestration
             → Harness → Runtime Selection → Execution → Validation → Recovery
             → Reflection → Knowledge → Research Brief
```

Every stage is an existing engine's real entry point — no shortcuts.

## Package shape

```
nexus_research/
  topic.py        ResearchTopic + the four research phases (the decomposition declaration)
  workflow.py     ResearchWorkflow — build the platform WorkflowRequest (no planning logic)
  coordinator.py  ResearchCoordinator — drive the existing pipeline autonomously (Milestone 1)
  brief.py        ResearchBrief — project the WorkflowRun into a research deliverable
  recovery.py     recovery_outlook — the governed continuations via the existing engine (M5)
  session.py      ResearchSession — the immutable outcome (brief + run + replay)
```

## How it reuses the platform

The coordinator sits on top of two integration layers already built:

* **`nexus_workflows`** — the end-to-end `WorkflowCoordinator` that drives Context → … → Knowledge
  over one shared substrate. Research passes it a research-shaped `WorkflowRequest` and an adapter
  factory (the provider-substitution seam from Capability Program 2).
* **`nexus_runtime_adapters`** — the adapter registry and the deterministic `select_runtime`
  funnel. Research resolves the chosen runtime's adapter and lets the Runtime Manager select.

`ResearchCoordinator` therefore contains **no planning, execution, validation, recovery,
reflection, or knowledge logic**. It builds a request, runs the existing pipeline, and projects the
result. That is the whole point: the value is the *composition*, and the platform already provides
every part.

## Milestone 1 — the three coordination primitives

* **`ResearchWorkflow`** turns a `ResearchTopic` into the platform `WorkflowRequest` — a research
  Goal, the Capability + Skills to register, and one declared Work Item per phase. It declares
  work; it does not plan it.
* **`ResearchCoordinator`** drives the engines in order via the existing `WorkflowCoordinator`,
  choosing the runtime adapter and projecting the `ResearchBrief`.
* **`ResearchSession`** is the immutable record — topic, runtime, the raw `WorkflowRun`, the brief,
  and the Knowledge repositories (so a later run consumes what this one learned). `replay()` is the
  existing log reconstruction, unchanged.

## Milestone 2 — decomposition by the existing Planning engine

The topic declares four phases — **gather sources, summarize evidence, compare findings, generate
briefing** — as `WorkItemSpec`s. The existing Planning engine (no special-case planner) turns them
into Work Packages and an Execution Graph. Each phase requires the abstract `code_generation`
capability every runtime advertises, so the same research Work Package is eligible on any runtime
(a capability-match fact, not special-casing). The verification asserts Planning produced exactly
four Work Packages — one per declared phase.

## The Research Brief

The "Research Brief" is a **projection** of the `WorkflowRun`, not a new artifact type: the sources
gathered (gather-phase execution artifacts), the briefing produced (generate-phase artifacts), the
Validation evidence collected, the governed decisions, the reusable findings Reflection surfaced,
and the Knowledge persisted. It references everything by id (INV-27) and duplicates nothing. A
brief is `is_actionable` when it is validated and produced a briefing artifact.
