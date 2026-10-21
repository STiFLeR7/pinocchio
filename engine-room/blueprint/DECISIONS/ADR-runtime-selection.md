# ADR: Runtime Selection Framework

## Status
Approved

## Context
In previous implementations, routing tasks to runtimes (e.g., Gemini CLI vs. Nexus Agent) relied on brittle string-matching heuristics inside the description field (e.g., `description.startswith("goal:")` or `contains("nexus")`). This heuristic-based routing prevents enterprise readiness because:
1. It is non-governed and cannot enforce execution policies.
2. It is non-auditable, as the database does not explicitly track which runtime or profile was requested or active.
3. It lacks flexibility, requiring orchestrator code modifications to support new runtimes (like Claude Code) or custom workloads.

To establish production governance, we require a first-class **Runtime Selection Framework** where every task explicitly defines its execution metadata, backed by a registry, profiles, and governance policies.

---

## Decisions

We approve the design and implementation of the Runtime Selection Framework with the following specifications:

1. **Explicit Task Metadata Columns**:
   * Add four explicit columns to `TaskRecord` (and corresponding schemas/services):
     * `runtime_type` (e.g., `"cli"`, `"agent"`, `"research"`)
     * `runtime_id` (e.g., `"gemini"`, `"nexus"`, `"claude"`)
     * `execution_profile` (e.g., `"research"`, `"planning"`, `"coding"`, `"refactoring"`, `"analysis"`, `"reporting"`, `"custom"`, `"default"`)
     * `runtime_policy` (e.g., `"approved"`, `"monitored"`, `"blocked"`)

2. **Decoupled Runtime Registry**:
   * Implement a registry pattern where runtime adapters register themselves under unique IDs.
   * The orchestrator resolves adapters dynamically via the registry, eliminating hardcoded `if/else` checks for specific runner names.

3. **Configurable Execution Profiles**:
   * Execution profiles decouple configuration constraints from the execution runner.
   * Profiles influence runtime behaviors such as timeouts, checkpoint frequency, artifact expectations, and governance rules.

4. **Runtime Governance & Policies**:
   * Every execution is subjected to policy enforcement (e.g., checking if the selected runtime and profile are `"approved"`).
   * Governance rules intercept execution prior to initialization to ensure strict compliance.

---

## Consequences

* **Orchestrator Routing**: Dynamic routing replaces heuristic text parsing in [orchestrator.py](file:///D:/nexus/nexus/scheduling/orchestrator.py) by querying the task's explicit columns.
* **Extensibility**: Adding future adapters (such as Claude Code) requires zero changes to the orchestrator; they register under the runtime registry and are instantly selectable.
* **Audit Trail**: Every execution record maps back to explicit task configurations, making execution parameters 100% auditable.
