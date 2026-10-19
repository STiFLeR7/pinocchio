# SQLite Relational Database Schema Design

This document specifies the database design for the **Nexus Control Plane**. The schema uses relational integrity (foreign keys, cascading deletes, index configurations) mapped via SQLAlchemy 2.x and SQLite WAL mode.

---

## Entity Relationship Overview

```
 [tasks] 
    |
    +--- (1:N) ---> [approvals] 
    |
    +--- (1:1) ---> [research_jobs]
    |
    +--- (1:N) ---> [executions] 
                      |
                      +--- (1:N) ---> [execution_steps]

 [audit_logs]               (Append-only ledger)
 [workflow_checkpoints]     (State checkpoint snapshots)
 [system_events]            (Normalization/Event queue cache)
```

---

## Table Specifications

### 1. `tasks` (Primary state tracker)
- **Description**: Stores task info, status, and metadata.
- **Fields**:
  - `id`: `UUID` (PK, default `uuid4`)
  - `title`: `VARCHAR(500)` (Not Null)
  - `description`: `TEXT` (Nullable)
  - `status`: `VARCHAR(50)` (Not Null, default `"created"`)
  - `priority`: `INTEGER` (Not Null, default `2`)
  - `created_at`: `TIMESTAMP` (Not Null, default `UTC_NOW`)
  - `updated_at`: `TIMESTAMP` (Not Null, default `UTC_NOW`, onupdate `UTC_NOW`)
  - `is_archived`: `BOOLEAN` (Not Null, default `False`)
- **Indexes**:
  - `idx_tasks_status` ON (`status`)
  - `idx_tasks_created` ON (`created_at` DESC)
- **Relationships**:
  - `approvals`: 1:N (`ApprovalRecord`), Cascade delete.
  - `executions`: 1:N (`ExecutionRecord`), Cascade delete.
- **Lifecycle**: `created` → `queued` → `active` [↔ `blocked`] → `completed` / `failed` / `cancelled`.

### 2. `approvals` (Authorization gates)
- **Description**: Tracks user approvals required for task step execution.
- **Fields**:
  - `id`: `UUID` (PK)
  - `task_id`: `UUID` (FK `tasks.id`, Not Null, Index)
  - `status`: `VARCHAR(50)` (Not Null, default `"pending"`)
  - `requested_at`: `TIMESTAMP` (Not Null)
  - `decided_at`: `TIMESTAMP` (Nullable)
  - `decided_by`: `VARCHAR(200)` (Nullable, tracks Owner Discord User ID)
  - `expires_at`: `TIMESTAMP` (Nullable, defaults to requested_at + 24 hours)
  - `decision_reason`: `TEXT` (Nullable)
  - `created_at`: `TIMESTAMP` (Not Null)
  - `updated_at`: `TIMESTAMP` (Not Null)
  - `is_archived`: `BOOLEAN` (Not Null)
- **Indexes**:
  - `idx_approvals_task_status` ON (`task_id`, `status`)
  - `idx_approvals_expires` ON (`expires_at`)
- **Lifecycle**: `pending` → `approved` / `rejected` / `expired` / `cancelled`.

### 3. `executions` (Overall task run phases)
- **Description**: Captures execution phases associated with a task run.
- **Fields**:
  - `id`: `UUID` (PK)
  - `task_id`: `UUID` (FK `tasks.id`, Not Null, Index)
  - `approval_id`: `UUID` (FK `approvals.id`, Nullable, Index, set null on delete)
  - `runner`: `VARCHAR(100)` (Not Null)
  - `repository`: `VARCHAR(500)` (Nullable)
  - `started_at`: `TIMESTAMP` (Nullable)
  - `completed_at`: `TIMESTAMP` (Nullable)
  - `exit_status`: `VARCHAR(50)` (Nullable)
  - `created_at`: `TIMESTAMP` (Not Null)
  - `updated_at`: `TIMESTAMP` (Not Null)
  - `is_archived`: `BOOLEAN` (Not Null)
- **Relationships**:
  - `steps`: 1:N (`ExecutionStepRecord`), Cascade delete.

