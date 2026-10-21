# Operational Timeline (Milestone 2)

`TimelineCoordinator.build(record)` projects a submission's `WorkflowTimeline` into a unified,
operator-facing `OperationalTimeline`. It is pure instrumentation over the authoritative event log —
it decides nothing, and removing it changes visibility, never behaviour.

## Operator phases

Each engine stage is mapped to an operator phase; Orchestration / Harness / Runtime fold into one
**Runtime** phase, and the two Knowledge stages (read/write) both surface as **Knowledge**:

```
Context → Knowledge → Planning → Runtime → Execution → Validation → Recovery → Reflection
```

A briefing submission appends a **Briefings** phase linking to the validated briefing artifacts, so
the timeline covers the mission's full display list: Context, Planning, Runtime, Execution,
Validation, Recovery, Reflection, Knowledge, Briefings.

## Every entry links back to persisted evidence

A `TimelineEntry` carries two references into persisted state (INV-27 — references, never content):

* `evidence_refs` — the artifact references the stage produced (execution deliverables, validation
  evidence, briefing artifacts);
* `first_event_index` + `event_count` — the span of the authoritative event log the stage appended.

So even a stage that produces no artifact (a Knowledge read, a Runtime prepare) still links to the
persisted events it emitted. `OperationalTimeline.evidence()` returns every artifact reference across
the run, and `total_events` is the authoritative event count.

## Replay validation

Replay is the existing log reconstruction, unchanged: `OperatorSession.replay(submission_id)` calls
`nexus_workflows.reconstruct` over the submission's event log and returns a `ReplayTimeline`. The
tests assert:

* `replay.total_events == len(record.run.events)` — no information loss;
* `replay.event_ids == tuple(e.identifier for e in record.run.events)` — exact ordered
  reconstruction;
* `OperationalTimeline.total_events == len(record.run.events)` — the timeline's count matches the
  persisted log;

and that two operator sessions running the same submission produce byte-identical event logs
(deterministic, INV-16 / INV-17).

## Traceability

The timeline is the operator's spine: from a phase entry to its artifacts, from artifacts to the
Validation evidence that judged them (`explorer.validation_reports()`), from a submission to its
plan and work packages, and from any submission back to a full event-log replay. Nothing in the
timeline is fabricated — every field is read from the persisted `WorkflowRun`.
