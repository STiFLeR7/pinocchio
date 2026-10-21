# Runtime Primitives V2

This document identifies the fundamental runtime primitives (data structures, variables, handles, and execution parameters) utilized across CLI, Agent, and Research executors, separating shared attributes from category-specific primitives.

---

## 1. Shared Runtime Primitives

These primitives are present in every execution context and are managed directly by the memory, database, and scheduling subsystems:

* **`ExecutionID`** (UUID): Unique primary index tracking a specific runner execution record in the database.
* **`TaskID`** (UUID): Pointer to the parent orchestrator task authorization.
* **`Status`** (Enum): State flag representing runner life (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `TIMED_OUT`, `CANCELLED`).
* **`Time Bounds`** (`StartTime` / `EndTime`): DateTime markers tracking duration.
* **`Heartbeat`** (DateTime): Periodic pulse indicator written to SQLite to confirm execution liveness.
* **`CheckpointState`** (JSON): Arbitrary serialized dictionary representing runner state at a specific logic gate.
* **`SynthesisSummary`** (Text): Markdown synthesis compiled after execution.

---

## 2. Category-Specific Primitives

These primitives exist only within their respective execution boundaries and do not bleed into other runtimes.

```
+------------------------------------------------------------------------+
|                               Nexus Control Plane                      |
|                                                                        |
|   +-------------------+  +--------------------+  +------------------+  |
|   |   CLI Primitives  |  |  Agent Primitives  |  |Research Primit.  |  |
|   |                   |  |                    |  |                  |  |
|   |  - Command String |  |  - Goal / Prompt   |  | - Search Query   |  |
|   |  - Process Handle |  |  - Plan / Graph    |  | - Citation Source|  |
|   |  - stdout/stderr  |  |  - Reasoning Steps |  | - Ingested Fact  |  |
|   |  - Exit Code      |  |  - Tool Call / Args|  | - Report Document|  |
|   |  - Working Dir    |  |  - Tool Result     |  |                  |  |
|   |  - Timeout limit  |  |  - Agent Memory    |  |                  |  |
|   +-------------------+  +--------------------+  +------------------+  |
+------------------------------------------------------------------------+
```

### A. CLI Runtime Primitives
* **`Command`** (String): Raw command line input passed to the OS shell (e.g. `uv run pytest`).
* **`ProcessHandle`** (Subprocess Object): Object containing process ID (PID) and standard stream handles.
* **`stdout` / `stderr`** (Character Streams): OS standard output and standard error text accumulators.
* **`ExitCode`** (Integer): Standard exit indicator returned by the operating system process (e.g., `0` for success).
* **`WorkingDirectory`** (Path String): Destination directory path where the shell process executes.
* **`TimeoutLimit`** (Integer): Time limit in seconds before forcing termination.

### B. Agent Runtime Primitives
* **`Goal` / `Prompt`** (String): Description of the final target objective (e.g., *"Refactor authentication service encryption"*).
* **`Plan`** (Graph or List): Deconstructed sequence of sub-tasks compiled by the model.
* **`ToolCall`** (JSON / Object): Call definition containing:
  * `tool_name` (e.g., `write_file`)
  * `arguments` (e.g., `{"path": "auth.py", "content": "..."}`)
  * `call_id` (Unique string index)
* **`ToolResult`** (String / JSON): Outcome returned by the tool context after execution.
* **`ReasoningStep`** (Text): Chain-of-thought (CoT) trace mapping the agent's thoughts, plans, and observations.
* **`AgentMemory`** (JSON / Context Dict): Session memory variables passed between LLM reasoning iterations.

### C. Research Runtime Primitives
* **`ResearchQuery`** (String): API search query strings dispatched to external search providers (e.g. Google Search, arXiv API).
* **`CitationSource`** (JSON): Metadata mapping retrieved data back to origin (URL, Author, Date, Title).
* **`IngestedFact`** (Text): Extracted factual text segments recorded in SQLite database index.
* **`ReportDocument`** (Text / Markdown): Structured summary report output.
