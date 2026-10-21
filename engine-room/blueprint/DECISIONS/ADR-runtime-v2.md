# ADR: Runtime V2 Design & Refactoring Plan

## Status
Proposed

## Context
The Gemini CLI Runtime Adapter (AP-301) established our first production adapter. However, this implementation revealed that `BaseRuntimeAdapter` holds strong assumptions about shell command execution and POSIX stream captures (`stdout`/`stderr`).

To prevent architectural leakage when introducing Claude Code (which is interactive) and Nexus Agent (which runs as an API loop), we require a decoupled interface structure: **Runtime V2**.

---

## Decisions

We approve the design of Runtime V2 with the following specifications:

1. **Adapter Interface Decoupling**:
   * Evolve [BaseRuntimeAdapter](file:///D:/nexus/nexus/execution/runners/base.py) to declare only execution-agnostic lifecycle methods: `initialize()`, `heartbeat()`, `checkpoint()`, `terminate()`, `summarize()`, `persist()`.
   * Create `CLIRuntimeAdapter` inheriting from `BaseRuntimeAdapter`, defining `stdout_log`, `stderr_log`, `execute(command)`, and `validate(repository_path, command)`.
   * Create `AgentRuntimeAdapter` inheriting from `BaseRuntimeAdapter`, defining `validate_goal(goal)` and `execute_goal(goal)`.

2. **Polymorphic Database Schemas**:
   * Introduce a new table `agent_steps` in [models.py](file:///D:/nexus/nexus/memory/models.py) to store agent trajectory traces, preserving the existing `execution_steps` table for CLI-only subprocesses.
   * Standardize polymorphic types inside the `execution_artifacts` metadata column.

3. **Orchestrator Separation**:
   * Refactor [orchestrator.py](file:///D:/nexus/nexus/scheduling/orchestrator.py) to run dispatching loops checks based on adapter classes.

---

## Implementation Strategy & Action Points

We divide the next milestones into three isolated implementation blocks:

```
[ AP-302A: Runtime Refactor ]
  - Refactor base contracts & orchestrator dispatching
  - Add agent_steps table schema
       |
       +-----------------------+-----------------------+
       |                                               |
       v                                               v
[ AP-302B: Claude Runtime ]                     [ AP-303A: Nexus Runtime ]
  - Subprocess PTY integration                    - API reasoning tool loop
  - Extends CLIRuntimeAdapter                     - Extends AgentRuntimeAdapter
```

1. **AP-302A: Runtime Refactor (Core Refactor)**:
   * **Scope**: Interface definitions, database schema addition (`agent_steps`), factory routing, and orchestrator dispatch updates.
   * **Dependency**: Must complete first.
2. **AP-302B: Claude Runtime (Claude CLI)**:
   * **Scope**: Claude adapter implementation, PTY streaming, patch captures, and E2E validation.
   * **Dependency**: Depends on AP-302A.
3. **AP-303A: Nexus Runtime (Nexus API)**:
   * **Scope**: Nexus agent loop, planning steps, OpenRouter integration, trajectory logging, and E2E validation.
   * **Dependency**: Depends on AP-302A.
