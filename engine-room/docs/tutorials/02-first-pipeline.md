# Tutorial 02 — Running Your First Pipeline

## What you'll learn

How a Goal becomes a completed, governed, durably-recorded run — the smallest possible end-to-end example
of Nexus's core mechanism.

## Concept: Goal → Knowledge, one call

Every unit of work in Nexus starts as a **Goal** and ends, if it completes, having recorded **Knowledge** —
everything in between is the **Constitutional Pipeline**, one deterministic driver
(`nexus_workflows.spine.ConstitutionalPipeline`) that runs a fixed sequence of stages. You don't orchestrate
those stages yourself; you build the platform once (a composition root) and call one method:

```python
pipeline = build_constitutional_pipeline(infra)
run = pipeline.coordinator.run(request)
```

`request` here is a `SpineRequest` — the platform's own reference-Goal builder,
`spine_reference_request()`, gives you one that's guaranteed to work without you having to hand-construct
every field a real Goal needs.

## Run it

```bash
uv run python examples/01-hello-nexus/run.py
```

Read [`examples/01-hello-nexus/run.py`](../../examples/01-hello-nexus/) — it's under 15 lines. Read its
[README.md](../../examples/01-hello-nexus/README.md) for the line-by-line walkthrough; this tutorial won't
repeat it.

## What you should see

`status: completed`, `succeeded: True`, all nine stage names listed, and one Knowledge item identifier.
That last part is the point: even the smallest possible run produces durable, retrievable Knowledge — it's
not a side effect you opted into, it's what "completed" means.

## Check your understanding

- What does `build_infrastructure()` give you that `build_constitutional_pipeline()` needs? (The
  in-memory event store, projections, and repositories every subsystem reads from and writes to — the
  substrate the pipeline runs on top of.)
- If you ran this example twice in a row, would you get the same Knowledge item identifier both times?
  (Yes — `spine_reference_request(run="hello")`'s `run` parameter is the only thing that varies identity
  here; same input, same deterministic result.)

## Go deeper

[`docs/internals/WALKTHROUGH-v2.md`](../internals/WALKTHROUGH-v2.md) §5–7 for the pipeline in code, with a
worked example of how one Goal's identity flows through every stage.

## Next

[Tutorial 03 — Understanding the Constitutional Pipeline](03-constitutional-pipeline.md)
