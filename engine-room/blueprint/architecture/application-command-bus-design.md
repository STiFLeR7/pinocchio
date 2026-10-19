# Application Command Bus Design

This document details the architectural design for introducing a formal Application Command Bus to decouple communication adapters from core transactional logic inside the Nexus Control Plane.

---

## 1. Concept Overview

A **Command Bus** is a behavioral pattern that acts as a message router, decoupling the request originator (e.g., [bot.py](file:///D:/nexus/nexus/communication/discord/bot.py)) from the operational handler that executes business rules. 

Under the current implementation, UI slash commands directly coordinate database sessions and invoke transactional logic. The Command Bus introduces an application boundary layer:

```
+------------------------------------+
|       Communication Adapter        |  (e.g., Discord Slash Command)
+-----------------+------------------+
                  |
                  | Dispatches Command Object
                  v
+-----------------+------------------+
|           Command Bus              |  (In-Memory Router)
+-----------------+------------------+
                  |
                  | Resolves and Invokes
                  v
+-----------------+------------------+
|         Command Handler            |  (Executes transactional boundaries)
+------------------------------------+
```

---

## 2. Sequential Workflows

### Current Discord Flow
In the current flow, UI components directly access the persistence layer, which creates high coupling:

```mermaid
sequenceDiagram
    autonumber
    actor User as Discord Operator
    participant Bot as discord/bot.py
    participant DB as database.py (get_session)
    participant Service as TaskService
    participant Memory as Memory Layer (SQLite)

    User->>Bot: Slash Command /task_create
    Note over Bot: Accesses bot.session_factory
    Bot->>DB: Open AsyncSession Context
    DB-->>Bot: yield session
    Bot->>Service: Instantiate TaskService(session, event_gateway)
    Bot->>Service: create_task(title, desc, priority)
    Service->>Memory: INSERT TaskRecord
    Service-->>Bot: TaskRecord (CREATED)
    Bot->>Service: change_status(task_id, TaskStatus.QUEUED)
    Service->>Memory: UPDATE TaskRecord Status
    Service-->>Bot: Updated Record
    Bot->>User: Reply text card "Task Ingested & Enqueued"
```

### Proposed Command Bus Flow
The proposed architecture isolates the communication layer, restricting it to command dispatching:

```mermaid
sequenceDiagram
    autonumber
    actor User as Discord Operator
    participant Bot as discord/bot.py
    participant Bus as Command Bus
    participant Handler as CreateTaskHandler
    participant DB as database.py (get_session)
    participant Service as TaskService
    participant Memory as Memory Layer (SQLite)

    User->>Bot: Slash Command /task_create
    Note over Bot: Instantiates CreateTaskCommand
    Bot->>Bus: dispatch(CreateTaskCommand)
    Bus->>Handler: handle(CreateTaskCommand)
    Note over Handler: Resolves dependencies and manages transaction
    Handler->>DB: Open AsyncSession Context
    DB-->>Handler: yield session
    Handler->>Service: Instantiate TaskService(session)
    Handler->>Service: create_task(title, desc, priority)
    Service->>Memory: INSERT TaskRecord
    Service-->>Handler: TaskRecord
    Handler->>Service: change_status(task_id, TaskStatus.QUEUED)
    Service->>Memory: UPDATE TaskRecord
    Service-->>Handler: Updated Record
    Handler-->>Bus: Success Result (Task ID)
    Bus-->>Bot: Command Result
    Bot->>User: Reply text card "Task Ingested & Enqueued"
```

---

## 3. Analysis of Flows

### Coupling Points
* **Current Flow**: [bot.py](file:///D:/nexus/nexus/communication/discord/bot.py) is directly coupled to [database.py](file:///D:/nexus/nexus/database.py), [TaskService](file:///D:/nexus/nexus/memory/task_service.py), and [ApprovalService](file:///D:/nexus/nexus/approvals/service.py).
* **Proposed Flow**: [bot.py](file:///D:/nexus/nexus/communication/discord/bot.py) is only coupled to the Command Bus interface and the command data transfer objects (DTOs).

### Hidden Dependencies
* In the current flow, database session management (such as transaction commits and rollbacks) is handled directly inside slash commands. If a session throws an error, the Discord interaction itself can fail if not caught, bypassing domain exceptions.
* In the proposed flow, transactions are contained within Command Handlers, ensuring that failures are translated into structured command responses.

### Testing Implications
* **Current Flow**: Testing requires complex mocks of Discord interaction objects and connection factories.
* **Proposed Flow**: Commands and handlers are pure Python objects that can be unit-tested without mocking any Discord components or invoking connection state frameworks.

### Future Maintenance
* As email gateways and runner platforms are added, they can reuse commands (`CreateTaskCommand`, `ApproveTaskCommand`) without duplicating database connection logic.
