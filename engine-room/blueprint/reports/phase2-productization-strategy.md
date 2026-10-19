# Phase 2 Productization Strategy & Workflow Ownership Review

This report outlines the operational strategy for Phase 2 Productization, addresses structural concerns regarding task models, and plans the outbox system reliability.

---

## 1. Productization Strategy Overview

Entering **Productization Mode** shifts focus from validating conceptual schemas to building an operational system. Our focus is guided by:
* **Interface Decoupling**: Maintain clear division between client handlers (Discord) and business services (`TaskService`, `ApprovalService`).
* **Real-time Observability**: Stream run commands and step outputs to logging channels so operators never have to trace logs in database servers.
* **Transactional Reliability**: Use transactional outbox models to bridge external API latency/outages (Discord, OpenRouter).

---

## 2. Workflow Ownership Review

### The Hazard: Task Model Bloat
A common design trap in agent architectures is allowing the `Task` model to absorb orchestration responsibilities—turning a simple work item record into a container tracking checkpoints, retry limits, notification counts, and summary digests.

### Current Evaluation
We evaluate the current fields and relationships of `TaskRecord`:
* **TaskRecord**: Contains only `id`, `created_at`, `updated_at`, `is_archived`, `title`, `description`, `status`, and `priority`.
* **Approvals & Executions**: Placed in separate, distinct tables (`approvals`, `executions`) referencing `task_id` as foreign keys.
* **Checkpoints**: Saved in `workflow_checkpoints` mapped to `workflow_id`.
* **Notifications**: Tracked in `audit_log` records by correlating transaction context.

**Conclusion**: The `TaskRecord` remains a clean, target work item. It has **not** absorbed orchestration state. 

### Trigger Conditions for WorkflowInstance
We will monitor the model boundaries. If any of the following conditions emerge in Phase 3 or Phase 4, we will author an ADR to formally introduce `WorkflowInstance` as a separate top-level primitive:
1. The orchestrator must model complex multi-task dependency trees (e.g. DAG structures where Task B starts only when Task A succeeds).
2. We need to track execution sessions across multiple different machines or distinct workspace directories for the same execution.
3. The parent orchestrator must support branching execution structures that bypass approvals depending on previous runtime outcomes.

---

## 3. Discord Mapping to Database State Machines

To ensure that the UI never bypasses security gates, Discord events map directly to internal transaction boundaries:

| Discord User Action | Triggered Event | Database Service Action | Resulting Task State |
|---|---|---|---|
| `/task create` | Input Ingestion | `TaskService.create_task` | `CREATED` -> `QUEUED` |
| System Auto-gate | Event Routing | `ApprovalService.create_approval_request` | `BLOCKED` (Waiting for owner sign-off) |
| Clicks `Approve` button | Button Interaction | `ApprovalService.evaluate_approval(APPROVED)` | `ACTIVE` (Task is ready to run) |
| Clicks `Reject` button | Button Interaction | `ApprovalService.evaluate_approval(REJECTED)` | `CANCELLED` |
| Runner Spawns | OS Subprocess | `ExecutionService.start_execution` | `ACTIVE` (Step: `running`) |
| Runner Finishes | Process Termination | `ExecutionService.finalize_execution` | `COMPLETED` or `FAILED` |

---

## 4. Transactional Outbox Sweeper Mechanics

To guarantee that no Discord notification is lost if the network drops:
1. When a database transaction writes to `tasks` or `approvals`, it writes a corresponding notification payload to the `system_events` table as part of the **same transaction**.
2. A background outbox loop reads all rows in `system_events` with `status == "pending"`.
3. The outbox dispatcher attempts to send the notification to the target Discord channel.
4. If the call succeeds, the row status is updated to `sent`.
5. If the call fails due to network outage or rate-limiting, the dispatcher backs off, leaving the row in `pending` to be retried on the next sweep.
