# Tutorial 07 — Replay & Recovery

## What you'll learn

Why replay and restart are the same mechanism (not two features), and why a failed execution is a governed
outcome rather than a crash. This tutorial covers the two guarantees that most distinguish Nexus from a
simple agent framework.

## Concept: replay is exact, not best-effort

State in Nexus is never stored independently — it's always a deterministic fold over the durable event log
(ADR-001). That means "replay" and "reconstruct after a restart" are literally the same function call:

```python
events = infra_2.event_store.read_all()
session = reconstruct_pipeline_session(events, request.pipeline_session_id)
```

There's no separate "restart mode" — a fresh process that reopens the same durable file and calls this
function gets back exactly the same session a live process would have. This is measured, not assumed: see
[`docs/benchmarks/persistence-and-replay.md`](../benchmarks/persistence-and-replay.md) for replay/restart
throughput at real scale.

## Concept: a failed execution still reaches Knowledge

Validation judges an execution from evidence the platform collected — never from the runtime's own claim
of success (INV-20). When that evidence says the execution failed, the pipeline doesn't crash or drop the
run silently:

```python
request = spine_reference_request(run="recovery", fail=True)
run = pipeline.coordinator.run(request)
assert run.status.value == "completed"   # still reaches Knowledge
assert not run.succeeded                 # but did not succeed
```

Recovery classifies the failure and decides a bounded continuation (e.g. `retry`); Knowledge still records
what happened, including the failure. This is deliberately unlike a stack trace or a silently-swallowed
exception — the platform always knows what happened and what it decided to do about it.

## Run it

```bash
uv run python examples/08-replay/run.py
uv run python examples/09-recovery/run.py
```

Read both example READMEs — [`08-replay`](../../examples/08-replay/README.md) and
[`09-recovery`](../../examples/09-recovery/README.md) — for their full walkthroughs.

## What you should see

For replay: an original run's stages, then the exact same stages reconstructed from a freshly reopened
durable file with zero prior in-memory state. For recovery: `status: completed` alongside `succeeded:
False`, plus recorded execution/validation/recovery decisions and a Knowledge item — even though nothing
"succeeded."

## Check your understanding

- If Recovery decides `retry`, does the platform automatically retry for you? (Recovery's decision is
  recorded and governed — whether and how a retry actually happens is a bounded, policy-mediated
  continuation, not silent, unlimited automation.)
- Why can't `SpineStatus` distinguish "succeeded" from "failed" directly? (Because "did the pipeline finish"
  and "did the work succeed" are different questions — `SpineStatus` only tracks the former; `run.succeeded`
  and `run.execution_outcomes`/`validation_decisions` answer the latter.)

## Go deeper

[`docs/internals/WALKTHROUGH-v2.md`](../internals/WALKTHROUGH-v2.md) §6 for why replay and restart are
exact rather than best-effort; [`docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md`](../v2/RC2_EXECUTION_IDENTITY_REPORT.md)
for the regression evidence that concurrent goals replay independently, not just single ones.

## Next

Pick any of: [08 — Runtime Adapters](08-runtime-adapters.md), [09 — Policy Authoring](09-policy-authoring.md)
— or continue straight to [10 — Building Your First Autonomous Workflow](10-autonomous-workflow.md) if
you've already read 04–06.
