# Nexus Briefings — Pipeline

`nexus_briefings` is a **consumer** of the Nexus control plane, not a platform extension. It turns
governed execution, validated evidence, reflection, and knowledge into production-quality
operational briefings, and introduces no new architectural layer, engine, contract, ADR, or
invariant. Given a brief type the `BriefingCoordinator` drives the full pipeline end to end:

```
Brief Request → Context → Knowledge → Planning → Execution → Validation → Recovery
             → Reflection → Knowledge Update → Brief Composer → Rendered Brief
```

Every stage is an existing engine's real entry point — no shortcuts. This marks the transition from
building the platform to delivering user-facing capabilities powered by it.

## Package shape

```
nexus_briefings/
  brieftype.py    BriefType + BriefSection + the four supported products (the decomposition config)
  workflow.py     BriefingWorkflow — build the platform WorkflowRequest (no planning logic)
  coordinator.py  BriefingCoordinator — drive the existing pipeline and compose the brief (M1)
  composer.py     BriefComposer — project the WorkflowRun into a Brief from validated evidence (M3)
  document.py     Brief + BriefSectionView — the composed briefing (a projection, by reference)
  renderers.py    Markdown / HTML / JSON renderers + the render() dispatcher (M4)
  session.py      BriefingSession — the immutable outcome (brief + run + render + replay)
```

## How it reuses the platform

The coordinator sits on top of the two integration layers already built:

* **`nexus_workflows`** — the end-to-end `WorkflowCoordinator` that drives Context → … → Knowledge
  over one shared substrate. Briefings pass it a briefing-shaped `WorkflowRequest` and an adapter
  factory (the provider-substitution seam from Capability Program 2).
* **`nexus_runtime_adapters`** — the adapter registry and the deterministic `select_runtime`
  funnel. Briefings resolve the chosen runtime's adapter and let the Runtime Manager select.

`BriefingCoordinator` therefore contains **no planning, execution, validation, recovery,
reflection, or knowledge logic**. It builds a request, runs the existing pipeline, composes the
`Brief`, and renders it. The three Milestone-1 primitives are exactly this thin:

* **`BriefingWorkflow`** turns a `BriefType` into the platform `WorkflowRequest` — a briefing Goal,
  the Capability + Skills to register, and one declared Work Item per section. It declares work; it
  does not plan it (the existing Planning engine decomposes it — INV-04).
* **`BriefingCoordinator`** drives the engines in order via the existing `WorkflowCoordinator`,
  chooses the runtime adapter, and composes/renders the result.
* **`BriefingSession`** is the immutable record — brief type, runtime, the raw `WorkflowRun`, the
  composed `Brief`, and the Knowledge repositories (so a later generation consumes what this one
  learned). `render()` and `replay()` are pure projections; replay is the existing log
  reconstruction, unchanged.

## Participating engines

A single generation invokes all ten control-plane engines
(`session.timeline.distinct_engines()`): Context Engineering, Knowledge (read), Planning,
Orchestration, Harness, Runtime, Execution, Validation, Recovery, Reflection, and Knowledge (write)
— then the Brief Composer and a renderer produce the delivered artifact. The end-to-end test
`test_briefing_invokes_every_engine_and_decomposes_into_sections` asserts the full engine set and
that Planning produced one Work Package per declared section.
