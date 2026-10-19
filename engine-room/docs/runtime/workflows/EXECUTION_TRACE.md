# Execution Trace -- Implementation

The cross-layer operational timeline (Milestone 3): one coherent execution history for a workflow
run, built purely from the authoritative event log. It is instrumentation only -- it never
influences a decision, and removing it changes visibility, never behaviour (doc 16 discipline).

## What is captured

`nexus_workflows/timeline.py` records a `StageRecord` for every engine invocation the coordinator
brackets with `enter(...)` / `complete(...)`:

| Field | Meaning |
|---|---|
| `ordinal` | stage index in execution order |
| `engine` / `label` | the engine entered, and a per-invocation label (e.g. `execution:node-draft`) |
| `entered_at` / `completed_at` | recorded timestamps (injected source, INV-17) |
| `event_index_before` / `event_index_after` | the shared-log positions bracketing the stage |
| `emitted_event_types` | the events **this** stage appended to the log, in order |
| `emitted_count` | `after - before` -- the replay-stable duration proxy |
| `artifact_refs` | the artifacts the stage produced, by id (INV-27) |
| `correlation_identifier` | the operation lineage the stage's events carry (INV-39) |

A `WorkflowTimeline` aggregates the stages: `engines()` (ordered, with repeats), `distinct_engines()`
(the participants), `artifacts()` (every produced reference), and `emitted_types()` (the full event
type stream).

## How it is recorded

`TimelineRecorder` wraps the event store's `read_all` and the clock's `now`. Each stage is a
bracket: `enter` snapshots the current log length; `complete` snapshots again and records exactly
the slice of events appended in between, plus the produced artifacts. Because the whole pipeline
runs under one `FixedTimestampSource`, timestamps are deterministic, so the honest measure of a
stage's work is `emitted_count`, not wall-clock.

## The captured trace (reference workflow, happy path)

```
context_engineering  -> context.*        artifacts: [context_package]
knowledge (read)     -> (no events)      read-only serve, 0 emitted
planning             -> work_package.created x2, execution_graph.created, plan.created, planning.completed
                        artifacts: [plan, execution_graph]
orchestration        -> orchestration.*  artifacts: [harness_request x2]
harness              -> harness.*         artifacts: [execution_package x2]
runtime              -> runtime.session_created/allocated/prepared/ready ... (x2 sessions)
execution:node-draft -> runtime.started/output/completed/destroyed   artifacts: [artifact refs]
execution:node-review-> runtime.started/output/completed/destroyed
validation:node-*    -> validation.*      artifacts: [evidence refs]
recovery:node-*      -> recovery.*
reflection           -> reflection.started/analysis_completed/report_created/completed
                        artifacts: [reflection_report]
knowledge (write)    -> knowledge.candidate_received/candidate_accepted/item_created
```

The ordering is asserted in `test_timeline_is_a_coherent_ordered_history`
(`context < planning < execution < reflection`), and total events equals the shared log length
(`test_every_event_is_persisted_to_the_shared_log`).

## Determinism

Two runs of the same request over independent pipelines produce **equal timelines**
(`test_full_pipeline_is_byte_identical_across_runs`): identical stages, identical emitted-type
streams, identical artifact references -- because every engine and the recorder are pure functions
of the request and the injected clock.
