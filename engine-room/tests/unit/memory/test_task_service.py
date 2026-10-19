"""Unit tests for the TaskService lifecycle and transition guards."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from nexus.core.events import NexusEvent
from nexus.core.exceptions import TaskEngineError
from nexus.core.types import EventType, TaskStatus
from nexus.gateway.gateway import EventGateway
from nexus.memory.models import AuditLogRecord
from nexus.memory.service import MemoryService
from nexus.memory.task_service import TaskService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_task_creation_flow(db_session: AsyncSession) -> None:
    """Verify TaskService correctly inserts TaskRecord and logs the creation event."""
    memory_service = MemoryService(db_session)
    gateway = EventGateway()
    task_service = TaskService(db_session, memory_service, gateway)

    published_events: list[NexusEvent] = []

    async def collect_events(event: NexusEvent) -> None:
        published_events.append(event)

    gateway.subscribe(EventType.TASK_CREATED, collect_events)

    task = await task_service.create_task(
        title="Implement Task Service",
        description="Write CRUD and transition guards",
        priority=3,
    )
    await db_session.flush()

    assert task.id is not None
    assert task.status == TaskStatus.CREATED.value

    # Verify event published
    assert len(published_events) == 1
    assert published_events[0].entity_id == task.id
    assert published_events[0].event_type == EventType.TASK_CREATED

    # Verify audit log recorded
    stmt = select(AuditLogRecord).where(AuditLogRecord.entity_id == task.id)
    res = await db_session.execute(stmt)
    audit_logs = res.scalars().all()
    assert len(audit_logs) == 1
    assert audit_logs[0].event_type == "task.created"


@pytest.mark.asyncio
async def test_valid_task_transitions(db_session: AsyncSession) -> None:
    """Verify that a task can transition through valid lifecycle states."""
    memory_service = MemoryService(db_session)
    task_service = TaskService(db_session, memory_service)

    task = await task_service.create_task("Transition Task")
    await db_session.flush()

    # CREATED -> QUEUED
    await task_service.change_status(task.id, TaskStatus.QUEUED)
    assert task.status == TaskStatus.QUEUED.value

    # QUEUED -> ACTIVE
    await task_service.change_status(task.id, TaskStatus.ACTIVE)
    assert task.status == TaskStatus.ACTIVE.value

    # ACTIVE -> BLOCKED
    await task_service.change_status(task.id, TaskStatus.BLOCKED)
    assert task.status == TaskStatus.BLOCKED.value

    # BLOCKED -> ACTIVE
    await task_service.change_status(task.id, TaskStatus.ACTIVE)
    assert task.status == TaskStatus.ACTIVE.value

    # ACTIVE -> COMPLETED
    await task_service.change_status(task.id, TaskStatus.COMPLETED)
    assert task.status == TaskStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_invalid_task_transitions(db_session: AsyncSession) -> None:
    """Verify that transition guards prevent illegal state changes."""
    memory_service = MemoryService(db_session)
    task_service = TaskService(db_session, memory_service)

    task = await task_service.create_task("Invalid Transitions")
    await db_session.flush()

    # CREATED -> ACTIVE is invalid
    with pytest.raises(TaskEngineError) as exc_info:
        await task_service.change_status(task.id, TaskStatus.ACTIVE)
    assert "Invalid task transition from created to active" in str(exc_info.value)

    # CREATED -> QUEUED is valid
    await task_service.change_status(task.id, TaskStatus.QUEUED)

    # QUEUED -> COMPLETED is invalid
    with pytest.raises(TaskEngineError):
        await task_service.change_status(task.id, TaskStatus.COMPLETED)

    # QUEUED -> ACTIVE is valid
    await task_service.change_status(task.id, TaskStatus.ACTIVE)

    # ACTIVE -> COMPLETED is valid
    await task_service.change_status(task.id, TaskStatus.COMPLETED)

    # Transitioning out of terminal COMPLETED state is invalid
    with pytest.raises(TaskEngineError):
        await task_service.change_status(task.id, TaskStatus.ACTIVE)
