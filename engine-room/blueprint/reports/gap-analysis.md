# Nexus Gap Analysis & Primitive Evaluation

This report evaluates potential missing runtime primitives, analyzes the structural design of the core execution units, and catalogs the remaining architectural gaps before Phase 1 begins.

---

## 1. Task 4 — Potential Missing Runtime Primitives

### 1.1. Core Investigation: `WorkflowInstance`
We must determine whether the system should introduce `WorkflowInstance` as a first-class primitive, or if the current `TaskRecord` is sufficient as the root execution unit.

#### Logical Scope Comparison:
```
Task (Primary Unit)                       WorkflowInstance (Proposed Parenting)
├── Research Job (Sub-step)               └── WorkflowInstance (Fix Bug X)
├── Approval Gate (Sub-step)                  ├── Task 1: Research Job
├── Subprocess Runner (Sub-step)              ├── Task 2: Code Plan Generation
└── Summary Report (Sub-step)                 ├── Task 3: Execution Run
                                              └── Task 4: Summary Report
```

### 1.2. Decision: NO (Retain Task as Root; Evolve in v0.5+)

#### Detailed Rationale:
1. **Accidental Complexity**: Introducing a separate `WorkflowInstance` layer above `Task` creates a redundant tier of parent-child relationships for a single-operator MVP. A single task ("Fix bug X in Memex") naturally maps to a sequential workflow run.
2. **Task as the Natural Workflow Container**: In our schema design, a `TaskRecord` owns multiple child records: `ApprovalRecord`, `ExecutionRecord`, `ExecutionStepRecord`, and `ResearchItemRecord`. Therefore, a task is **already** a workflow instance. 
3. **State Overhead**: Adding `WorkflowInstance` would require duplicate state management, more database queries, and increased transaction locking, violating the simplicity constraints of SQLite.
4. **Conclusion**: We will not introduce `WorkflowInstance` as a first-class table in Phase 1. The `TaskRecord` remains the true root execution unit. If we need to support multi-task pipelines in v0.5/v1.0, we will introduce a `workflows` parent table then.

---

## 2. Task 5 — Architectural Gaps Before Phase 1

Below is the structured catalog of gaps that must be resolved either before or during the Phase 1 development cycle.

### 2.1. Critical Gaps (Must resolve before/during Phase 1)

#### GAP-001: Database Lock Handling in SQLite Async loops
- **Description**: SQLite has database-level write locks. If the background Heartbeat Sweeper is updating `execution_steps` while the Task Engine is writing a task state change, an async event loop can encounter `sqlite3.OperationalError: database is locked`.
- **Impact**: Operational crash and unrecoverable task state corruption.
- **Resolution**: Setup SQLAlchemy connection pooling with a busy timeout parameter (e.g. `timeout=30.0` seconds) and enforce Write-Ahead Logging (WAL) mode programmatically.

#### GAP-002: System Events Outbox Publisher Loop
- **Description**: The `system_events` table acts as our transactional outbox. We have designed the table, but we do not have an active background process to read pending events, publish them to subscribers, and mark them as completed.
- **Impact**: Normalized system events are cached in the database but never dispatched to external subscribers (like Discord or Email).
- **Resolution**: Add an outbox publisher daemon as part of `AP-102` (Event System) using `APScheduler` to sweep and process events every 5 seconds.

#### GAP-003: Subprocess Output Buffer Limits
- **Description**: Subprocess commands can output megabytes or gigabytes of log text (e.g., recursive directory searches or verbose test runs). If stdout/stderr values are written directly to SQLite without size checks, the database could run out of disk space or freeze the FastAPI server.
- **Impact**: Database write blocks, memory exhaustion, and control plane crashes.
- **Resolution**: Enforce strict logging buffer limits (e.g. max 1MB per step) in `nexus/execution/` and truncate older lines at runtime.

---

### 2.2. Important Gaps (Must resolve during Phase 2/3)

#### GAP-004: Erroneous Retry States
- **Description**: The Task State Machine transitions from `ACTIVE` to `FAILED` on step crash. However, we have not defined a state or counter for automatic retries of idempotent steps.
- **Impact**: Workflows fail permanently on minor network glitches, requiring manual recovery.
- **Resolution**: Add a `retry_count` column to `execution_steps` and a transition guard supporting `FAILED` -> `QUEUED` if `retry_count < max_retries`.

#### GAP-005: Discord Bot Rate Limit Recovery
- **Description**: The Discord gateway sends embeds for approvals. If Hill Patel triggers multiple approvals concurrently, the bot can hit Discord API rate limits and discard messages.
- **Impact**: Approval requests are lost, leaving tasks locked in `BLOCKED` state permanently.
- **Resolution**: Implement a bounded queue inside the Discord Integration package to handle rate limit headers and retry with exponential backoff.

---

### 2.3. Future Gaps (Post-MVP Concerns)

#### GAP-006: Multi-Tenant Data Isolation
- **Description**: The database schemas assume a single operator (Hill Patel). There are no `user_id` or `tenant_id` foreign keys in the tables.
- **Impact**: Transitioning to multi-user support in the future will require schema migrations.
- **Resolution**: Deferred to v0.5+.

#### GAP-007: Vector Knowledge Retrieval (RAG)
- **Description**: Research summaries are currently stored as plain text inside `KnowledgeItemRecord`. There is no vector database or search index setup.
- **Impact**: The LLM planner will have to retrieve knowledge via keyword matches or load entire files, wasting tokens.
- **Resolution**: Deferred to v1.0.
