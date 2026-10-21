# CLI Runtime Comparison: Gemini vs. Claude

This document compares the implementation and behavioral characteristics of the **Gemini Runtime Adapter** and the **Claude Runtime Adapter** inside the CLI execution group.

---

## 1. Lifecycle and Capabilities Comparison

Both adapters inherit from the abstract `CLIRuntimeAdapter`, sharing all core capabilities under identical governance rules:

| Capability | Gemini CLI | Claude CLI | Shared Mechanism |
| --- | --- | --- | --- |
| **Base Class** | `CLIRuntimeAdapter` | `CLIRuntimeAdapter` | Yes |
| **Execution Model** | Subprocess shell | Subprocess shell | Standard Python `asyncio.subprocess` |
| **Input Streams** | Shell command string | Shell command string | Yes |
| **Output Streams** | Captured stdout/stderr | Captured stdout/stderr | Captured and logged to `ExecutionStepRecord` |
| **Workspace Governance**| `GovernanceManager` check | `GovernanceManager` check | Enforces directory containment & command allowlists |
| **Timeout Enforcement** | Active subprocess kill | Active subprocess kill | Standard `asyncio.wait_for` handling |
| **Persisted Artifacts** | `stdout`, `summary`, `diff` | `stdout`, `summary`, `diff` | Logged as standard DB rows in `ExecutionArtifactRecord` |

---

## 2. Common Integration Patterns

Both CLI adapters delegate execution parameters to the same governance checks:
* **Timeout Verification**: Resolves from the task's execution profile.
* **Workspace Containment**: Validates that all execution commands are safe and execute inside approved workspace repositories.
* **OpenRouter Summarization**: Synthesizes command outputs into standard briefings.

---

## 3. Future Divergence

While both adapters currently execute shell commands asynchronously in a subprocess shell, future expansions can add runner-specific execution modes:
* **Gemini CLI**: Can integrate local code compilers or sandbox containers.
* **Claude CLI**: Can transition to an interactive PTY session (e.g. streaming interactive terminal sessions using `pexpect` or raw PTY streams) to support Claude Code interactive prompts.

Because they are cleanly decoupled, these changes can be implemented inside each runner class without any leakage into the core orchestrator or memory schemas.
