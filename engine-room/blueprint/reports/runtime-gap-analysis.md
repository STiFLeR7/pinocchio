# Nexus Runtime Gap Analysis

This document evaluates the database schema integrity, event replayability index, memory-first design alignments, and potential runtime primitives.

---

## 1. Database Review

### 1.1. Schema & Index Evaluation
- **Indexes**: Indexes are placed on `correlation_id` (tracing), `entity_id` and `entity_type` (for context compiling), and status columns. This provides fast queries during context reduction.
- **Relationships**: Parent-child relationships (e.g. `TaskRecord -> Approvals -> Executions -> Steps`) are defined with foreign key constraints and `ondelete="CASCADE"` or `ondelete="SET NULL"` parameters to prevent orphan records.
- **Future Migration Concerns**: Transitioning SQLite to PostgreSQL will require replacing dialects and moving `JSON` field columns to `JSONB` for optimized indexing.
- **Missing Constraints**: A unique constraint should be placed on `workflow_checkpoints` to ensure no duplicate checkpoints are written for the same workflow/step sequence.

---

## 2. Event System Replayability & Durability

### 2.1. Audit Replay Assessment
- **Workflow Reconstruction**: Every state transition emits a `NexusEvent` saved as an immutable `AuditLogRecord`. Reconstructing task state is possible by filtering logs on `entity_id = task_id` and replaying enqueued states sequentially.
- **Summary Regeneration**: Since all prompt messages and tool outputs are saved in the logs, summaries can be regenerated at any time by feeding the historical message list to OpenRouter.
- **Failure Replays**: Subprocess commands and their exact stdout/stderr logs are stored in `ExecutionStepRecord`, allowing developers to replicate crashed conditions.
- **Recovery after Restart**: On reboot, the Heartbeat Sweeper identifies active steps, marks them as timed-out, and rolls back the task status to `FAILED`, guaranteeing system consistency.

---

## 3. Memory System Review (Memory-First vs. State-First)

- **The Critique**: Is the implementation truly memory-first, or is it state-first with memory attached?
- **Analysis**:
  - *State-First with Memory Attached*: A classic agent pattern where variables are held in a global memory dict, and occasionally flushed to disk. If the thread crashes, the variables are lost.
  - *Memory-First (The Nexus Design)*: Nexus compiles its active `ContextFrame` dynamically. The source of truth is the database checkpoints and event logs. The memory state is **derived** at runtime from these logs. Therefore, Nexus is **truly memory-first**: the database state dictates the in-memory context, not the other way around.
- **Weaknesses**: Replaying extensive historical logs on every single turn will become slow if log entries grow to thousands of rows without compaction checkpoints. We must enforce strict context size limits and trigger checkpoints regularly.

---

## 4. Missing Primitives Evaluation

We evaluate potential runtime primitives for inclusion in the system:

| Proposed Primitive | Description | Classification | Rationale |
|---|---|---|---|
| **WorkflowInstance** | Explicit parent execution graph for tasks. | **Reject** | A `TaskRecord` already serves as the parent container for approvals and executions, making this redundant for MVP. Evolve in v0.5+. |
| **ExecutionSession** | Tracks the active connection session with a runner. | **Phase 2** | Useful to manage SSH or remote workspace mounts for Claude Code/Gemini CLI. |
| **ResearchArtifact** | Structured files harvested during research runs. | **Future** | Useful for v0.5 search summarizers; not needed for Phase 1. |
| **DecisionRecord** | Tracks why an agent chose a planning path. | **Reject** | Can be stored as metadata inside standard `AuditLogRecord` payloads. |
