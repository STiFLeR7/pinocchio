# Nexus Runtime Primitives Specification

This document defines the atomic, irreducible **runtime primitives** of the **Nexus Control Plane**. These primitives serve as the structural foundation for the Task Engine, Approval Engine, and Subprocess Runner implementation in Phase 1 and Phase 2.

---

## 1. First-Class (Durable) Primitives

First-class primitives represent immutable records persisted directly in the relational database (`SQLite`). They are the source of truth for the system state.

```
+--------------------------------------------------------------------------+
|                            FIRST-CLASS PRIMITIVES                        |
|                                                                          |
|  +---------------------------+             +---------------------------+  |
|  | TaskRecord                |             | AuditLogRecord            |  |
|  | (The root execution job)  |             | (Immutable event ledger)  |  |
|  +---------------------------+             +---------------------------+  |
|                |                                         |                |
|                v                                         v                |
|  +---------------------------+             +---------------------------+  |
|  | ExecutionRecord           |             | WorkflowCheckpointRecord  |  |
|  | (Individual runner steps) |             | (State checkpoints)       |  |
|  +---------------------------+             +---------------------------+  |
+--------------------------------------------------------------------------+
```

1. **Task (`TaskRecord`)**:
   - **Definition**: The root runtime primitive. Represents the overall user-initiated intent (e.g. "Fix lint error on file X").
   - **Attributes**: `id` (UUID), `status` (`TaskStatus`), `priority` (`Priority`), and `is_archived`.
2. **ExecutionStep (`ExecutionRecord`)**:
   - **Definition**: An atomic, subprocess tool call execution (equivalent to Pi's `ToolCall`).
   - **Attributes**: `id` (UUID), `task_id` (FK), `runner` (`RunnerType`), `started_at`, `last_heartbeat`, `timeout_threshold`, and `exit_status` (`ExitStatus`).
3. **ExecutionResult (`ExecutionRecord` payload columns)**:
   - **Definition**: The outcome of an `ExecutionStep` (equivalent to Pi's `ToolResult`).
   - **Attributes**: `logs` (raw stdout/stderr), `result` (parsed structured JSON outcome), and `completed_at`.
4. **StateTransition (`AuditLogRecord`)**:
   - **Definition**: An immutable ledger entry recording a system state change (equivalent to Pi's append-only logging).
   - **Attributes**: `event_type` (`EventType`), `entity_type`, `entity_id`, `data` (JSON payload), `correlation_id` (UUID), and `actor`.
5. **Checkpoint (`WorkflowCheckpointRecord`)**:
   - **Definition**: A serialized snapshot of a workflow state to enable pause, resume, and recovery (equivalent to Pi's `CompactionEntry`).
   - **Attributes**: `workflow_id`, `step_name`, `state` (JSON payload), and `completed_at`.

---

## 2. Derived (Ephemeral) Primitives

Derived primitives exist only in memory during runtime execution. They are reconstructed dynamically by querying first-class primitives from the database.

1. **ContextFrame**:
   - **Definition**: The active token window compiled for the LLM during a turn.
   - **Assembly**: Computed by reading the task's historical `ExecutionStep` logs and `AuditLogRecord` events, truncated or summarized according to active checkpoints.
2. **ActiveToolset**:
   - **Definition**: The list of subprocess runners and validation policies active for the current step.
   - **Reconstruction**: Resolved dynamically by reading configuration files (`config/settings.yaml` and `config/repositories.yaml`) and mapping them to the task state.
3. **ApprovalStatus**:
   - **Definition**: The validation boundary determining if a runner step is allowed to run.
   - **Reconstruction**: Checked by matching the `ExecutionRecord` request against the latest active `ApprovalRecord` for that task.
