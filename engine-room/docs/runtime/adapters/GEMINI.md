# Gemini Runtime Adapter — Implementation

`nexus_runtime_gemini` (Milestone 2) is the second implementation of the generic
`RuntimeAdapter` protocol. It is deliberately a near-mirror of the Claude adapter — that
similarity *is* the evidence: a second model-backed runtime drops in with the same nine-concern
shape, no upstream change.

## Contract parity with Claude

| Concern | Member | Gemini behaviour |
|---|---|---|
| **A Advertise** | `descriptor()` | `RUNTIME`, identity `gemini-cli`, capabilities `code_generation`, `file_write` |
| **B Configure** | `configure(config)` | echoes config secret-free (never values) |
| **C/D/E/F/H Execute** | `execute(...)` | renders the Work Package into a prompt, drives an injected `GeminiInvoker`, normalizes each raw Gemini event |
| **I Clean up** | `cleanup()` | releases the session |

Advertising `code_generation` + `file_write` (the same abstract capabilities as Claude) is what
makes the *identical* reference Work Package eligible on Gemini — cross-runtime compatibility is a
capability-match fact, not special-casing.

## Normalization

```
TEXT      -> OutputSignal(STDOUT)
TOOL_USE  -> ProgressSignal(phase="tool_use", fraction=None)
ARTIFACT  -> ArtifactSignal(artifact_ref, kind)          # e.g. "<wp>-summary.md"
RESULT    -> TerminalSignal(COMPLETED)
ERROR     -> TerminalSignal(FAILED, error_class="provider-failure")
```

The only runtime-*specific* observable is the produced artifact: Gemini writes `summary.md` where
Claude writes `main.py`. That difference is exactly what "only runtime-specific artifacts may
differ" (Milestone 6) permits; the governance skeleton is identical.

## The two invokers

* **`StubGeminiInvoker`** — deterministic, subprocess-free; a pure function of the prompt (a
  planning turn, a `write_file` tool use, a `summary.md` artifact, a closing turn, a result).
* **`GeminiCliInvoker`** — shells to the real `gemini` CLI (`--output-format json`); the opt-in
  smoke path. Best-effort line parser: `content` → text, `tool_call` → tool use, `finish` →
  result/error. Cancellation terminates the process between lines (doc 09), and the
  kill-on-teardown `finally` guarantees no orphaned process.

## Fault mapping

A Gemini error (e.g. a safety refusal) becomes a `FAILED` terminal with the canonical
`provider-failure` `error_class` / `provider` owner — the same doc-11 mapping Claude uses, so
Validation and Recovery treat a Gemini failure identically to any other runtime failure.
