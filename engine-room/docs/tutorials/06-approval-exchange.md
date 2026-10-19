# Tutorial 06 — Approval Exchange

## What you'll learn

How a gated node pauses a run, and how an operator's real decision resumes it — the platform's actual
human-in-the-loop mechanism, not a simulated one.

## Concept: Requested → Pending → Approved (or Denied)

Some work should not run without an explicit human decision. You express this on the request itself —
`gated=("review",)` marks the `"review"` node as requiring approval — and the pipeline pauses there rather
than skipping or blocking silently:

```python
request = spine_reference_request(run="approval", gated=("review",))
paused = pipeline.coordinator.run(request)
pending = exchange.publish(request.pipeline_session_id, paused.execution_state.waiting_nodes)
decision = exchange.approve(request, "node-review", decided_by="alice", reason="looks correct")
```

`ApprovalExchange` (`nexus_approval`) owns this whole lifecycle — `publish`/`approve`/`deny`/`expire`, plus
`session`/`pending`/`history`/`explanation` for inspecting it afterward. This is the same mechanism behind
every "human-governed" claim elsewhere in the documentation — not a separate demo-only path.

## Run it

```bash
uv run python examples/07-approval-exchange/run.py
```

Read [`examples/07-approval-exchange/README.md`](../../examples/07-approval-exchange/README.md) for the
full lifecycle walkthrough.

## What you should see

The pipeline pausing at the gated node, a pending approval visible via `exchange.pending(...)`, and the run
resuming to completion only after `exchange.approve(...)` is called.

## Check your understanding

- What's the difference between this and Tutorial 09's Policy Engine? (Policy decides *whether an action is
  allowed at all*, deterministically, with no human involved by default. Approval Exchange is the mechanism
  a Policy decision of `RequireApproval` hands off *to* — a human decision, not a rule evaluation.)
- Is a denied approval a crash? (No — `exchange.deny(...)` is a normal, recorded outcome, exactly the way
  Tutorial 07's Recovery example treats a failed execution as a normal, recorded outcome rather than a
  crash.)

## Go deeper

[`docs/v2/human_interaction/05_APPROVALS.md`](../v2/human_interaction/05_APPROVALS.md);
[`docs/benchmarks/guarantees.md`](../benchmarks/guarantees.md#approval-integrity) for the evidence behind
this guarantee.

## Next

[Tutorial 07 — Replay & Recovery](07-replay-and-recovery.md)
