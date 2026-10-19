# Nexus Event Model Specification

This document specifies the first-class event models routed through the **Nexus Event Gateway** (`nexus/gateway/`). All events are defined as strict, frozen Pydantic schemas.

---

## 1. Event Routing Schema Map

Every event inherits from the base `NexusEvent` envelope:
```python
class NexusEvent(BaseModel):
    id: UUID
    event_type: EventType
    entity_type: str
    entity_id: UUID | None
    data: dict[str, Any]
    correlation_id: UUID
    timestamp: datetime
    source: str
```

---

## 2. Event Catalog

### 1. `TaskCreated`
- **Producer**: API Subsystem (on task creation via HTTP POST `/api/v1/tasks`).
- **Consumer**: Task Engine (initializes lifecycle log entries), Event Gateway (writes `audit_logs`).
- **Payload Schema**:
  - `title`: `str`
  - `priority`: `int`
  - `status`: `str`

### 2. `TaskQueued`
- **Producer**: Task Engine (when a task moves from `created` to `queued`).
- **Consumer**: Scheduler (evaluates execution triggers), Event Gateway.
- **Payload Schema**:
  - `task_id`: `UUID`
  - `queue_position`: `int`

### 3. `TaskStarted`
- **Producer**: Task Engine (when task changes to `active`).
- **Consumer**: Execution Subsystem (initializes run structures).
- **Payload Schema**:
  - `task_id`: `UUID`
  - `runner`: `str`

### 4. `ApprovalRequested`
- **Producer**: Task Engine (when execution triggers a privileged action block).
- **Consumer**: Communication Subsystem (sends Discord embed approval cards, emails SMTP triggers).
- **Payload Schema**:
  - `task_id`: `UUID`
  - `approval_id`: `UUID`
  - `requester`: `str`
  - `expires_at`: `datetime`

### 5. `ApprovalGranted`
- **Producer**: Approval Engine (when owner Discord User ID approves the card).
- **Consumer**: Task Engine (unblocks execution task, sets status to `active`), Communication Subsystem (removes active Discord cards).
- **Payload Schema**:
  - `approval_id`: `UUID`
  - `decided_by`: `str` (Discord User ID)
  - `reason`: `str | None`

### 6. `ApprovalExpired`
- **Producer**: Scheduler / Approval Engine (when expiration sweeps detect the 24-hour limit is passed).
- **Consumer**: Task Engine (moves task back to review/cancelled queue), Communication Subsystem (notifies owner of expiration).
- **Payload Schema**:
  - `approval_id`: `UUID`
  - `expired_at`: `datetime`

### 7. `ExecutionStarted`
- **Producer**: Execution Subsystem (when subprocess begins).
- **Consumer**: Task Engine, Observer Dashboard.
- **Payload Schema**:
  - `execution_id`: `UUID`
  - `command`: `str`
  - `runner`: `str`

### 8. `ExecutionHeartbeat`
- **Producer**: Subprocess Runner (periodic signal sent while running).
- **Consumer**: Execution Subsystem (updates `last_heartbeat` in DB).
- **Payload Schema**:
  - `execution_id`: `UUID`
  - `timestamp`: `datetime`
  - `step_index`: `int`

### 9. `ExecutionCompleted`
- **Producer**: Subprocess Runner (on successful shell process exit code `0`).
- **Consumer**: Task Engine (moves status to `completed`), Memory Manager (evaluates state files).
- **Payload Schema**:
  - `execution_id`: `UUID`
  - `exit_code`: `int`
  - `output_summary`: `str`

### 10. `ExecutionFailed`
- **Producer**: Subprocess Runner (on non-zero exit codes or subprocess crashes).
- **Consumer**: Task Engine (moves status to `failed`), Communication Subsystem (delivers critical email/Discord alerts).
- **Payload Schema**:
  - `execution_id`: `UUID`
  - `exit_code`: `int`
  - `error_message`: `str`

### 11. `CheckpointCreated`
- **Producer**: Memory Manager (on dialog compaction/summarization).
- **Consumer**: Task Engine.
- **Payload Schema**:
  - `workflow_id`: `UUID`
  - `step_name`: `str`
  - `summary`: `str`

### 12. `ResearchCompleted`
- **Producer**: Research Agent (OpenRouter search run completes).
- **Consumer**: Memory Manager (writes to `knowledge_items`), Communication Subsystem (delivers Daily Summary reports).
- **Payload Schema**:
  - `job_id`: `UUID`
  - `findings_count`: `int`
