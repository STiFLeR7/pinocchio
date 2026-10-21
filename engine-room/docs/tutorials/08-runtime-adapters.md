# Tutorial 08 — Runtime Adapters

## What you'll learn

How Nexus runs work against an actual LLM CLI or shell process without the rest of the pipeline knowing or
caring which one — the platform's real extensibility seam.

## Concept: one protocol, several interchangeable implementations

Every runtime — Claude Code, Gemini CLI, a local shell process — implements the same `RuntimeAdapter`
protocol (`nexus_execution.adapter`). Nothing above the adapter layer branches on provider identity. Swapping
one runtime for another is a single composition-root parameter, not a code change anywhere else:

```python
def _shell_adapter_factory(request: SpineRequest) -> ShellRuntimeAdapter:
    return ShellRuntimeAdapter(invoker=StubShellInvoker(fail=request.fail))

pipeline = build_constitutional_pipeline(infra, adapter_factory=_shell_adapter_factory)
```

This is the same seam a new runtime provider would plug into — see
`docs/runtime/adapters/ADAPTER_REGISTRY.md` for the generic registry/discovery layer.

## Run it

```bash
uv run python examples/04-runtime-selection/run.py
```

Read [`examples/04-runtime-selection/README.md`](../../examples/04-runtime-selection/README.md) — note
its own observation that `ShellRuntimeAdapter`'s advertised capabilities happen to overlap with what the
reference Goal needs, which is exactly why a one-line adapter swap is enough here.

## What you should see

The identical pipeline, identical nine stages, completing successfully — but dispatched through
`ShellRuntimeAdapter` instead of the default Claude adapter, provable by inspecting which adapter actually
ran.

## Check your understanding

- What would happen if you swapped in an adapter whose advertised capabilities didn't cover what the Goal
  needs? (Orchestration/Runtime Manager's own resolve→match→allocate funnel wouldn't be able to satisfy the
  request — this is the same capability-resolution mechanism ADR-002 established, not something a runtime
  swap bypasses.)
- Why does the platform never let Orchestration import `nexus_runtime` directly? (Architecture-fitness
  guardrail tests enforce this dependency boundary — see
  [`docs/benchmarks/quality-gates.md`](../benchmarks/quality-gates.md) for a real example of this guardrail
  catching a violation during RC1's own entrypoint construction.)

## Go deeper

[`docs/v2/runtime/00_RUNTIME_OVERVIEW.md`](../v2/runtime/00_RUNTIME_OVERVIEW.md) and the rest of
`docs/v2/runtime/`; [`adr/ADR-002.md`](../../adr/ADR-002.md) (Registry Architecture — the decision that
makes "a Runtime is a Harness of category Runtime" true).

## Next

[Tutorial 09 — Policy Authoring](09-policy-authoring.md)
