# Communication Boundary Review

This document audits the boundary lines of the Nexus Control Plane, evaluating where communication integrations intersect with operational and database states, and defines rules for separating Commands, Events, and Queries.

---

## 1. Boundary Audit & Coupling Points

An audit of the Phase 2 codebase highlights areas of direct coupling between the presentation layer (`communication/`) and persistence/domain layers (`memory/` and `approvals/`):

* **Direct DB Context Instantiation**: Inside [bot.py](file:///D:/nexus/nexus/communication/discord/bot.py#L226-L238), slash commands directly instantiate database sessions and control execution logic.
* **Service Dependency Leaks**: The Discord bot is directly responsible for managing state transitions (e.g., creating a task and immediately calling `task_service.change_status(task.id, TaskStatus.QUEUED)`). 
* **Stateful Views**: [ApprovalView](file:///D:/nexus/nexus/communication/discord/bot.py#L31-L121) holds a reference to the `session_factory` and coordinates approval evaluation internally on click events.

---

## 2. Command, Event, and Query Separation

To prevent boundary leakage, Nexus defines strict criteria for Commands, Events, and Queries (CQRS boundaries):

### Command
* **Definition**: An imperative request to mutate system state.
* **Characteristics**:
  - Named in the imperative mood (e.g., `CreateTask`, `ApproveTask`).
  - Dispatched by user interfaces (Discord command, Email gateway).
  - Routed to exactly **one** handler.
  - **Can fail**: Performs validation, checks business rules, and can raise exceptions.
* **Ownership**: Handlers reside in the Application service boundary layer and run database transaction scopes.

### Event
* **Definition**: A notification of a state mutation that has already occurred.
* **Characteristics**:
  - Named in the past tense (e.g., `TaskCreated`, `ApprovalGranted`).
  - Emitted by services or command handlers after a successful write transaction.
  - Routed to **zero or more** subscribers.
  - **Cannot block or fail the caller**: Propagated asynchronously to decouple downstream logic.
* **Ownership**: Managed by the [EventGateway](file:///D:/nexus/nexus/gateway/gateway.py) and transactional outbox sweeper ([outbox.py](file:///D:/nexus/nexus/gateway/outbox.py)).

### Query
* **Definition**: A read-only request for the current system state.
* **Characteristics**:
  - Named with query prefixes (e.g., `GetTask`, `ListTasks`).
  - Triggered by user interfaces to fetch data.
  - Side-effect free.
* **Ownership**: Executes against repositories or services directly, bypassing event loops.

---

## 3. Directory Ownership Rules

| Directory / Layer | Allowed Actions | Forbidden Actions |
| :--- | :--- | :--- |
| **`communication/`** | Dispatches Commands/Queries via Bus. Translates UI inputs into clean payload records. | Cannot import `sqlalchemy` components, manage sessions, or write directly to tables. |
| **`memory/`** | Implements data schema models and basic database operations. | Cannot import `discord`, CLI runners, or open network sockets. |
| **`events/`** | Distributes and routes past-tense events. | Cannot execute business mutations directly. |
| **`execution/`** | Runs isolated subprocesses and streams stdout log packets. | Cannot modify task parent metadata status records directly. |
