# ADR: Command Bus Evaluation

## Status
**Adopt During Phase 3**

---

## 1. Context

The Nexus Control Plane has successfully completed the foundation layer (Phase 1) and is productizing its core workflows (Phase 2). However, the recent integration health audit revealed that the presentation layer ([bot.py](file:///D:/nexus/nexus/communication/discord/bot.py)) directly interacts with the database persistence layer ([database.py](file:///D:/nexus/nexus/database.py)), manages context transaction loops, and instantiates operational services ([TaskService](file:///D:/nexus/nexus/memory/task_service.py), [ApprovalService](file:///D:/nexus/nexus/approvals/service.py)).

As we prepare to add more communication adapters (Email, custom HTTP APIs) and diverse execution runner agents (Gemini, Claude, Nexus), continuing to execute operational logic directly inside UI controllers will lead to duplicated code and leaking boundaries.

---

## 2. Alternatives Considered

### Alternative A: Adopt Now
Refactor the current codebase immediately to introduce a Command Bus prior to completing Phase 2.

* **Pros**:
  - Eliminates architectural debt immediately.
  - Ensures all subsequent Phase 2 features conform to clean boundary patterns.
* **Cons**:
  - Delays Phase 2 acceptance and delivery.
  - Risk of introducing bugs into the verified, passing E2E test suite ([test_mvp_workflow.py](file:///D:/nexus/tests/e2e/test_mvp_workflow.py)).

### Alternative B: Adopt During Phase 3 (Recommended)
Finalize Phase 2 productization using the current design, and mandate the implementation of the Command Bus at the start of Phase 3 before writing any agent expansion code.

* **Pros**:
  - Allows immediate delivery and verification of Phase 2 business logic.
  - Aligns the refactor with the introduction of parallel agent runner tasks in Phase 3, which benefit the most from decoupled command execution.
* **Cons**:
  - Temporary duplication of database setup blocks persists during Phase 2.

### Alternative C: Reject
Do not implement a Command Bus; continue invoking services directly from controllers.

* **Pros**:
  - Avoids class overhead and extra boilerplates.
* **Cons**:
  - High risk of spaghetti code and boundary degradation as new runner platforms are added.

---

## 3. Decision Rationale

We select **Alternative B: Adopt During Phase 3**.

* **Focus on Value**: The primary objective of Phase 2 is productization and E2E validation. Introducing structural refactoring at this stage delays delivery.
* **Proactive Boundary Protection**: Deferring the Command Bus to Phase 3 prevents it from becoming permanent technical debt, while ensuring that the upcoming multi-agent runners are built on a decoupled architecture.

---

## 4. Implementation Path (Phase 3 Start)

1. Introduce a lightweight `CommandBus` interface.
2. Port [bot.py](file:///D:/nexus/nexus/communication/discord/bot.py) slash commands to dispatch command DTOs.
3. Migrate database session blocks from `bot.py` into dedicated command handlers.
