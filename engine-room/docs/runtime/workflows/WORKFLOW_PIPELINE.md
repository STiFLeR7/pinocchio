# Workflow Pipeline -- Implementation

`nexus_workflows` proves the Nexus control plane is **one coherent system**, not ten independently
tested parts. It composes every implemented engine into a complete Goal->Knowledge flow using only
their existing public APIs. It introduces no new architecture, engine, contract, ADR, or invariant.

## Package shape

```
nexus_workflows/
  request.py      WorkflowRequest -- the immutable description of one execution
  reference.py    reference_request() -- the deterministic reference workflow (Milestone 2)
  pipeline.py     PipelineBuilder / Pipeline -- wire every engine over one substrate (Milestone 1)
  projection.py   project_intake() -- the one sanctioned Harness->Runtime seam
  timeline.py     WorkflowTimeline / StageRecord / TimelineRecorder -- cross-layer history (Milestone 3)
  coordinator.py  WorkflowCoordinator / WorkflowRun -- drive the engines in order (Milestone 1/2/5/6)
  executor.py     PipelineExecutor + reconstruct() -- run + replay from the log (Milestone 1/4)
```

## The three orchestration primitives (Milestone 1)

- **`PipelineBuilder`** wires the ten engines over a single `InfrastructureContext` and a single
  injected `TimestampSource`, so every engine appends to one authoritative event log and one
  deterministic clock (ADR-001, INV-17). It contains no business logic. A `Pipeline` hosts one
  execution (engine ids are deterministic per Goal); pass shared `knowledge_repositories` to carry
  learning across executions.
- **`WorkflowCoordinator`** drives the engines in order for one `WorkflowRequest`, performing only
  the two boundary adaptations (Harness->Runtime projection, Reflection->Knowledge candidate
  adaptation) and recording the timeline. Every step is a call to an existing engine entry point.
- **`PipelineExecutor`** is the top-level entry: `execute(request)` runs the coordinator;
  `replay()` reconstructs the operational history from the event log alone.

## Execution order (the full chain)

```
Goal
 -> Context Engineering  service.engineer(goal, ContextRequest)            -> ContextPackage
 -> [Knowledge read]     engine.serve(KnowledgeQuery)                      -> prior understanding
 -> Planning             service.plan(goal, PlanningRequest)               -> Plan + WorkPackages + ExecutionGraph + ExecutionStrategy
 -> Orchestration        service.orchestrate(OrchestrationRequest)         -> HarnessRequests + RuntimeRequests (ready queue)
 -> Harness              service.compile(CompilationRequest)               -> ExecutionPackages + ExecutionManifests
 -> [projection]         project_intake(package, runtime_request, manifest)-> RuntimeIntake
 -> Runtime              manager.prepare(PreparationRequest)               -> RuntimeSession @ READY
 -> Execution            engine.execute(session, adapter, work_package)    -> ExecutionResult
 -> Validation           engine.validate(result, work_package, events)     -> ValidationReport
 -> Recovery             engine.recover(report, result, events)            -> RecoveryPlan
 -> Reflection           engine.reflect(scope, results, reports, plans)    -> ReflectionReport (candidates)
 -> [Knowledge write]    engine.ingest(KnowledgeCandidate)                 -> durable Knowledge Item
```

The reference workflow decomposes the Goal into **two independent work items** so both become ready
nodes -- yielding two operational episodes, which is what lets Reflection *confirm* a pattern and
propose a Knowledge Candidate (Milestone 5/6). Each item requires the `code_generation` capability
the Claude runtime advertises, so orchestration offers the runtime as a candidate and selection
succeeds.

## What the coordinator adapts (and only this)

1. **Harness -> Runtime projection** (`project_intake`): Runtime is deliberately isolated from
   upstream types (it imports only `{nexus_core, nexus_infra}`), so a compiled `ExecutionPackage`
   is projected by value into the `nexus_core`-only `RuntimeIntake` -- the seam `nexus_runtime`
   documents as "assembled at the integration boundary". References only (INV-27).
2. **Reflection -> Knowledge adaptation**: an advisory `KnowledgeCandidate` from the Reflection
   Report is rebuilt as a `nexus_knowledge` candidate with validated evidence provenance, then
   ingested. `nexus_knowledge` imports no Reflection; the coordinator adapts by value.

Everything else is an unmodified engine call.

## Registration bookkeeping (existing registries, no engine change)

The coordinator registers the run's inputs into the **existing** registries before driving:
Capabilities into the Planning capability registry and Harness capability source; Skills into the
Harness skill source; the compiled ContextPackage / ExecutionStrategy / WorkPackages into the
Harness sources; and the runtime descriptor into both the Orchestration harness registry (so it is
offered as a candidate, INV-37) and the Runtime registry (with a `capacity` matching the ready-node
count, a runtime configuration value, not a contract change).

## Verification

`tests/integration/test_workflow_pipeline.py` proves: every engine is invoked
(`distinct_engines() == all ten`), every event persists to the shared log, replay reconstructs with
no information loss, Knowledge influences run 2's planning, the failure path engages every engine,
runs are byte-identical, and no upstream layer imports `nexus_workflows`. Full gate: **2166 passed
/ 1 skipped, 99.18% coverage**; `nexus_workflows` at 100%.
