"""Unit tests for the system enums."""

from __future__ import annotations

from nexus.core.types import (
    ApprovalStatus,
    EventType,
    ExitStatus,
    Priority,
    RunnerType,
    TaskStatus,
)


def test_task_status_members() -> None:
    """Verify TaskStatus members exist and serialize correctly."""
    assert TaskStatus.CREATED.value == "created"
    assert TaskStatus.QUEUED.value == "queued"
    assert TaskStatus.ACTIVE.value == "active"
    assert TaskStatus.BLOCKED.value == "blocked"
    assert TaskStatus.COMPLETED.value == "completed"
    assert TaskStatus.CANCELLED.value == "cancelled"
    assert TaskStatus.FAILED.value == "failed"


def test_approval_status_members() -> None:
    """Verify ApprovalStatus members exist and serialize correctly."""
    assert ApprovalStatus.PENDING.value == "pending"
    assert ApprovalStatus.APPROVED.value == "approved"
    assert ApprovalStatus.REJECTED.value == "rejected"
    assert ApprovalStatus.EXPIRED.value == "expired"
    assert ApprovalStatus.CANCELLED.value == "cancelled"


def test_execution_status_members() -> None:
    """Verify ExecutionStatus members exist and serialize correctly."""
    from nexus.core.types import ExecutionStatus

    assert ExecutionStatus.PENDING.value == "pending"
    assert ExecutionStatus.RUNNING.value == "running"
    assert ExecutionStatus.COMPLETED.value == "completed"
    assert ExecutionStatus.FAILED.value == "failed"
    assert ExecutionStatus.TIMED_OUT.value == "timed_out"
    assert ExecutionStatus.CANCELLED.value == "cancelled"


def test_event_types_are_strings() -> None:
    """Verify that all EventType enum values are strings."""
    for event_type in EventType:
        assert isinstance(event_type.value, str)
        assert isinstance(event_type, str)


def test_priority_values() -> None:
    """Verify that Priority values map to correct integers."""
    assert Priority.LOW.value == 1
    assert Priority.MEDIUM.value == 2
    assert Priority.HIGH.value == 3
    assert Priority.CRITICAL.value == 4


def test_runner_types() -> None:
    """Verify that all runner types exist."""
    assert RunnerType.GEMINI_CLI.value == "gemini_cli"
    assert RunnerType.CLAUDE_CODE.value == "claude_code"
    assert RunnerType.HERMES_AGENT.value == "hermes_agent"
    assert RunnerType.RESEARCH.value == "research"


def test_exit_status() -> None:
    """Verify ExitStatus members exist."""
    assert ExitStatus.SUCCESS.value == "success"
    assert ExitStatus.FAILURE.value == "failure"
    assert ExitStatus.TIMEOUT.value == "timeout"
    assert ExitStatus.CANCELLED.value == "cancelled"
    assert ExitStatus.ERROR.value == "error"
