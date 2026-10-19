# Shell Runtime Adapter — Implementation

`nexus_runtime_shell` (Milestone 3) is the third `RuntimeAdapter`, and the most interesting one:
a shell has **no** "assistant turn" or "tool use" vocabulary. It runs a command and surfaces
stdout/stderr and an exit code. Proving that this non-model runtime drives the pipeline
*identically* to Claude/Gemini is the strongest evidence the abstraction is truly
provider-independent — the difference is confined entirely to *normalization*.

## Contract

| Concern | Member | Shell behaviour |
|---|---|---|
| **A Advertise** | `descriptor()` | `RUNTIME`, identity `shell`, capabilities `command_execution`, `code_generation`, `file_write` |
| **B Configure** | `configure(config)` | echoes config secret-free |
| **C/D/E/F/H Execute** | `execute(...)` | renders the Work Package into a command, drives an injected `ShellInvoker`, normalizes each raw shell event |
| **I Clean up** | `cleanup()` | releases the session |

It advertises `code_generation` alongside its distinctive `command_execution` so the *same*
reference Work Package (which requires `code_generation`) is eligible on the shell — a shell can
run a code-generating command. It contains **no business logic** (the Milestone-3 constraint): it
decides nothing and grades nothing.

## Normalization — the shell's different vocabulary

```
STDOUT   -> OutputSignal(STDOUT)
STDERR   -> OutputSignal(STDERR)
ARTIFACT -> ArtifactSignal(artifact_ref, kind)     # e.g. "<wp>-output.txt"
EXIT(0)  -> TerminalSignal(COMPLETED)
EXIT(n)  -> TerminalSignal(FAILED, error_class="provider-failure")   # non-zero exit → doc-11
```

There are **no progress signals** — a shell reports none, and the adapter invents none (doc 12:
honest 'unknown' over fabricated progress). This is why a shell run emits fewer `runtime.*` events
than a model run; those events (`runtime.output` / `runtime.progress` / `runtime.artifact_emitted`)
are exactly the runtime-*variable* set the governance signature excludes (see `CROSS_RUNTIME`).

## The two invokers

* **`StubShellInvoker`** — deterministic, subprocess-free; a pure function of the command (two
  stdout lines, one produced `output.txt`, a zero exit — or, in fail mode, a stderr diagnostic and
  exit `127`).
* **`SubprocessShellInvoker`** — runs a real command via `subprocess` (`/bin/sh -c`), streaming
  stdout line by line, checking cancellation between lines, surfacing the process exit code, and
  killing any surviving process in the teardown `finally`.

## Command execution, stdout/stderr, exit codes, cancellation, timeout

All five Milestone-3 requirements are covered: command execution (`_render_command`),
stdout/stderr (two `StreamChannel`s), exit codes (the `EXIT` event → terminal + `exit_status`),
cancellation (cooperative `control.cancelled` check, enforced by the engine too), and timeout (the
engine's `deadline_steps` bound over the adapter's signal stream — provider-independent, so the
shell inherits it unchanged).
