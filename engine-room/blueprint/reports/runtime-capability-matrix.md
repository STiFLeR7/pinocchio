# Runtime Capability Matrix

This document provides a feature-by-feature capability matrix comparing the three target operational runtimes: Gemini CLI, Claude Code, and Nexus Agent.

---

## 1. Capability Matrix Table

| Operational Dimension | Gemini CLI | Claude Code | Nexus Agent |
| :--- | :--- | :--- | :--- |
| **Execution Model** | Batch CLI Command Run | Interactive CLI Tool (NPM) | Autonomous Multi-step API Loop |
| **Subprocess Spawning** | Yes (OS Shell wrap) | Yes (NPM / Node execution) | No (API network execution) |
| **API-Based Run** | No (Local CLI wrapper) | No (Local CLI wrapper) | Yes (OpenRouter/custom API) |
| **Interactive Prompts** | No (Batch execution) | Yes (Terminal PTY/UI prompts) | No (Automated tool loop) |
| **Log Streaming** | Yes (stdout/stderr piping) | Yes (ANSI colors, PTY stdout) | No (Event/action log traces) |
| **Checkpointing** | Yes (Manual stage saves) | Yes (Step state checkpoints) | Yes (State & plan serialization) |
| **Heartbeats** | Yes (Periodic task updates) | Yes (Periodic process poll) | Yes (Iteration loop heartbeat) |
| **Artifact Capture** | `stdout`, `stderr`, `summary`, `diff` | `stdout`, `stderr`, `patches`, `diff` | `generated_files`, `event_traces` |
| **Summarization** | Yes (Post-run LLM synthesis) | Yes (Post-run LLM synthesis) | Yes (Continuous execution log summary)|
| **State Recovery** | Yes (Restart command reload) | Yes (Resume previous step) | Yes (Restore planning graph/memory) |
| **Governance Validation**| Pre-run path and branch filters| Path, branch, and command checks| Dynamic runtime tool-usage policies|

---

## 2. Key Insights from the Matrix

1. **Subprocess vs. API Boundary**:
   * Gemini CLI and Claude Code are **Subprocess CLI runtimes**. They execute as local OS shell commands, outputting raw `stdout` and `stderr` streams, and interact with the filesystem directly.
   * Nexus is an **API-Based Agent runtime**. It runs as an autonomous agent reasoning loop. It calls remote models to select tools, outputs JSON response payloads, and manages memory state. It does not output standard OS streams.

2. **Interactivity Challenge**:
   * Claude Code frequently asks for user confirmation (e.g. "Do you want to run this command?"). Validating it requires a pseudo-terminal (PTY) emulation layer to inspect stream indicators.
   * Gemini CLI and Nexus run fully unattended.

3. **Governance Discrepancy**:
   * CLI runtimes are validated *pre-run* by checking the command string.
   * Agent runtimes cannot be validated solely pre-run, because their actions are generated *dynamically* inside the agent loop. Governance of agents requires monitoring tool invocations *during* the execution loop (runtime guarding).
