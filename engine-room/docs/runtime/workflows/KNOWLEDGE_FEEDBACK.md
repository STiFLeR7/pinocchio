# Knowledge Feedback -- Implementation

The learning loop (Milestone 5): what one execution learns, a later execution's Planning uses --
and it flows **only** through Knowledge, never through Reflection (INV-26).

## The loop

```
Run 1:  ... -> Reflection (candidates) -> Knowledge (durable Item)
Run 2:  Knowledge (read) -> Planning (informed) -> ...
```

`WorkflowCoordinator` closes it with two ordinary engine calls:

1. **Write (end of run 1).** After Reflection, the coordinator adapts each advisory candidate into
   a `nexus_knowledge.KnowledgeCandidate` with validated-evidence provenance (the run's Validation
   Report references) and calls `knowledge.engine.ingest(...)`. The Acceptance Engine independently
   re-verifies evidence and persists a durable Item keyed by the workflow's Knowledge subject.
2. **Read (start of run 2, before Planning).** The coordinator calls
   `knowledge.engine.serve(KnowledgeQuery(kind, subject))` -- a read-only query -- and folds the
   returned understanding into the `PlanningRequest` as `assumptions`
   (`prior-knowledge: <statement>`). Planning consumes a Knowledge **query result**, never
   Reflection.

## Why this preserves INV-26 (structurally)

- Planning's real API is `plan(Goal, PlanningRequest)`; it has **no** Knowledge or Reflection
  parameter. Learning reaches it only because the coordinator puts Knowledge-derived assumptions
  into the request it builds.
- `nexus_planning` imports no `nexus_reflection` (guardrail
  `test_planning_reaches_learning_only_through_knowledge`), and `nexus_knowledge` imports no
  upstream layer -- so a consumer of Knowledge cannot reach Reflection through it. The invariant is
  preserved by construction, not convention.

## Carrying Knowledge across executions

Engine ids are deterministic per Goal, so each execution uses its own event log (fresh
`Pipeline`). Durable Knowledge is carried forward by sharing the **Knowledge repositories** between
pipelines:

```python
executor1 = PipelineExecutor(PipelineBuilder().build())
run1 = executor1.execute(reference_request(run="r1"))                 # writes Knowledge

shared = executor1.pipeline.knowledge.repositories
executor2 = PipelineExecutor(PipelineBuilder(knowledge_repositories=shared).build())
run2 = executor2.execute(reference_request(run="r2"))                 # reads it
```

Both runs use one shared Knowledge `subject`, so run 2 retrieves what run 1 learned, while their
event logs stay fully independent.

## Observable improvement

`WorkflowRun.knowledge_consumed` records how many Knowledge Items informed that run's Planning:

- `run1.knowledge_consumed == 0` -- nothing learned yet;
- `run2.knowledge_consumed >= 1` -- run 2's Planning read run 1's Knowledge.

Asserted by `test_knowledge_from_run_one_influences_planning_in_run_two`. The reference workflow's
happy path yields a `REPEATED_SUCCESS` candidate ("promote the reusable successful approach");
the failure path yields `REPEATED_FAILURE` / `BOTTLENECK` / `RETRY_FREQUENCY` candidates -- both
become durable, subject-keyed Knowledge that steers future planning.
