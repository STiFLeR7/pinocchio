"""Shared enumerations for the Nexus control plane.

All enums inherit from ``str`` and ``enum.Enum`` so they serialise
cleanly to JSON via Pydantic and are usable as SQLAlchemy column values.
"""

from __future__ import annotations

import enum


class TaskStatus(enum.StrEnum):
    """Lifecycle states for a task."""

    CREATED = "created"
    QUEUED = "queued"
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ApprovalStatus(enum.StrEnum):
    """Decision states for an approval gate."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ExecutionStatus(enum.StrEnum):
    """Runtime states for an execution run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class OutboxStatus(enum.StrEnum):
    """Lifecycle states for an outbox message."""

    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"



class EventType(enum.StrEnum):
    """Canonical event types emitted throughout the system."""

    # Task lifecycle
    TASK_CREATED = "task.created"
    TASK_UPDATED = "task.updated"
    TASK_COMPLETED = "task.completed"
    TASK_CANCELLED = "task.cancelled"

    # Approval lifecycle
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_REJECTED = "approval.rejected"
    APPROVAL_EXPIRED = "approval.expired"

    # Execution lifecycle
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"
    EXECUTION_TIMED_OUT = "execution.timed_out"

    # Research
    RESEARCH_STARTED = "research.started"
    RESEARCH_COMPLETED = "research.completed"
    RESEARCH_FAILED = "research.failed"

    # Communication
    NOTIFICATION_SENT = "notification.sent"
    NOTIFICATION_FAILED = "notification.failed"

    # Reporting
    REPORT_GENERATED = "report.generated"

    # System
    SYSTEM_STARTED = "system.started"
    SYSTEM_STOPPED = "system.stopped"

    # Workflow
    WORKFLOW_CHECKPOINTED = "workflow.checkpointed"
    WORKFLOW_RESUMED = "workflow.resumed"

    # Sandbox lifecycle
    SANDBOX_CREATED = "sandbox.created"
    SANDBOX_STARTED = "sandbox.started"
    SANDBOX_TERMINATED = "sandbox.terminated"
    SANDBOX_TIMEOUT = "sandbox.timeout"
    SANDBOX_FAILURE = "sandbox.failure"

    # Scheduler job lifecycle (AP-103)
    SCHEDULER_JOB_STARTED = "scheduler.job.started"
    SCHEDULER_JOB_COMPLETED = "scheduler.job.completed"
    SCHEDULER_JOB_FAILED = "scheduler.job.failed"
    SCHEDULER_JOB_SKIPPED = "scheduler.job.skipped"


class AgentType(enum.StrEnum):
    """Logical agent roles within the orchestration layer."""

    RESEARCH = "research"
    PLANNING = "planning"
    EXECUTION = "execution"
    COMMUNICATION = "communication"
    MEMORY = "memory"


class RunnerType(enum.StrEnum):
    """Available execution runner backends."""

    GEMINI_CLI = "gemini_cli"
    CLAUDE_CODE = "claude_code"
    NEXUS_AGENT = "nexus_agent"
    # Deprecated codename alias for NEXUS_AGENT — retained for back-compat with persisted records.
    HERMES_AGENT = "hermes_agent"
    RESEARCH = "research"


class ExitStatus(enum.StrEnum):
    """Final disposition of an execution run."""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    ERROR = "error"


class Priority(int, enum.Enum):
    """Task priority levels (higher value = higher priority)."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
