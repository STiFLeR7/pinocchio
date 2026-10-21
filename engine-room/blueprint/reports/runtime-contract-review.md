# Runtime Contract Review

This report audits the base `BaseRuntimeAdapter` contract to identify implicit assumptions, generic behaviors, and points of friction for non-CLI runtimes (such as API-based autonomous agent runtimes like Nexus).

---

## 1. Audit of BaseRuntimeAdapter Methods

The standard [BaseRuntimeAdapter](file:///D:/nexus/nexus/execution/runners/base.py) defines the following contract:

```python
class BaseRuntimeAdapter(ABC):
    stdout_log: str
    stderr_log: str

    @abstractmethod
    async def initialize(self) -> None: ...
    @abstractmethod
    async def validate(self, repository_path: str, command: str) -> None: ...
    @abstractmethod
    async def execute(self, command: str) -> dict[str, Any]: ...
    @abstractmethod
    async def heartbeat(self) -> None: ...
    @abstractmethod
    async def checkpoint(self, step_name: str, state: dict[str, Any]) -> None: ...
    @abstractmethod
    async def terminate(self) -> None: ...
    @abstractmethod
    async def summarize(self) -> str: ...
    @abstractmethod
    async def persist(self) -> None: ...
```

---

## 2. Answers to Audit Questions

### 1. Which methods are truly generic?
* **`initialize()`**: Every runtime (CLI, subprocess, API, or hybrid) must setup its keys, connections, or initial configuration parameters before starting.
* **`heartbeat()`**: Required for all runtimes. Both background sub-processes and long-running API loops must update a temporal indicator (`last_heartbeat`) to prevent the scheduler from marking them as timed out.
* **`checkpoint(step_name, state)`**: Generic mechanism to record intermediate progress state. Any multi-step agent loop (including Nexus or Claude) or subprocess steps should checkpoint progress.
* **`summarize()`**: Generic requirement. Synthesizes run logs/traces into a clean markdown format using LLM complete APIs.

### 2. Which methods contain Gemini assumptions?
* **`persist()`**: The current implementation of `persist()` assumes git repository workspace structure and checks for `git diff` via subprocess. While generic for local repository modifications, it assumes the runtime itself modifies the repository locally rather than generating patches or running in a container.
* **`stdout_log` / `stderr_log` fields**: These fields assume that execution output streams exist in standard POSIX formats. Gemini CLI outputs stderr and stdout, but API-based/autonomous agents emit event logs, model traces, and tool calls.

### 3. Which methods assume subprocess execution?
* **`execute()`**: The adapter maps execution to a direct OS shell run.
* **`terminate()`**: Termination is expected to stop a running local process or kill a PID. For non-subprocess or API-based runtimes, termination requires signaling connection cancellation, terminating an API session, or stopping an event loop.

### 4. Which methods assume CLI execution?
* **`validate(repository_path, command)`**: The validation of a string `command` using blacklist string filters assumes the input is a single CLI shell invocation.
* **`execute(command)`**: Assumes that the runner accepts a single command string to execute.

### 5. Which methods would fail for Nexus-style API execution?
* **`validate()`**: Nexus receives a task prompt/goal (e.g. "Optimize query index in DB") rather than a single CLI shell command string. Validating a CLI command string fails to review what tools the autonomous agent will call dynamically during its API execution loop.
* **`execute()`**: Passing a shell command string is inapplicable to Nexus, which executes an iterative API agent loop (Reasoning -> Action -> Observation).
* **`stdout_log` / `stderr_log` property access**: Nexus doesn't output traditional standard output/error files. Reading these fields yields empty strings, missing vital execution trace history.
