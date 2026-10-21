# Nexus Runtime Classification Report

This report evaluates and classifies the **Nexus Agent Framework** to determine its runtime classification category in the Nexus architecture.

---

## 1. Evaluation of Classification Options

We evaluated the Nexus runtime against the following candidate classifications:

1. **CLI Runtime**:
   * *Description*: Wraps local command-line binaries (e.g. `gemini`, `claude`).
   * *Nexus fit*: **Poor**. Nexus does not run as a local command-line binary that executes single commands. It executes as a multi-step agent reasoning loop calling remote APIs.

2. **Agent Runtime**:
   * *Description*: Runs an autonomous loop that queries models, reasons about goals, decides on tool calls (e.g. file search, editing, execution), and observes the outputs.
   * *Nexus fit*: **Excellent**. Nexus's core operational model is an autonomous agent loop (ReAct loop / tool-use trajectory).

3. **Research Runtime**:
   * *Description*: Performs background data retrieval, searches the web, fetches articles, and compiles facts.
   * *Nexus fit*: **Partial**. While Nexus can perform research using tools, it is designed for broader problem-solving, code modification, and task planning.

4. **Planning Runtime**:
   * *Description*: Deconstructs user tasks into logical step sequences and dependency graphs.
   * *Nexus fit*: **Partial**. Nexus contains custom planning capability, but it couples planning with direct tool execution.

5. **Hybrid Runtime**:
   * *Description*: Integrates planning, research, and tool-use execution in an API-driven loop.
   * *Nexus fit*: **Strong**. Nexus is a hybrid framework since it performs planning (decomposing goals) and executing tools in a single context.

---

## 2. Recommended Classification

We recommend classifying Nexus as an **Agent Runtime** (with hybrid Planning and Research capabilities).

### Classification Rationale:
* **API-Driven Lifecycles**: Nexus operates over network API calls (e.g., to OpenRouter/custom model ports) rather than invoking a local subprocess CLI binary.
* **Autonomous Tool Use**: The runner does not receive a pre-defined command to run in a terminal. It is given a system goal and generates actions/commands *dynamically* at runtime.
* **Non-POSIX Outputs**: The runtime emits state transitions and tool-execution logs rather than standard OS `stdout`/`stderr` streams.
