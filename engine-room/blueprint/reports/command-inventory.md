# Command Inventory

This inventory catalogs the Application Commands within the Nexus Control Plane, classifying them by development phase.

---

## 1. Phase 2: Productization & Core Workflows

These commands define the minimum viable product (MVP) pipeline.

### CreateTaskCommand
* **Description**: Ingests a new task request and schedules it for execution.
* **Payload**:
  - `title: str` (The title of the task)
  - `description: str | None` (The task steps or scripts)
  - `priority: int` (The priority from 1 to 4)
* **Emitter**: Discord bot slash commands (`/task_create`), CLI endpoints.
* **Handler Impact**: Instantiates a record in [TaskRecord](file:///D:/nexus/nexus/memory/models.py), transitions status to `CREATED`, and automatically transitions to `QUEUED`.

### ApproveTaskCommand
* **Description**: Approves a pending gate, allowing execution to start.
* **Payload**:
  - `approval_id: UUID` (The unique identifier of the approval gate)
  - `decided_by: str` (The operator ID who approved it)
  - `reason: str` (Decision justification context logs)
* **Emitter**: Discord interactive views ([ApprovalView](file:///D:/nexus/nexus/communication/discord/bot.py#L31-L121) Click).
* **Handler Impact**: Sets approval status to `APPROVED`, transitions task to `ACTIVE`, and triggers subprocess runner hooks.

### RejectTaskCommand
* **Description**: Rejects execution, preventing runners from executing commands.
* **Payload**:
  - `approval_id: UUID`
  - `decided_by: str`
  - `reason: str`
* **Emitter**: Discord interactive views ([ApprovalView](file:///D:/nexus/nexus/communication/discord/bot.py#L31-L121) Click).
* **Handler Impact**: Sets approval status to `REJECTED`, sets task status to `FAILED`.

### StartExecutionCommand
* **Description**: Initializes runner records and launches terminal processes.
* **Payload**:
  - `task_id: UUID`
* **Emitter**: Workflow orchestrator daemon ([WorkflowOrchestrator](file:///D:/nexus/nexus/scheduling/orchestrator.py#L31-L55)).
* **Handler Impact**: Spawns OS subprocess and creates [ExecutionRecord](file:///D:/nexus/nexus/memory/models.py).

### CompleteExecutionCommand
* **Description**: Ends execution and saves results.
* **Payload**:
  - `execution_id: UUID`
  - `exit_status: ExitStatus`
  - `result_payload: dict[str, Any]`
* **Emitter**: Workflow orchestrator daemon ([WorkflowOrchestrator](file:///D:/nexus/nexus/scheduling/orchestrator.py#L31-L55)).
* **Handler Impact**: Updates status to `success` or `failure`, aggregates runner outputs, and triggers summaries.

---

## 2. Phase 3: Multi-Agent & Parallel Execution

These commands will support research and runner extensions in Phase 3.

### CreateResearchJobCommand
* **Description**: Initializes a parallel Web/Codebase research agent job.
* **Payload**:
  - `task_id: UUID`
  - `query: str`
  - `sources: list[str]`
* **Emitter**: Workflow orchestrator daemon.
* **Handler Impact**: Spawns research agent threads and adds records to `ResearchItemRecord`.

### CancelExecutionCommand
* **Description**: Immediately terminates running subprocesses.
* **Payload**:
  - `execution_id: UUID`
  - `reason: str`
* **Emitter**: Discord commands (`/task_cancel`), system timeout alerts.
* **Handler Impact**: Sends termination signals (SIGTERM/SIGKILL) to subprocesses.

---

## 3. Future Enhancements

Commands deferred beyond Phase 3.

### GenerateSummaryCommand
* **Description**: Manually requests OpenRouter to summarize execution logs.
* **Payload**:
  - `task_id: UUID`
* **Emitter**: Discord slash commands (`/task_summary`).
* **Handler Impact**: Invokes OpenRouter API and updates report logs.

### RetryTaskCommand
* **Description**: Re-runs a failed task from the last known checkpoint.
* **Payload**:
  - `task_id: UUID`
* **Emitter**: Operator UI button.
* **Handler Impact**: Loads task state and schedules a new execution.
