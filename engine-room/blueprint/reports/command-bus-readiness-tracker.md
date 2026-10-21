# Command Bus Readiness Tracker

This document tracks all system ingress points inside the Nexus Control Plane to serve as the migration guide for the Phase 3 Application Command Bus transition.

---

## 1. Tracker Registry

| Ingress Source | Current Implementation Path | Future Command Mapping | Coupling Score |
| :--- | :--- | :--- | :--- |
| **Discord Slash Command** `/task_create` | Direct call to [TaskService.create_task](file:///D:/nexus/nexus/memory/task_service.py) & [TaskService.change_status](file:///D:/nexus/nexus/memory/task_service.py) via bot session context. | `CreateTaskCommand` | **5 / 5** (Direct DB session control & transaction block ownership) |
| **Discord Interactive Button** `Approve` | Direct call to [ApprovalService.evaluate_approval](file:///D:/nexus/nexus/approvals/service.py) via [ApprovalView.handle_decision](file:///D:/nexus/nexus/communication/discord/bot.py#L48-L102). | `ApproveTaskCommand` | **5 / 5** (Direct service call, parameter mapping, and state validation) |
| **Discord Interactive Button** `Reject` | Direct call to [ApprovalService.evaluate_approval](file:///D:/nexus/nexus/approvals/service.py) via [ApprovalView.handle_decision](file:///D:/nexus/nexus/communication/discord/bot.py#L48-L102). | `RejectTaskCommand` | **5 / 5** (Direct service call, parameter mapping, and state validation) |
| **Discord Slash Command** `/task_list` | Direct SQL SELECT query on `TaskRecord` within custom bot command callbacks. | `ListTasksQuery` | **4 / 5** (Direct SQL queries on ORM maps inside UI handlers) |
| **Discord Slash Command** `/task_status` | Direct query call to [TaskService.get_task](file:///D:/nexus/nexus/memory/task_service.py) via bot command. | `GetTaskQuery` | **4 / 5** (Direct service dependency on presentation layer) |
| **Outbox Sweep Trigger** | Sweep reads `SystemEventRecord` and invokes [dispatch_outbox_event](file:///D:/nexus/nexus/gateway/outbox.py). | `ProcessOutboxQueueCommand` | **3 / 5** (Coupled to Discord channels mapping structure) |
| **Runner Process Termination** | Triggered by orchestrator thread tracking completion of execution subprocess. | `CompleteExecutionCommand` | **3 / 5** (Direct integration in orchestrator callback pipelines) |

---

## 2. Ingress Coupling Metrics Guidance

We rate coupling scores using the following criteria:

* **5 / 5 (Extreme Coupling)**: UI/network adapter directly instantiates SQLAlchemy sessions, creates transactions, performs multiple service writes, and runs state updates.
* **4 / 5 (High Coupling)**: UI/network adapter queries the ORM model space directly or holds strong dependencies on service instances for read operations.
* **3 / 5 (Moderate Coupling)**: Sub-system invokes orchestration components directly, but maps parameters into clean DTO objects first.
* **1-2 / 5 (Low Coupling)**: Target component triggers asynchronously via decoupled event signals.

---

## 3. Migration Action Plan (Phase 3 Gate)

At the start of Phase 3, we will execute the following steps to clear this registry:

1. **Implement Core Bus**: Build a simple command dispatch loop that resolves handlers based on command type mapping.
2. **Decouple Command Handlers**: Migrate all database session instantiations out of [bot.py](file:///D:/nexus/nexus/communication/discord/bot.py) and into command handler files.
3. **Decouple Queries**: Migrate direct queries out of bot slash commands into specialized read queries (e.g. `ListTasksQuery`).
