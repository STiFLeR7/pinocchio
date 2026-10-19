"""SQLAlchemy 2.x ORM models for the Nexus memory layer.

Every mutable table includes ``id``, ``created_at``, ``updated_at``, and
``is_archived``.  The ``audit_log`` table is intentionally immutable and
append-only — it omits ``updated_at`` and ``is_archived``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nexus.database import AuditMixin, Base, TimestampMixin

# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


class TaskRecord(TimestampMixin, Base):
    """A unit of work tracked by the orchestration layer."""

    __tablename__ = "tasks"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="created",
        index=True,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    runtime_type: Mapped[str | None] = mapped_column(String(50), nullable=True, default="cli")
    runtime_id: Mapped[str | None] = mapped_column(String(50), nullable=True, default="gemini")
    execution_profile: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default="default"
    )
    runtime_policy: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default="approved"
    )

    # Relationships
    approvals: Mapped[list[ApprovalRecord]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    executions: Mapped[list[ExecutionRecord]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    research_jobs: Mapped[list[ResearchJobRecord]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------


class ApprovalRecord(TimestampMixin, Base):
    """An approval gate guarding task execution."""

    __tablename__ = "approvals"

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    decided_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    task: Mapped[TaskRecord] = relationship(back_populates="approvals")
    executions: Mapped[list[ExecutionRecord]] = relationship(
        back_populates="approval",
        lazy="selectin",
    )


# ---------------------------------------------------------------------------
# Executions
# ---------------------------------------------------------------------------


class ExecutionRecord(TimestampMixin, Base):
    """A single execution run of a task by a runner backend."""

    __tablename__ = "executions"

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    approval_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("approvals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    runner: Mapped[str] = mapped_column(String(100), nullable=False)
    repository: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_heartbeat: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    timeout_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    exit_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    logs: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    task: Mapped[TaskRecord] = relationship(back_populates="executions")
    approval: Mapped[ApprovalRecord | None] = relationship(back_populates="executions")
    steps: Mapped[list[ExecutionStepRecord]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    agent_steps: Mapped[list[AgentStepRecord]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    artifacts: Mapped[list[ExecutionArtifactRecord]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# ---------------------------------------------------------------------------
# Audit log (immutable, append-only)
# ---------------------------------------------------------------------------


class AuditLogRecord(AuditMixin, Base):
    """Immutable, append-only audit trail of all system events.

    This table deliberately omits ``updated_at`` and ``is_archived``
    — records are never modified or soft-deleted.
    """

    __tablename__ = "audit_log"

    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # type: ignore[type-arg]
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    component: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actor: Mapped[str | None] = mapped_column(String(200), nullable=True)


# ---------------------------------------------------------------------------
# Research items
# ---------------------------------------------------------------------------


class ResearchItemRecord(TimestampMixin, Base):
    """A research finding or reference collected by a research agent."""

    __tablename__ = "research_items"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)  # type: ignore[type-arg]


# ---------------------------------------------------------------------------
# Research findings (AP-306)
# ---------------------------------------------------------------------------


class ResearchFindingRecord(TimestampMixin, Base):
    """A formal research finding record containing structured discovery metadata (AP-306)."""

    __tablename__ = "research_findings"

    source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)  # type: ignore[type-arg]
    importance_score: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


# ---------------------------------------------------------------------------
# Briefings (AP-307)
# ---------------------------------------------------------------------------


class BriefingRecord(TimestampMixin, Base):
    """A formal briefing record containing generated operational digests (AP-307)."""

    __tablename__ = "briefings"

    briefing_type: Mapped[str] = mapped_column(String(100), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    delivery_channels: Mapped[list | None] = mapped_column(JSON, nullable=True)  # type: ignore[type-arg]
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)


# ---------------------------------------------------------------------------
# Knowledge items
# ---------------------------------------------------------------------------


class KnowledgeItemRecord(TimestampMixin, Base):
    """A distilled knowledge item in the persistent knowledge base."""

    __tablename__ = "knowledge_items"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)  # type: ignore[type-arg]


# ---------------------------------------------------------------------------
# Workflow checkpoints
# ---------------------------------------------------------------------------


class WorkflowCheckpointRecord(TimestampMixin, Base):
    """Checkpoint snapshot for resumable workflow state."""

    __tablename__ = "workflow_checkpoints"

    workflow_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    step_name: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # type: ignore[type-arg]
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


# ---------------------------------------------------------------------------
# Execution Steps
# ---------------------------------------------------------------------------


class ExecutionStepRecord(TimestampMixin, Base):
    """An individual command invocation step under an execution run."""

    __tablename__ = "execution_steps"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    command: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    timeout_threshold: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    execution: Mapped[ExecutionRecord] = relationship(back_populates="steps")


# ---------------------------------------------------------------------------
# Agent Steps
# ---------------------------------------------------------------------------


class AgentStepRecord(TimestampMixin, Base):
    """An individual reasoning, thought, or tool execution step under an agent execution run."""

    __tablename__ = "agent_steps"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    thought: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tool_arguments: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # type: ignore[type-arg]
    tool_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )
    last_heartbeat: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    execution: Mapped[ExecutionRecord] = relationship(back_populates="agent_steps")


# ---------------------------------------------------------------------------
# Research Jobs
# ---------------------------------------------------------------------------


class ResearchJobRecord(TimestampMixin, Base):
    """Schedules and tracks automated research runs."""

    __tablename__ = "research_jobs"

    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    schedule_cron: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="scheduled",
        index=True,
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    task: Mapped[TaskRecord | None] = relationship(back_populates="research_jobs")


# ---------------------------------------------------------------------------
# System Events (Outbox Cache)
# ---------------------------------------------------------------------------


class SystemEventRecord(AuditMixin, Base):
    """Outbox cache table to track events before they are normalized/dispatched."""

    __tablename__ = "system_events"

    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)  # type: ignore[type-arg]
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )


# ---------------------------------------------------------------------------
# System Outbox (Decoupled Messaging)
# ---------------------------------------------------------------------------


class SystemOutboxRecord(TimestampMixin, Base):
    """Outbox table for decoupled asynchronous message dispatch."""

    __tablename__ = "system_outbox"

    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)  # type: ignore[type-arg]
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# Persistent Telemetry Metrics (AP-502)
# ---------------------------------------------------------------------------


class SystemMetricRawRecord(AuditMixin, Base):
    """Raw telemetry metric readings (7 days retention)."""

    __tablename__ = "system_metrics_raw"

    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metric_value: Mapped[float] = mapped_column(nullable=False)
    release_version: Mapped[str] = mapped_column(String(50), nullable=False)


class SystemMetricAggregateRecord(TimestampMixin, Base):
    """Aggregated historical performance telemetry (90 days retention)."""

    __tablename__ = "system_metrics_aggregates"

    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    avg_value: Mapped[float] = mapped_column(nullable=False)
    max_value: Mapped[float] = mapped_column(nullable=False)
    min_value: Mapped[float] = mapped_column(nullable=False)
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_version: Mapped[str] = mapped_column(String(50), nullable=False)
    release_version: Mapped[str] = mapped_column(String(50), nullable=False)
    measurement_window: Mapped[str] = mapped_column(String(50), nullable=False)  # 'hourly', 'daily'
    aggregated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


# ---------------------------------------------------------------------------
# Repository Governance Registry
# ---------------------------------------------------------------------------


class RepositoryRegistryRecord(TimestampMixin, Base):
    """Registry of approved repositories and validation rules for subprocess execution."""

    __tablename__ = "repository_registry"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    absolute_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    allowed_branches: Mapped[Any] = mapped_column(JSON, nullable=False)
    allowed_commands: Mapped[Any] = mapped_column(JSON, nullable=False)
    timeout_limit_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    # AP-304 additions
    allowed_runtimes: Mapped[Any] = mapped_column(JSON, nullable=True)
    allowed_profiles: Mapped[Any] = mapped_column(JSON, nullable=True)
    blocked_branches: Mapped[Any] = mapped_column(JSON, nullable=True)
    protected_branches: Mapped[Any] = mapped_column(JSON, nullable=True)
    owner: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    concurrency_limit_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    command_blacklist_additions: Mapped[Any] = mapped_column(JSON, nullable=True)

    @property
    def repository_id(self) -> uuid.UUID:
        return self.id

    @property
    def repository_name(self) -> str:
        return self.name

    @repository_name.setter
    def repository_name(self, value: str) -> None:
        self.name = value

    @property
    def repository_path(self) -> str:
        return self.absolute_path

    @repository_path.setter
    def repository_path(self, value: str) -> None:
        self.absolute_path = value


# ---------------------------------------------------------------------------
# Execution Artifacts
# ---------------------------------------------------------------------------


class ExecutionArtifactRecord(TimestampMixin, Base):
    """First-class execution result artifacts (diffs, patches, outputs)."""

    __tablename__ = "execution_artifacts"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # type: ignore[type-arg]

    # Relationships
    execution: Mapped[ExecutionRecord] = relationship(back_populates="artifacts")


# ---------------------------------------------------------------------------
# Governance Semaphores
# ---------------------------------------------------------------------------


class GovernanceSemaphoreRecord(TimestampMixin, Base):
    """Semaphore table for atomic concurrency validation gating."""

    __tablename__ = "governance_semaphores"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    is_locked: Mapped[bool] = mapped_column(nullable=False, default=False)


# ---------------------------------------------------------------------------
# System Policies
# ---------------------------------------------------------------------------


class SystemPolicyRecord(TimestampMixin, Base):
    """Global platform-wide policy settings."""

    __tablename__ = "system_policies"

    policy_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    policy_value: Mapped[Any] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by: Mapped[str | None] = mapped_column(String(200), nullable=True)


class SystemPolicyHistoryRecord(TimestampMixin, Base):
    """Immutable historical log of all policy modifications for auditability."""

    __tablename__ = "system_policy_history"

    policy_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    policy_value: Mapped[Any] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False, default="update")
