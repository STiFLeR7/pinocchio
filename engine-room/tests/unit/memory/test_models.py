"""Unit tests for SQLAlchemy models in the memory layer."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from nexus.memory.models import (
    ApprovalRecord,
    AuditLogRecord,
    ExecutionRecord,
    ExecutionStepRecord,
    KnowledgeItemRecord,
    ResearchItemRecord,
    ResearchJobRecord,
    SystemEventRecord,
    TaskRecord,
    WorkflowCheckpointRecord,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_task_record_creation(db_session: AsyncSession) -> None:
    """Verify that a TaskRecord can be created and saved in the DB."""
    task = TaskRecord(
        title="Test task",
        description="A task description",
        status="created",
        priority=2,
    )
    db_session.add(task)
    await db_session.flush()

    assert task.id is not None
    assert isinstance(task.id, uuid.UUID)
    assert task.title == "Test task"
    assert task.description == "A task description"
    assert task.status == "created"
    assert task.priority == 2
    assert task.created_at is not None
    assert task.updated_at is not None
    assert task.is_archived is False


def test_audit_log_is_append_only() -> None:
    """Verify that AuditLogRecord is immutable and append-only.

    It must inherit from AuditMixin (no updated_at or is_archived columns).
    """
    assert not hasattr(AuditLogRecord, "updated_at")
    assert not hasattr(AuditLogRecord, "is_archived")
    # Should still have id and created_at
    assert hasattr(AuditLogRecord, "id")
    assert hasattr(AuditLogRecord, "created_at")


def test_all_models_have_id() -> None:
    """Verify that all ORM models defined in models.py have an id attribute."""
    models = [
        TaskRecord,
        ApprovalRecord,
        ExecutionRecord,
        ExecutionStepRecord,
        AuditLogRecord,
        ResearchItemRecord,
        KnowledgeItemRecord,
        WorkflowCheckpointRecord,
        ResearchJobRecord,
        SystemEventRecord,
    ]
    for model in models:
        assert hasattr(model, "id")
        # Ensure it is a mapping/mapped attribute or class property
        assert hasattr(model, "__tablename__")


@pytest.mark.asyncio
async def test_new_models_creation(db_session: AsyncSession) -> None:
    """Verify that ExecutionStepRecord, ResearchJobRecord, and SystemEventRecord can be created."""
    task = TaskRecord(
        title="Parent Task",
        description="A parent task",
        status="created",
        priority=2,
    )
    db_session.add(task)
    await db_session.flush()

    execution = ExecutionRecord(
        task_id=task.id,
        runner="gemini_cli",
        repository="D:/projects/nexus",
    )
    db_session.add(execution)
    await db_session.flush()

    step = ExecutionStepRecord(
        execution_id=execution.id,
        command="git status",
        status="pending",
        timeout_threshold=60,
    )
    db_session.add(step)

    research_job = ResearchJobRecord(
        task_id=task.id,
        query="AI updates",
        schedule_cron="0 9 * * *",
        status="scheduled",
    )
    db_session.add(research_job)

    system_event = SystemEventRecord(
        event_type="TASK_CREATED",
        payload={"task_id": str(task.id)},
        status="pending",
    )
    db_session.add(system_event)
    await db_session.flush()

    assert step.id is not None
    assert step.execution_id == execution.id
    assert step.execution == execution
    assert step.command == "git status"
    assert step.timeout_threshold == 60

    assert research_job.id is not None
    assert research_job.task_id == task.id
    assert research_job.task == task
    assert research_job.schedule_cron == "0 9 * * *"

    assert system_event.id is not None
    assert system_event.event_type == "TASK_CREATED"
    assert system_event.payload == {"task_id": str(task.id)}
    assert system_event.status == "pending"
    assert not hasattr(SystemEventRecord, "updated_at")
