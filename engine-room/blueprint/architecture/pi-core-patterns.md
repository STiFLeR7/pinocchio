# Pi Core Patterns & Nexus Adoption Mapping

This document lists the core architectural and systems-design patterns found in **Pi Core**, details their mechanics, and classifies them for adoption in the **Nexus Control Plane**.

---

## Pattern Matrix

| Pattern | Source/Domain | Nexus Classification | Actionable Architecture for Nexus |
|---|---|---|---|
| **Append-Only Event Reduction** | State & Storage | **Adapt** | Maintain state in standard relational SQLite tables (`tasks`, `executions`), but log all state changes dynamically to an immutable `audit_log` table. |
| **Pydantic/API Schema Separation** | Context Management | **Adopt Directly** | Maintain a strict decoupling between internal database schemas (`schemas.py`) and external API models (e.g., OpenRouter payloads). |
| **Pre-Execution Validation Hooks** | Tool Architecture | **Adapt** | Evaluate target authorization blocks via database checks (`beforeToolCall`) against the owner's `ApprovalRecord` before executing any runner subprocess. |
| **Sequential Logging of Parallel Outputs**| Concurrency | **Adopt Directly** | Run subprocess execution steps in parallel (asyncio), but insert their log records sequentially in assistant-call order. |
| **Dialogue Compaction & Summarization** | Context Management | **Adapt** | Write a background service to summarize dialog history and save checkpoints to `WorkflowCheckpointRecord` when context windows fill. |
| **Steering and Follow-up Queues** | Queue Orchestration | **Adapt** | Implement a database-backed execution queue where active jobs can be paused, aborted, or queued via external commands. |

---

## Detailed Pattern Analyses

### 1. Append-Only Event Reduction
- **Pi Core Mechanics**: The session log tree does not perform direct database table updates. Instead, it appends micro-events (e.g. `thinking_level_change`, `message_end`, `leaf_update`). Reopening the log parses and processes all entries sequentially to compute the final agent state.
- **Nexus Assessment (Adapt)**:
  - *Why not adopt directly?* Rebuilding state from raw events on every HTTP call is computationally expensive and hard to query inside SQL.
  - *Adoption Plan*: Use standard relational columns for querying (e.g. `TaskRecord.status = "active"`). However, pair every status update with a mandatory write to `AuditLogRecord`. The state machine should use standard database records, but the audit trail remains immutable and append-only.

### 2. Pydantic/API Schema Separation
- **Pi Core Mechanics**: Pi structures messages internally using an enriched `AgentMessage` type (carrying fields like skill invocations and UI parameters). It uses `convertToLlm` to format these messages right before invoking the provider API.
- **Nexus Assessment (Adopt Directly)**:
  - *Adoption Plan*: Keep internal domain models strictly decoupled from OpenRouter schemas. Pydantic schemas in `schemas.py` (`TaskResponse`, `ExecutionResponse`) represent our domain. When calling LLMs, run a mapping utility inside the intelligence module to format messages to the OpenRouter format.

### 3. Pre-Execution Validation Hooks (`beforeToolCall`)
- **Pi Core Mechanics**: Before any tool execute loop begins, argument validation runs, followed by `beforeToolCall()`. If it returns `{ block: true }`, the execution is halted and a failure is returned.
- **Nexus Assessment (Adapt)**:
  - *Adoption Plan*: In our execution runner (`nexus/execution/`), compile the subprocess arguments and invoke a check against the `ApprovalRecord` in SQLite. If the task is blocked or lacks an owner approval, abort the execution before running the subprocess.

### 4. Sequential Logging of Parallel Outputs
- **Pi Core Mechanics**: Even when executing multiple tool calls concurrently (`Promise.all`), Pi holds the results and emits/persists `toolResultMessage` sequentially in the assistant's original call order.
- **Nexus Assessment (Adopt Directly)**:
  - *Adoption Plan*: When running multi-step tasks concurrently via `asyncio.gather`, collect their logs and stdout outputs. Ensure that writes to the database `AuditLogRecord` and `ExecutionRecord` tables are performed sequentially, preserving the order of execution requests to avoid non-deterministic context layouts.

### 5. Context Compaction (Checkpointing)
- **Pi Core Mechanics**: When token consumption crosses limits, Pi runs an LLM-driven summarization process, writes the summary to a compaction entry, and prunes older message lists.
- **Nexus Assessment (Adapt)**:
  - *Adoption Plan*: Implement dialogue truncation inside the context compiler of our intelligence module. When context length reaches 75% of limit:
    1. Invoke a summarization task via OpenRouter.
    2. Write the summary to `WorkflowCheckpointRecord`.
    3. Truncate older audit log records from the active prompt window, starting the prompt with the compacted summary.
