# Tutorial 03 — Understanding the Constitutional Pipeline

## What you'll learn

Why there are exactly nine stages, why they run in a fixed order, and how to observe a run from the
outside without touching its internals.

## Concept: nine stages, one owner each

Nexus names thirteen single-owner capabilities in its Constitution (no two subsystems ever own the same
kind of decision — this is INV-02, the platform's most-repeated rule). A single Goal drives nine of them,
in this fixed order, through one call:

```
Intent → Engineering → Context → Planning → Actuation → Validation → Recovery → Reflection → Knowledge
```

`Actuation` isn't one subsystem — it's Orchestration selecting what's executable, Harness compiling it,
the Runtime Manager allocating exactly one runtime, and the Execution Engine running it, bridged together
as one pipeline stage. Everything else is exactly one named subsystem. The order is fixed because each
stage's output is the next stage's required input — Planning cannot run before Context exists, Validation
cannot judge an execution that hasn't happened yet.

## Concept: watching a run from the outside

You never have to instrument the pipeline yourself to see what it did. **Operations**
(`nexus_operations`) is a read-only observation plane over the exact same durable log every stage writes
to:

```python
operations = build_operations(pipeline.coordinator, approval, infra)
summary = operations.service.session_lookup(session_id)
# summary.status, summary.stages_completed, summary.pending_approvals
```

This is how you'd check on a long-running or scheduled goal without re-running it — Tutorial 05 uses this
exact pattern for scheduled work.

## Run it

```bash
uv run python examples/02-first-pipeline/run.py
```

Read [`examples/02-first-pipeline/README.md`](../../examples/02-first-pipeline/README.md) for the full
code walkthrough (it narrates all nine stages plus the Operations lookup) — this tutorial gives you the
concept, the example gives you the code.

## What you should see

All nine stage names printed in fixed order, then an Operations-plane summary of the same session showing
`status: completed` and the same nine stages under `stages_completed`.

## Check your understanding

- Why is Validation evidence-based rather than a self-report from the runtime? (INV-20 — Nexus never
  trusts a runtime's own claim of success; Validation judges from deterministic evidence the platform
  collected itself. Tutorial 07's Recovery example makes this concrete: a run can report `succeeded: False`
  while still `status: completed`.)
- What would happen if you called `operations.service.session_lookup()` with a session id from a *different*
  run? (You'd either get that other run's summary or a not-found result — never a merged or wrong-goal
  result; this exact boundary was hardened in RC2, see [`docs/benchmarks/guarantees.md`](../benchmarks/guarantees.md#execution-isolation-cross-goal).)

## Go deeper

[`docs/architecture/README.md`](../architecture/README.md)'s Execution Lifecycle section; the Constitution
itself, [`docs/v2/ARCHITECTURE_CONSTITUTION.md`](../v2/ARCHITECTURE_CONSTITUTION.md).

## Next

Pick any of: [04 — Memory](04-memory.md), [05 — Scheduling Work](05-scheduling-work.md),
[06 — Approval Exchange](06-approval-exchange.md), [08 — Runtime Adapters](08-runtime-adapters.md),
[09 — Policy Authoring](09-policy-authoring.md) — each branches independently from here.
