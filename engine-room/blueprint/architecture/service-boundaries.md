# Nexus Service Boundaries & Dependency Rules

This document specifies the structural boundaries, responsibilities, owned models/events, and import constraints for each Python sub-package in the `nexus/` directory.

---

## Service Dependency Architecture

```
                 +-------------------+
                 |       agents      |
                 +-------------------+
                           |
                           v
 +-------------------------------------------------------+
 |                       execution                       |
 +-------------------------------------------------------+
        |                  |                   |
        v                  v                   v
 +--------------+   +--------------+   +-----------------+
 |  scheduler   |   |  approvals   |   |  integrations   |
 +--------------+   +--------------+   +-----------------+
        |                  |                   |
        +------------------+-------------------+
                           |
                           v
 +-------------------------------------------------------+
 |                     memory / core                     |
 +-------------------------------------------------------+
                           |
                           v
 +-------------------------------------------------------+
 |                        events                         |
 +-------------------------------------------------------+
```

---

## Package Specifications

### 1. `nexus/core/` (Bootstrapping and Common Primitives)
- **Responsibilities**: Base exceptions, standard types, logging setups, and configuration settings loading.
- **Owned Models**: None.
- **Owned Events**: None.
- **Dependencies**: None.
- **Forbidden Dependencies**: MUST NOT import from any other `nexus/` sub-package (this is the absolute root layer).

### 2. `nexus/events/` (Normalizer and Gateway Router)
- **Responsibilities**: Encapsulates `NexusEvent` validation, Event Gateway, outbox delivery, and database-backed event logging.
- **Owned Models**: `AuditLogRecord`, `system_events`.
- **Owned Events**: All `NexusEvent` base envelopes.
- **Dependencies**: `nexus/core/` (for base types/settings).
- **Forbidden Dependencies**: MUST NOT import from `nexus/memory/`, `nexus/execution/`, `nexus/approvals/`, or `nexus/agents/`.

### 3. `nexus/memory/` (Durable storage manager)
- **Responsibilities**: Relational persistence management (SQLAlchemy engine/sessionmaker setup), schema migrations (Alembic), Pydantic schemas, and workflow state checkpoints.
- **Owned Models**: `TaskRecord`, `WorkflowCheckpointRecord`, `ResearchItemRecord`, `KnowledgeItemRecord`.
- **Owned Events**: `CheckpointCreated`.
- **Dependencies**: `nexus/core/`, `nexus/events/` (to write audit logs).
- **Forbidden Dependencies**: MUST NOT import from `nexus/execution/`, `nexus/approvals/`, or `nexus/agents/`.

### 4. `nexus/approvals/` (Governance gates)
- **Responsibilities**: Manages task execution blocks, Discord user ID matching, verification timeout timers, and approval resolution.
- **Owned Models**: `ApprovalRecord`.
- **Owned Events**: `ApprovalRequested`, `ApprovalGranted`, `ApprovalRejected`, `ApprovalExpired`.
- **Dependencies**: `nexus/core/`, `nexus/events/`, `nexus/memory/`.
- **Forbidden Dependencies**: MUST NOT import from `nexus/execution/` or `nexus/agents/`.

### 5. `nexus/execution/` (Subprocess runtimes)
- **Responsibilities**: Runner abstraction layers (Gemini CLI, Claude Code), subprocess creation (`asyncio`), and step logging.
- **Owned Models**: `ExecutionRecord`, `ExecutionStepRecord`.
- **Owned Events**: `ExecutionStarted`, `ExecutionHeartbeat`, `ExecutionCompleted`, `ExecutionFailed`.
- **Dependencies**: `nexus/core/`, `nexus/events/`, `nexus/memory/`, `nexus/approvals/` (to check validation guards).
- **Forbidden Dependencies**: MUST NOT import from `nexus/agents/`.

### 6. `nexus/scheduler/` (Job orchestrator)
- **Responsibilities**: Periodically triggers background tasks (using `APScheduler`), sweeps active execution steps for heartbeats, and manages cron runs.
- **Owned Models**: None.
- **Owned Events**: None.
- **Dependencies**: `nexus/core/`, `nexus/events/`, `nexus/memory/`, `nexus/execution/`.
- **Forbidden Dependencies**: None.

### 7. `nexus/integrations/` (External communications)
- **Responsibilities**: Discord bot connections, Discord card embed generation, SMTP Gmail client, and OpenRouter request wrappers.
- **Owned Models**: `research_jobs`.
- **Owned Events**: `NotificationSent`, `NotificationFailed`.
- **Dependencies**: `nexus/core/`, `nexus/events/`, `nexus/memory/`.
- **Forbidden Dependencies**: None.

### 8. `nexus/agents/` (Planning and research logic)
- **Responsibilities**: Houses LLM decision loops, research logic, and planner loops.
- **Owned Models**: None.
- **Owned Events**: `ResearchCompleted`.
- **Dependencies**: `nexus/core/`, `nexus/events/`, `nexus/memory/`, `nexus/execution/`, `nexus/integrations/`.
- **Forbidden Dependencies**: None.

---

## Strict Coupling Invariants

1. **Cycle Prevention**: Circular imports in Python are blocked by keeping packages strictly layered. A lower-numbered layer must **never** import from a higher-numbered layer.
2. **Database Isolation**: No module outside `nexus/memory/` may interact with the database engine factory directly; all queries must use session context managers provided by `database.py`.
3. **No Direct Subprocess Spawning**: Subprocesses must only be created inside `nexus/execution/` module boundary to enforce preflight approval checks.
