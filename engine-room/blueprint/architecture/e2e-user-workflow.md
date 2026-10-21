# End-to-End MVP User Workflow

This document charts the sequence of execution steps from initial task ingestion on Discord to complete run finalization and recovery.

---

## 1. Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User as Operator (Discord)
    participant Bot as Discord Bot Task
    participant Api as FastAPI Services
    participant DB as SQLite WAL Memory
    participant Exec as Runner (Subprocess)
    participant LLM as OpenRouter Summarizer

    User->>Bot: Slash Command: /task create "Build auth"
    Bot->>Api: TaskCreate Schema
    Api->>DB: Insert TaskRecord (status="created")
    DB-->>Api: TaskRecord Created
    Api->>Api: Event: TASK_CREATED
    Api->>DB: Insert ApprovalRecord (status="pending")
    Api->>DB: Update TaskRecord (status="blocked")
    Api-->>Bot: Approval Created Callback
    Bot->>User: Post card in #approvals with Approve/Reject buttons

    User->>Bot: Clicks "Approve" button
    Bot->>Api: Verify owner ID & evaluate approval
    Api->>DB: SELECT FOR UPDATE on ApprovalRecord
    Note over Api,DB: Check if pending, check if owner authorized
    Api->>DB: Update ApprovalRecord (status="approved")
    Api->>DB: Update TaskRecord (status="active")
    Api->>Api: Event: APPROVAL_GRANTED
    Api-->>Bot: Update embed message card to green/approved
    Api->>Exec: start_execution() -> spawn subprocess
    Exec->>DB: Insert ExecutionRecord & ExecutionStepRecord

    loop Live Execution Logs
        Exec->>DB: Stream log lines to ExecutionStepRecord (stdout/stderr)
        Exec->>Bot: Write step commands to #execution-log
    end

    Exec-->>Api: Subprocess terminates (exit_code=0)
    Api->>DB: Finalize ExecutionRecord (exit_status="success")
    Api->>DB: Update TaskRecord (status="completed")
    Api->>Api: Event: TASK_COMPLETED
    
    Api->>LLM: Request summary (ContextFrame payload)
    LLM-->>Api: Generated text summary
    Api->>Bot: Publish report to #summaries
```

---

## 2. Timeline Step-by-Step

1. **Create Task**: Operator runs `/task create` inside Discord.
2. **Observe Task Persistence**: Task is persisted in SQLite database as `created`, then queued.
3. **Receive Approval Request**: Interactive card is posted to `#approvals` containing button widgets.
4. **Approve via Owner**: Designated owner clicks **Approve** button, validating user authorization.
5. **Trigger Execution**: Nexus engine transitions the task to `active` and spawns the configured command step.
6. **Record Execution Results**: Raw stdout/stderr terminal blocks are saved into the database execution step records.
7. **Generate Summary**: OpenRouter model parses the task and execution logs, writing a summary to `#summaries`.
8. **Verify Restart Recovery**:
   * If the Nexus process crashes during Step 5, upon reboot the startup lifecycle manager scans for running execution records.
   * Stale execution records are updated to `failed`/`timed_out`, and the parent task is cleanly rolled back to `FAILED` or re-queued, eliminating orphaned background tasks.
