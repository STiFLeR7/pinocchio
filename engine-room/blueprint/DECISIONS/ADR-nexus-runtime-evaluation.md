# ADR: Nexus Agent Runtime Evaluation

## Status
**Adopt as First-Class Runtime**

---

## 1. Context & Objective

As Nexus enters Phase 3, we must expand execution capabilities beyond static command scripts to support autonomous AI runtimes. While CLI wrappers (Gemini CLI, Claude Code) are powerful for direct codebase refactoring, we need a native runtime engine that can perform multi-step planning, file search, and autonomous tool execution.

This record evaluates **Nexus Agent** as a native runtime, detailing where it fits within the Nexus Control Plane.

---

## 2. Evaluation of Nexus Agent

We evaluate Nexus across four operational dimensions:

### Dimension 1: Planning Runtime
* **Capability**: Nexus uses planning models (like Qwen-2.5-Coder or Gemini-1.5-Pro) to break complex tasks down into structured execution steps before running shell commands.
* **Fit**: Serves as the primary planner inside the execution engine. If a task description is vague, Nexus generates an execution outline and requests confirmation from the operator.

### Dimension 2: Research Worker
* **Capability**: Nexus can coordinate local file searches and external Web search tool-calling loops.
* **Fit**: Integrates with [ResearchEngine](file:///D:/nexus/nexus/intelligence/research.py) to execute background research tasks and index updates in knowledge records.

### Dimension 3: Execution Worker
* **Capability**: Nexus executes subprocess commands, catches exit codes, and handles simple errors (like missing dependencies) by adjusting its plan and retrying.
* **Fit**: Acts as a lightweight coding worker for projects that do not require full IDE-grade CLI tools.

---

## 3. Decision Rationale

We select **Adopt as First-Class Runtime**.

* **Model Agnostic**: Nexus is built on standard tool-calling APIs, allowing it to swap models (e.g. switching to a local model if API connections fail).
* **Controlled Sandboxing**: Unlike external CLI binaries (e.g., `claude-code`), Nexus runs directly within Python, allowing us to log, intercept, and block tool calls before they execute on the host shell.

---

## 4. Implementation Plan

1. Implement [NexusRuntimeAdapter](file:///D:/nexus/nexus/execution/runners/nexus.py) extending the standard base contract.
2. Build local file-system and shell command tool interfaces for Nexus.
3. Configure structured JSON outputs to record step executions in `ExecutionStepRecord`.
