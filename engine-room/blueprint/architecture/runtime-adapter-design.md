# Runtime Adapter Design

This document details the design of the AI Runtime Adapter system, establishing a common interface contract for all execution runtimes inside the Nexus Control Plane.

---

## 1. Class Interface: BaseRuntimeAdapter

All execution runtimes (Gemini CLI, Claude Code, Nexus Agent) must implement [BaseRuntimeAdapter](file:///D:/nexus/nexus/execution/runners/base.py) to decouple the workflow orchestration from runner-specific logic.

```python
class BaseRuntimeAdapter(ABC):
    """Abstract base class establishing the contract for all Nexus execution runtimes."""

    @abstractmethod
    async def initialize(self) -> None:
        """Verify runtime environment settings and CLI binary installations."""
        pass

    @abstractmethod
    async def validate(self, repository_path: str, command: str) -> None:
        """Execute pre-run governance checks (repository, command whitelist, branch)."""
        pass

    @abstractmethod
    async def execute(self, command: str) -> ExecutionResult:
        """Launch the runner subprocess, capture output logs, and stream updates."""
        pass

    @abstractmethod
    async def heartbeat(self) -> None:
        """Update last_heartbeat timestamp in database to prevent system timeout."""
        pass

    @abstractmethod
    async def checkpoint(self, step_name: str, state: dict[str, Any]) -> None:
        """Persist intermediate task checkpoint metadata to SQLite."""
        pass

    @abstractmethod
    async def terminate(self) -> None:
        """Gracefully terminate or force-kill the subprocess execution container."""
        pass

    @abstractmethod
    async def summarize(self) -> str:
        """Generate a structured markdown summary of the execution outputs."""
        pass

    @abstractmethod
    async def persist(self) -> None:
        """Commit all remaining logs, steps, and artifacts to the database."""
        pass
```

---

## 2. Concrete Adapters

### Gemini CLI Runtime Adapter
* **Class**: [GeminiRuntimeAdapter](file:///D:/nexus/nexus/execution/runners/gemini.py)
* **Implementation Details**:
  - Interacts with the Gemini API or wraps the Gemini terminal client.
  - Spawns subprocess scripts passing task parameters.
  - Monitors output streams using async buffers.

### Claude Code Runtime Adapter
* **Class**: [ClaudeCodeRuntimeAdapter](file:///D:/nexus/nexus/execution/runners/claude.py)
* **Implementation Details**:
  - Wraps the `claude-code` Node CLI binary.
  - Employs a virtual terminal wrapper (using pseudo-terminal buffers) to capture standard streams and handle interactive prompts.
  - Restricts prompt inputs using command policy parameters.

### Nexus Agent Runtime Adapter
* **Class**: [NexusRuntimeAdapter](file:///D:/nexus/nexus/execution/runners/nexus.py)
* **Implementation Details**:
  - Implements a custom Python-driven agent loop.
  - Connects to OpenRouter or local model endpoints for planning and file search.
  - Tracks tool-execution steps (e.g. file read, file edit, command exec) using a structured JSON calling model.