### 4. `execution_steps` (Atomic subprocess command calls)
- **Description**: Individual subprocess invocations under an execution run.
- **Fields**:
  - `id`: `UUID` (PK)
  - `execution_id`: `UUID` (FK `executions.id`, Not Null, Index)
  - `command`: `TEXT` (Not Null)
  - `status`: `VARCHAR(50)` (Not Null, default `"pending"`)
  - `pid`: `INTEGER` (Nullable)
  - `exit_code`: `INTEGER` (Nullable)
  - `stdout`: `TEXT` (Nullable, active stdout write buffer)
  - `stderr`: `TEXT` (Nullable, active stderr write buffer)
  - `last_heartbeat`: `TIMESTAMP` (Nullable, checked by orphan monitor)
  - `timeout_threshold`: `INTEGER` (Not Null, step-level limit in seconds)
  - `created_at`: `TIMESTAMP` (Not Null)
  - `updated_at`: `TIMESTAMP` (Not Null)
  - `is_archived`: `BOOLEAN` (Not Null)
- **Indexes**:
  - `idx_execution_steps_heartbeat` ON (`status`, `last_heartbeat`)
- **Lifecycle**: `pending` → `running` → `completed` / `failed` / `timed_out` / `cancelled`.

### 5. `audit_logs` (Immutable system log ledger)
- **Description**: Append-only event store. This table is intentionally **immutable**: it has **no** `updated_at` or `is_archived` fields, and `update`/`delete` statements are forbidden.
- **Fields**:
  - `id`: `UUID` (PK, default `uuid4`)
  - `event_type`: `VARCHAR(100)` (Not Null, Index)
  - `entity_type`: `VARCHAR(100)` (Not Null, Index)
  - `entity_id`: `UUID` (Nullable, Index)
  - `data`: `JSON` (Nullable, carries variable event context)
  - `correlation_id`: `UUID` (Nullable, Index, tracks tracing context)
  - `component`: `VARCHAR(100)` (Nullable)
  - `actor`: `VARCHAR(200)` (Nullable)
  - `created_at`: `TIMESTAMP` (Not Null, default `UTC_NOW`)
- **Indexes**:
  - `idx_audit_logs_correlation` ON (`correlation_id`)
  - `idx_audit_logs_entity` ON (`entity_type`, `entity_id`)

### 6. `workflow_checkpoints` (Compaction state checkpoints)
- **Description**: Serialized snapshots for paused or compacted workflow states.
- **Fields**:
  - `id`: `UUID` (PK)
  - `workflow_id`: `UUID` (Not Null, Index)
  - `step_name`: `VARCHAR(200)` (Not Null)
  - `state`: `JSON` (Not Null, serialized Pydantic memory states)
  - `completed_at`: `TIMESTAMP` (Nullable)
  - `created_at`: `TIMESTAMP` (Not Null)
  - `updated_at`: `TIMESTAMP` (Not Null)
  - `is_archived`: `BOOLEAN` (Not Null)

### 7. `research_jobs` (Scheduled information gathering)
- **Description**: Schedules and tracks automated research runs.
- **Fields**:
  - `id`: `UUID` (PK)
  - `task_id`: `UUID` (FK `tasks.id`, Nullable, Index)
  - `query`: `TEXT` (Not Null)
  - `schedule_cron`: `VARCHAR(100)` (Nullable, APScheduler format)
  - `status`: `VARCHAR(50)` (Not Null, default `"scheduled"`)
  - `last_run_at`: `TIMESTAMP` (Nullable)
  - `created_at`: `TIMESTAMP` (Not Null)
  - `updated_at`: `TIMESTAMP` (Not Null)
  - `is_archived`: `BOOLEAN` (Not Null)

### 8. `system_events` (Normalization and outbox cache)
- **Description**: Outbox cache table to track events generated before they are normalizing/dispatched.
- **Fields**:
  - `id`: `UUID` (PK)
  - `event_type`: `VARCHAR(100)` (Not Null)
  - `payload`: `JSON` (Not Null)
  - `status`: `VARCHAR(50)` (Not Null, default `"pending"`)
  - `created_at`: `TIMESTAMP` (Not Null)
- **Indexes**:
  - `idx_system_events_status` ON (`status`)
