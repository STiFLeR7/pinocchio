# Phase 1 Retrospective & Audit Review

This document audits the completed Action Points for **Phase 1 (Core Infrastructure)**, evaluates architectural alignment, and proposes production hardening improvements.

---

## 1. Action Point Audits

### AP-101: Database Foundation
- **Intended Design**: Relational schemas in SQLAlchemy 2.x mapping all major tables (`tasks`, `approvals`, `executions`, `execution_steps`, `audit_logs`, `workflow_checkpoints`, `research_jobs`, `system_events`), with SQLite WAL settings and foreign key listeners.
- **Actual Implementation**: All tables defined inside `nexus/memory/models.py`. Foreign keys and WAL pragmas setup via event listeners in `nexus/database.py`. alembic version generated and migrated successfully.
- **Deviations**: None.
- **Risks**: SQLite database-level write locks under high concurrent writing.
- **Technical Debt**: SQLite is hard-coded; future migration to PostgreSQL will require database dialect adaptations.
- **Recommendations**: Enforce strict session context separation to avoid connection leaks.

### AP-102: Event System & Normalization
- **Intended Design**: Async Event Gateway, transactional outbox routing cache, and append-only audit logging.
- **Actual Implementation**: Built `EventGateway` in `nexus/gateway/gateway.py` with subscriber mapping. `MemoryService.log_event` and `enqueue_outbox_event` write to `AuditLogRecord` and `SystemEventRecord` using Pydantic JSON dump serialization.
- **Deviations**: In-memory gateway routes callbacks in-process instead of a decoupled task queue (suitable for MVP scope).
- **Risks**: Memory consumption if events are emitted faster than subscribers execute.
- **Technical Debt**: Outbox publisher sweep daemon is defined in gaps list but not fully automated via APScheduler.
- **Recommendations**: Implement outbox publisher loop during Phase 2 background task setup.

### AP-103: Memory Manager
- **Intended Design**: Derived state traversal replaying logs sequentially from the latest checkpoint snapshot to build the active context frame.
- **Actual Implementation**: Implemented `ContextCompiler` in `nexus/memory/manager.py` merging latest `WorkflowCheckpointRecord` with subsequent `AuditLogRecord` entries.
- **Deviations**: None.
- **Risks**: If the checkpoint is corrupt, context compilation fails completely.
- **Technical Debt**: Prompt truncation and summarization trigger logic is stubbed out and needs actual OpenRouter compiler wiring.
- **Recommendations**: Integrate context compiler directly with OpenRouter client.

### AP-104: Task Engine
- **Intended Design**: Standardized Task CRUD operations, transaction locking, and transition guard checks.
- **Actual Implementation**: Created `TaskService` in `nexus/memory/task_service.py` with valid transition mappings and row locking (`with_for_update`).
- **Deviations**: None.
- **Risks**: SQLite row-level locks are compiled but fallback to database-level locks, causing lock competition.
- **Technical Debt**: Status transition error details are raised as exceptions but not routed to alert notification adapters yet.
- **Recommendations**: Hook TaskEngine exceptions to gateway error publishers.

### AP-105: Approval Engine
- **Intended Design**: Gate check validations, credentials checks, and 24-hour expiration sweeps.
- **Actual Implementation**: Created `ApprovalService` in `nexus/approvals/service.py` verifying Discord IDs, creating gates, and sweeping expired records.
- **Deviations**: Discord bot notification is stubbed (to be built in Phase 3).
- **Risks**: Sweeper clock drift can cause slight delay in expiring approvals.
- **Technical Debt**: Hardcoded 24-hour expiry default inside method signature instead of parsing dynamically from settings.
- **Recommendations**: Bind expiry limit to Pydantic Settings parameter.

### AP-106: Runtime State Machines
- **Intended Design**: Unified E2E integration of Task, Approval, and Execution state machines.
- **Actual Implementation**: Built `ExecutionService` in `nexus/execution/service.py` linking runs and steps. Wrote comprehensive integration test `tests/integration/test_state_machines.py` verifying E2E state transition cycles.
- **Deviations**: None.
- **Risks**: Interrupted step runs can leave database records in `running` state if python crashes.
- **Technical Debt**: Concatenated logs are held in-memory before database commits, causing memory spikes.
- **Recommendations**: Implement step log chunk writing in chunks.

---

## 2. Blueprint Directory Audit

The `blueprint/` directory contains all historical and active architectural artifacts:
- **AP Tracking**: Checked off in `STATUS.md` and `ROADMAP.md`.
- **ADRs**: ADR-001 through ADR-015 check out cleanly.
- **Reports**: Final pre-implementation analysis reports are present.
- ** walk-throughs**: Placed in `blueprint/architecture/architecture-evolution.md`.
- **Status of Project Memory**: The blueprints serve as the source of truth, matching codebase implementations perfectly.

---

## 3. Production Hardening Recommendations (Top 10)

1. **SQLite to PostgreSQL migration** (Critical) - Enforce true concurrency and row-level locking for tasks.
2. **Outbox Publisher automation** (Critical) - Automate background sweeps of `system_events` table to prevent table bloating.
3. **Subprocess stream size constraints** (Critical) - Truncate command output exceeding 1MB.
4. **Task transaction retry policies** (Important) - Implement SQLite busy lock retry policies.
5. **Orphan subprocess cleanup script** (Important) - Reap lost OS process IDs on startup.
6. **Encrypted secrets configuration** (Important) - Secure passwords and tokens from plain-text YAML files.
7. **Dead-letter event queue** (Important) - Move corrupted events out of system queue.
8. **Rate limiting on gateway inputs** (Future) - Protect Event Gateway from API spam.
9. **Automatic database compression/vacuuming** (Future) - Maintain low storage sizes.
10. **Emergency bypass passcode** (Future) - Enable human operators to override gates.
