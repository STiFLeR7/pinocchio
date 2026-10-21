from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

DEFAULT_EXECUTION_TIMEOUT = 300


def resolve_execution_timeout(
    settings: Any, field_name: str, *, default: int = DEFAULT_EXECUTION_TIMEOUT
) -> int:
    """Resolve a runtime's execution timeout from settings, clamped by the hard limit (A-002).

    Reads ``settings.execution.<field_name>`` (e.g. ``claude_timeout``, ``gemini_timeout``,
    ``research_timeout``). Falls back to ``default`` when settings or the field are unavailable or
    non-numeric. The result is always clamped to ``settings.execution.hard_limit`` when configured,
    so the ADR-010 hard limit can never be exceeded.

    Replaces the v1.0.0 defect where runners read a non-existent ``research_timeout_seconds`` field
    and silently defaulted to 300s, ignoring configured per-runtime limits.
    """
    exec_cfg = getattr(settings, "execution", None) if settings is not None else None
    if exec_cfg is None:
        return default
    raw = getattr(exec_cfg, field_name, default)
    timeout = int(raw) if isinstance(raw, (int, float)) else default
    hard = getattr(exec_cfg, "hard_limit", None)
    if isinstance(hard, (int, float)):
        timeout = min(timeout, int(hard))
    return timeout


class BaseRuntimeAdapter(ABC):
    """Abstract base class defining the standard generic execution runtime adapter contract."""

    @abstractmethod
    async def initialize(self) -> None:
        """Verify runtime environment settings and installation files."""
        pass

    @abstractmethod
    async def heartbeat(self) -> None:
        """Update last_heartbeat timestamp in database to prevent task timeout."""
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
        """Commit all logs, steps, and artifacts to the database."""
        pass


class CLIRuntimeAdapter(BaseRuntimeAdapter, ABC):
    """Abstract base class for subprocess CLI command runners."""

    stdout_log: str
    stderr_log: str

    @abstractmethod
    async def validate(self, repository_path: str, command: str) -> None:
        """Execute pre-run governance checks (repository, branch, command safety)."""
        pass

    @abstractmethod
    async def execute(self, command: str) -> dict[str, Any]:
        """Launch runner subprocess, track stdout/stderr, and update metrics."""
        pass


class AgentRuntimeAdapter(BaseRuntimeAdapter, ABC):
    """Abstract base class for autonomous, API-driven agents."""

    @abstractmethod
    async def validate_goal(self, goal: str) -> None:
        """Verify the user goal does not violate security constraints."""
        pass

    @abstractmethod
    async def execute_goal(self, goal: str) -> dict[str, Any]:
        """Run the reasoning, planning, and action loop."""
        pass
