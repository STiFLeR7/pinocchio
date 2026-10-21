# Phase 3 AI Runtime Execution Strategy

This document details the operational strategy for integrating, executing, and sandboxing AI runtimes inside the Nexus Control Plane.

---

## 1. CLI Tools vs. Raw API Agents

Nexus supports two distinct classes of AI execution runtimes:

| Runtime Type | Examples | Strengths | Weaknesses |
| :--- | :--- | :--- | :--- |
| **CLI Runtimes** | `claude-code`, `gemini-cli` | Mature codebase search capabilities, built-in git operations, and quick file refactoring out-of-the-box. | Complex to sandbox, hard to parse raw ANSI output streams, and difficult to manage interactive CLI prompts. |
| **API Agents** | Nexus Agent (Custom API loop) | Structured tool calling, safe sandboxed shell executions, and clean JSON execution logs. | Requires building and maintaining custom planning and RAG search loops from scratch. |

### Subprocess Wrapper Integration Strategy
To support both types, Nexus wraps all execution runtimes in a subprocess interface. This wrapper manages execution limits, handles standard input/output streams, and enforces path restrictions via pseudo-terminal interfaces.

---

## 2. Interactive Shell Management (Claude Code)

Runtimes like `claude-code` are designed as interactive node binaries that expect a terminal connection (TTY). Standard subprocess pipes (`stdout = PIPE`) block or crash when interactive prompts occur.
* **Terminal Emulation (Pty)**: Nexus uses platform-specific terminal emulators (e.g., `pty` on Linux or pseudo-consoles on Windows) to simulate standard TTY prompts.
* **Prompt Sweeping**: The runtime adapter scans standard output streams for known interactive prompts (e.g. `[y/N]`, `approve?`), answering automatically based on task parameters to prevent hangs.

---

## 3. Sandboxing & Directory Safety

AI runtimes can write destructive commands (such as `rm -rf /` or recursive moves). Nexus secures runtime execution by applying directory restrictions:
* **Allowed Path Restraints**: Subprocess commands are executed only inside paths registered in `absolute_path` inside [RepositoryRegistryRecord](file:///D:/nexus/nexus/memory/models.py).
* **Environment Isolation**: Runtimes run in clean subshells with restricted environment variables, preventing access to host API keys or credential directories.
* **Virtualization (Future)**: Development roadmaps include wrapping CLI runtimes in lightweight Docker containers, mounting only the target repository as a local volume.
