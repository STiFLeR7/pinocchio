# Claude Runtime Adapter — Implementation

`nexus_runtime_claude` is the reference adapter — the one every other runtime mirrors. It was
implemented in the Runtime vertical slice and is unchanged by Capability Program 2; it is
documented here so the nine-concern contract Gemini and Shell follow is stated once.

## The nine concerns (doc 03)

The generic `RuntimeAdapter` protocol (`nexus_execution.adapter`) has four members onto which
doc 03's nine concerns A–I map. The Claude adapter satisfies them and **decides nothing**:

| Concern | Member | Claude behaviour |
|---|---|---|
| **A Advertise** | `descriptor()` | `RUNTIME` descriptor, identity `claude-code`, capabilities `code_generation`, `file_write` |
| **B Configure** | `configure(config)` | echoes `working_dir` / `env_keys` / `isolation_profile` **secret-free** (values live in `.env`, doc 17 §3) |
| **C/D/E/F/H Execute** | `execute(...)` | renders the Work Package into a prompt, drives an injected `ClaudeInvoker`, and **semantically normalizes** each raw Claude event into a runtime-independent signal |
| **I Clean up** | `cleanup()` | releases the session; the stub holds no OS resource |

## Semantic normalization (doc 22 §3)

The adapter is the *only* place the word "Claude" drives behaviour. `_normalize` maps each raw
provider event onto a provider-independent signal:

```
TEXT      -> OutputSignal(STDOUT)
TOOL_USE  -> ProgressSignal(phase="tool_use", fraction=None)   # honest 'unknown' (doc 12)
ARTIFACT  -> ArtifactSignal(artifact_ref, kind)                # by reference (INV-27, doc 13)
RESULT    -> TerminalSignal(COMPLETED)
ERROR     -> TerminalSignal(FAILED, error_class="provider-failure")  # doc-11 error model
```

## Two invokers (the wire boundary)

`invoker.py` isolates the transport (doc 23):

* **`StubClaudeInvoker`** — deterministic, subprocess-free; a pure function of the prompt, so two
  runs of the same Work Package yield byte-identical `runtime.*` events under a fixed clock. This
  is the CI/E2E path (the program's determinism requirement).
* **`ClaudeCliInvoker`** — shells to the real `claude` CLI in `stream-json` mode; the opt-in smoke
  path (`NEXUS_CLAUDE_SMOKE=1`). Only the *shape* of the event stream is asserted, never the
  model's text.

## What makes it substitutable

RM core and the Execution Engine import nothing from this package; they drive it only through the
protocol. Swapping in Gemini or Shell therefore changes nothing upstream — the proof carried by
`CROSS_RUNTIME`.
