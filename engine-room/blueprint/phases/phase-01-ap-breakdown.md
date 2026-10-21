# Phase 1 — Core Infrastructure Action Point Breakdown

This document provides the action point (AP) engineering breakdown for **Phase 1 (Core Infrastructure)**. Each AP is designed to be independently implementable, testable, and compliant with the runtime architecture specifications.

---

## Action Point Dependencies

```
[AP-101: DB Schema & Migration]
               |
               v
[AP-102: Event Gateway & Normalization]
               |
               v
[AP-103: Memory Manager (State Traversal)]
         /           \
        v             v
[AP-104: Task Engine]  [AP-105: Approval Engine]
        \             /
         v           v
[AP-106: Runtime State Machines Validation]
```

---

## Action Points Specs

### 1. AP-101: Database Foundation
- **Scope**: Define the remaining database models in SQLAlchemy (`executions`, `execution_steps`, `audit_logs`, `workflow_checkpoints`, `research_jobs`) and auto-generate the base Alembic revision migration.
- **Dependencies**: None.
- **Deliverables**:
  - Models added to `nexus/memory/models.py`.
  - Alembic migration script generated in `alembic/versions/`.
  - Database initialization code running inside `nexus/api.py` lifespan context manager.
- **Tests**:
  - `tests/unit/memory/test_models.py`: Verify fields, foreign keys, constraints, and cascades for the new models.
  - Integration test verifying Alembic upgrade/downgrade cycles.
- **Exit Criteria**: `uv run alembic upgrade head` completes with zero SQL errors, and all tables exist in SQLite.

### 2. AP-102: Event System & Normalization
- **Scope**: Build the base Event Gateway, outbox table (`system_events`), and audit logging client.
- **Dependencies**: AP-101.
- **Deliverables**:
  - `nexus/gateway/` router implementation.
  - Event schemas inside `nexus/core/events.py`.
  - `MemoryService.log_event` writing event payloads directly to `AuditLogRecord`.
- **Tests**:
  - Verify that emitting a `TaskCreated` event inserts a record into the `audit_logs` table with correct JSON parsing and correlation ID propagation.
- **Exit Criteria**: Event routing executes without event loop blockages, and audit logs are append-only.

### 3. AP-103: Memory Manager
- **Scope**: Reconstruct runtime states (`SessionContext`, active model, active tools) by traversing past database audit logs and checkpoints.
- **Dependencies**: AP-102.
- **Deliverables**:
  - `nexus/memory/manager.py` containing context assembly methods.
  - Context compilations supporting compaction checkpoints (`WorkflowCheckpointRecord`).
- **Tests**:
  - Mock history log containing `model_change`, `thinking_level_change`, and `message` entries. Verify that the context compiler reduces these to the correct model settings and message lists.
- **Exit Criteria**: Reconstructing context from history passes strict validation.

### 4. AP-104: Task Engine
- **Scope**: Standardize task lifecycle state updates, SQL transaction locks, CRUD queries, and history tracks.
- **Dependencies**: AP-103.
- **Deliverables**:
  - `nexus/memory/task_service.py` mapping CRUD commands.
  - Guard checks preventing invalid state transitions (e.g. `completed` → `active`).
- **Tests**:
  - Verify that setting status to `active` is blocked if state transition constraints are violated.
  - Verify that status changes insert corresponding `AuditLogRecord` rows.
- **Exit Criteria**: Task transitions execute atomically under transaction locks.

### 5. AP-105: Approval Engine
- **Scope**: Implement approval requests, owner ID check bindings, expiration sweeps, and approval gate logic.
- **Dependencies**: AP-103.
- **Deliverables**:
  - `nexus/approvals/service.py` to create, evaluate, and expire approval requests.
  - Database checks validating `ApprovalRecord` fields.
- **Tests**:
  - Verify that creating an approval defaults to a 24-hour expiration.
  - Verify that expiration sweeps update statuses to `expired`.
- **Exit Criteria**: Approval rules block execution states until approved.

### 6. AP-106: Runtime State Machines
- **Scope**: Integrate Task, Approval, and Execution state machines. Ensure step transitions are validated and logged concurrently.
- **Dependencies**: AP-104, AP-105.
- **Deliverables**:
  - Integration workflow orchestrator mapping state transitions between Tasks, Approvals, and Execution steps.
- **Tests**:
  - End-to-end integration test creating a task, requesting approval, granting approval, starting execution steps, and recording completion status.
- **Exit Criteria**: End-to-end task execution lifecycles pass with full audit coverage.
