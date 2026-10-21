# Knowledge Integration -- Implementation

How `nexus_knowledge` wires into the platform and how the end-to-end loop is proven.

## Composition

`build_knowledge(infrastructure, *, repositories=None, timestamps=None, policy=DEFAULT)` returns a
`KnowledgeContextBundle(infrastructure, repositories, engine)`. It reuses the Phase 2 substrate
unchanged (Milestone 7): the event emitter is the infrastructure context; Items are stored through
the pre-built `nexus_infra.KnowledgeRepository`; versions and candidates through generic
`InMemoryRepository`; the metrics sink is the infrastructure observability. Every dependency is
overridable and there is no module-level singleton -- identical to `build_recovery` /
`build_reflection`.

## Events (`knowledge.*`)

`producer="knowledge"`, `source="nexus_knowledge"`, ids carry the `know` marker (doc 07):

```
knowledge.candidate_received | candidate_accepted | candidate_rejected
knowledge.item_created | item_evolved | item_superseded | item_deprecated | item_expired | item_archived
knowledge.item_served   (optional, read-only-safe)
```

**Event id scoping (implementation refinement).** Doc 07 permits ids keyed by *subject key* **or**
*candidate identity*. Because many candidates map to one Subject Key, ingest-path events are keyed
by **candidate identity** (`evt-{candidate_id}-know-{kind}-{seq}`) so a second ingest of the same
subject never re-emits a colliding id; lifecycle transitions are keyed by
`{subject_key}-{state}`. Ids remain pure functions of stable identity (INV-16); the payload always
carries the `subject_key`. Correlation is threaded from the candidate's `correlation_identifier`
(INV-39).

## Consumption (doc 09)

Consumers (Planning / Context / Orchestration) read through `KnowledgeEngine.serve(KnowledgeQuery)`
-> `tuple[Knowledge, ...]`: Active by default, confidence-aware, kind/subject/subject-key filtered,
deterministic, side-effect-free. The returned frozen `Knowledge` value objects are immutable and
reference-based (INV-27); a consumer has no write path.

## The INV-26 boundary, structurally

`nexus_knowledge` imports only `{nexus_core, nexus_infra}`. Candidates cross the Reflection ->
Knowledge boundary **by value**: the orchestrating caller adapts a Reflection Report's advisory
candidate into a `KnowledgeCandidate` at the ingestion boundary (the G9 "adapt at the boundary"
choice). Because Knowledge imports no upstream layer, no consumer can reach Reflection *through*
Knowledge. Three guardrail tests assert this over package source:
`test_knowledge_imports_no_reflection`, `test_knowledge_imports_no_planning`,
`test_reflection_does_not_depend_on_knowledge`.

## End-to-end proof (Milestone 10)

`tests/integration/test_knowledge_pipeline.py` runs a real `ReflectionEngine` over a confirmed
(two-episode) runtime-failure history -> a repeated-failure pattern -> a Knowledge Candidate, then:

- adapts it by value and ingests it -> a durable, evidence-backed Item (`test_reflection_candidate_becomes_durable_knowledge`);
- has a Planning-style consumer read it **only** through a Knowledge query (`test_planning_style_consumer_reads_only_through_knowledge`);
- verifies Knowledge only *appends* to the log (`test_knowledge_only_appends_to_the_log`);
- verifies identical history -> identical Items and events (`test_pipeline_is_deterministic`).

## Registration

The package is registered in `pyproject.toml` (wheel packages), `Makefile` (`PACKAGES` / `TESTS` /
coverage), `.pre-commit-config.yaml` (mypy), and `.github/workflows/core-ci.yml` (ruff lint +
format, mypy, pytest, coverage). Full gate at delivery: **ruff clean, mypy strict clean (197 files),
2148 passed / 1 skipped, total coverage 99.15%** (`nexus_knowledge` at 100%).
