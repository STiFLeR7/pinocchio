# Tutorial 04 — Working with Memory

## What you'll learn

How Nexus records what it learned from a run as durable **Knowledge**, and how to read a specific item
back by identity.

## Concept: Knowledge is a durable, typed record, not a chat transcript

Every completed run of the Constitutional Pipeline reaches the Knowledge stage, which records real,
structured fields on the `Knowledge` domain object — `type`, `understanding`, `confidence`, `freshness`,
`evidence_refs` — never a free-text "summary of what happened." This matters because it's what lets a
*later* Goal consult *earlier* Knowledge as evidence, not as a vague prior.

You don't need custom code to get a durable Knowledge store — `build_constitutional_pipeline()` wires one
by default. To read one back directly (rather than only via `run.knowledge_item_ids`), you build the
repositories explicitly and query by id:

```python
knowledge_repositories = build_knowledge_repositories()
pipeline = build_constitutional_pipeline(infra, knowledge_repositories=knowledge_repositories)
...
item = knowledge_repositories.items.get(item_id)
```

## Run it

```bash
uv run python examples/05-memory/run.py
```

Read [`examples/05-memory/README.md`](../../examples/05-memory/README.md) for the full walkthrough,
including the real field names (a documented mistake was caught and fixed while building this example —
see the README's own note on `Knowledge.type`/`.understanding` vs. an earlier, wrong assumption).

## What you should see

A Knowledge item id from the run, then that same item read back directly via `.items.get(item_id)`,
printing its real fields — not a paraphrase, the actual stored values.

## Check your understanding

- Why does `Knowledge` carry `evidence_refs` rather than embedding the evidence directly? (Same "references
  over embedding" discipline the whole domain model follows — Evidence is owned by Validation; Knowledge
  points at it by reference, never copies it.)
- If you ran the reference Goal twice with the same `run=` parameter, would you get the same
  `item_id`? (Yes — Knowledge identity here is deterministic over the Goal's own identity, matching the
  "same input, same result" guarantee Tutorial 02 already showed you for the whole pipeline.)

## Go deeper

[`docs/v2/knowledge/`](../v2/knowledge/) and [`docs/runtime/knowledge/`](../runtime/knowledge/) — design and
as-built engineering docs for the Knowledge subsystem.

## Next

[Tutorial 05 — Scheduling Work](05-scheduling-work.md)
