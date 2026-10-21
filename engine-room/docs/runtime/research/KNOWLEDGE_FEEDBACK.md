# Research Knowledge Feedback — Implementation

Milestone 6: Reflection identifies reusable research patterns, Knowledge persists them, and a second
research run's **Planning** improves by consuming Knowledge — never Reflection directly (INV-26).

## The loop

```
Run 1:  … → Reflection (reusable pattern) → Knowledge (durable Item)
Run 2:  Knowledge (read) → Planning (informed) → …
```

This is the existing `nexus_workflows` learning loop, unchanged — research simply drives it with a
research topic and carries the Knowledge store across runs.

## First execution — learning is produced

The reference research workflow decomposes into four independent phases, so Reflection sees four
operational episodes — more than enough to *confirm* a pattern (≥ 2 occurrences). It surfaces a
reusable finding (`promote the reusable successful approach on <runtime>`), which the existing
Knowledge engine's Acceptance stage independently re-verifies against the run's Validation evidence
and persists as a durable, subject-keyed Item. `ResearchBrief.findings` and `knowledge_item_ids`
surface both. On the first run, `knowledge_consumed == 0` — nothing was learned yet.

## Second execution — Planning improves through Knowledge alone

Carrying the first run's `knowledge_repositories` into a second run seeds the shared Knowledge
store. Before Planning, the coordinator serves the topic's Knowledge subject (a read-only query) and
folds the returned understanding into the `PlanningRequest` as assumptions. Planning consumes a
Knowledge **query result**, never Reflection. On the second run, `knowledge_consumed >= 1`
(`test_second_run_consumes_knowledge_from_the_first`).

```python
coordinator = ResearchCoordinator()
topic = reference_topic()
first  = coordinator.research(topic, run="k1")                                    # writes Knowledge
second = coordinator.research(topic, run="k2",
                              knowledge_repositories=first.knowledge_repositories) # reads it
assert first.knowledge_consumed == 0 and second.knowledge_consumed >= 1
```

## Learning is runtime-independent

Because Knowledge is provider-independent, learning written on one runtime informs a later run on a
*different* runtime. `test_knowledge_feedback_crosses_a_runtime_switch` writes Knowledge on Claude
and shows a subsequent Gemini run's Planning consumes it — the research understanding is about the
subject, not the runtime that produced it.

## Why INV-26 holds

Planning's real API takes no Knowledge or Reflection parameter; learning reaches it only because the
coordinator puts Knowledge-derived assumptions into the request. `nexus_planning` imports no
`nexus_reflection`, and `nexus_knowledge` imports no upstream layer, so a Knowledge consumer cannot
reach Reflection through it. The invariant is preserved by construction — and `nexus_research`,
sitting above both, changes neither.
