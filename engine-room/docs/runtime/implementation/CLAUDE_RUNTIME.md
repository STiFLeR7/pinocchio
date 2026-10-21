# Claude Runtime — the adapter, its lifecycle, and its mappings

`nexus_runtime_claude` is the **only** place "Claude" drives behavior (doc `03` §1/§3). It
implements the generic `RuntimeAdapter` protocol; RM core and the Execution Engine import
nothing from it (asserted in `tests/integration/…`).

---

## 1. Two layers: wire vs. semantics (doc 22 §3, doc 23)

```
Work Package ──▶ ClaudeRuntimeAdapter ──(prompt)──▶ ClaudeInvoker ──▶ raw Claude events
                       │  semantic normalization        │  the "wire" (transport-shaped)
                       ▼                                 ▼
                 RuntimeSignal stream            RawClaudeEvent stream
```

- **`ClaudeInvoker`** (`invoker.py`) — the wire boundary. Produces provider-vocabulary
  `RawClaudeEvent`s. Two implementations:
  - `StubClaudeInvoker` — deterministic, subprocess-free (CI/E2E). A pure function of the
    prompt; models a real session's *shape* (assistant turns → tool use → artifact →
    result). `fail=` and `hang=` variants exercise the error and cancel/timeout paths.
  - `ClaudeCliInvoker` — shells to the real `claude` CLI in `--output-format stream-json`,
    parsing JSONL into raw events; cancellation terminates the process between lines
    (graceful-then-forced, `09`). Opt-in smoke only.
- **`ClaudeRuntimeAdapter`** (`adapter.py`) — semantic normalization: raw Claude event →
  runtime-independent `RuntimeSignal`. This is the only Claude→Nexus vocabulary translation.

## 2. The nine concerns, Claude-specifically (doc 03 §2)

| # | Concern | Claude implementation |
|---|---|---|
| A | Advertise | `descriptor()` → a `RUNTIME` `HarnessDescriptor` advertising abstract capabilities `code_generation`, `file_write` (provider-independent, INV-32). |
| B | Configure | `configure()` records the working dir; echoes an **secret-free** `ConfiguredRuntime` (isolation profile, working dir, env *keys* — never values, `17` §3). |
| C | Start | `execute()` opens with a `ProgressSignal(phase="starting")`, then drives the invoker (spawn/connect happens inside the invoker). |
| D | Stream | assistant text → `OutputSignal(STDOUT)`; the CLI JSONL stream is parsed to raw text events. |
| E | Progress | a Claude tool-use → `ProgressSignal(phase="tool_use", fraction=None)` — honest **unknown** fraction (`12`); never fabricated. |
| F | Artifacts | a produced file → `ArtifactSignal` referencing an id `"{work_package}-{path}"` — an Evidence Candidate **by reference** (`13`, INV-12, ADR-003), never content. |
| G | Cancel/timeout | cooperative via the engine's `ExecutionControl`; the CLI invoker terminates/kills the process. |
| H | Terminal status | a Claude `result` → `TerminalSignal(COMPLETED)`; a Claude `error` → `TerminalSignal(FAILED, error_class="provider-failure")` (`11`). `Completed` ≠ validated (INV-20). |
| I | Clean up | `cleanup()` releases the session; the stub holds no OS resource. A cleanup crash is caught and surfaced (`07` §6), never hidden. |

## 3. Prompt rendering (INV-09)

The adapter renders the embedded **Work Package** into the prompt (identifier, objective,
priority, skills) — never a Goal or raw request (INV-09). Rendering is deterministic, so a
given Work Package always yields the same prompt (and, with the stub, the same stream).

## 4. Error mapping (doc 11)

The adapter never invents an error class. A Claude error becomes a `FAILED` terminal signal
carrying the canonical doc-11 `error_class`/`owner` (`provider-failure` / `provider`); the
engine records these in the `runtime.failed` payload. Transport-level faults (from a real
CLI) surface as the engine's `TransportError` / `ProviderError` classification.

## 5. What the adapter must never do (doc 03 §6)

It does not select itself (INV-21), decide *when* to cancel/timeout (RM/engine), grade or
validate output (Validation, INV-20), or fabricate a capability/progress value. Removing any
line of adapter reasoning must not change *what* runs or *whether* it succeeded — the driver
litmus.
