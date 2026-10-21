# ADR: Runtime Abstraction Validation

## Status
Accepted

## Context
During Phase 3 implementation, the Gemini CLI Runtime Adapter was established as the first production runner under the [BaseRuntimeAdapter](file:///D:/nexus/nexus/execution/runners/base.py) interface contract. Before proceeding to Claude Code (AP-302) and Nexus Agent (AP-303), we conducted a contract audit to verify if `BaseRuntimeAdapter` is truly generic or contains implicit Gemini, CLI, or subprocess execution assumptions.

We observed:
1. **CLI Inputs**: The contract methods `validate(repository_path, command)` and `execute(command)` assume the target workload is represented by a single shell command string.
2. **POSIX Streams**: The contract enforces the presence of `stdout_log` and `stderr_log` attributes, which are absent or meaningless in API-based multi-step agent runtimes like Nexus.
3. **Subprocess Termination**: The `terminate()` action expects process-level termination (PIDs, shell killing) rather than remote API cancellations or connection aborts.

---

## Decision
We decide that **RuntimeAdapter requires evolution** before AP-302 implementation begins. 

We will refactor the base runtime interface contract to decouple the execution models. Specifically, we will evolve the abstraction as follows:

1. **Keep `BaseRuntimeAdapter` Generic**:
   * Contains only execution-model-agnostic methods: `initialize()`, `heartbeat()`, `checkpoint()`, `terminate()`, `summarize()`, `persist()`.
   * Removes `stdout_log` and `stderr_log` from the root abstract definition, as well as command string parameters from generic execution triggers.

2. **Introduce `CLIRuntimeAdapter`**:
   * Subclasses `BaseRuntimeAdapter`.
   * Restores `stdout_log`, `stderr_log`, and defines `execute(command: str)` and `validate(repository_path: str, command: str)`.
   * Used for subprocess-based runners (Gemini CLI, Claude Code).

3. **Introduce `AgentRuntimeAdapter`**:
   * Subclasses `BaseRuntimeAdapter`.
   * Accepts high-level task goals / prompts as inputs.
   * Exposes methods to track agent trajectories, tool invocations, and JSON response contexts.
   * Used for API-driven agents (Nexus Agent).

---

## Rationale
* **Prevents Architectural Leakage**: Avoids forcing Nexus or future API agents to implement empty/stub properties for `stdout_log` or `stderr_log`, and dummy command strings for execution.
* **Separates Governance Scopes**: Allows `CLIRuntimeAdapter` to use pre-run static filters, while `AgentRuntimeAdapter` can integrate dynamic, runtime tool call interceptors.
* **Simplifies Testing**: Simplifies mocking and validation for E2E tests by isolating the subprocess dependencies to a specific branch of the hierarchy.
