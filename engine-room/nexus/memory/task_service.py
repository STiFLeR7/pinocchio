"""Task service layer mapping CRUD operations and status transition guards.

Enforces valid state shifts and emits lifecycle events via the gateway.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from nexus.core.exceptions import TaskEngineError
from nexus.core.types import TaskStatus
from nexus.memory.models import TaskRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from nexus.gateway.gateway import EventGateway
    from nexus.memory.service import MemoryService


# Strict Task state transition dictionary guards
VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.CREATED: {TaskStatus.QUEUED},
    TaskStatus.QUEUED: {TaskStatus.ACTIVE, TaskStatus.CANCELLED},
    TaskStatus.ACTIVE: {
        TaskStatus.BLOCKED,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.BLOCKED: {TaskStatus.ACTIVE, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
}


class TaskService:
    """Handles task creation, state validation, row locking, and status shifts."""

    def __init__(
        self,
        db_session: AsyncSession,
        memory_service: MemoryService,
        event_gateway: EventGateway | None = None,
    ) -> None:
        """Initialize the TaskService with DB session, memory service, and gateway."""
        self.session = db_session
        self.memory_service = memory_service
        self.event_gateway = event_gateway

    async def create_task(
        self,
        title: str,
        description: str | None = None,
        priority: int = 2,
        runtime_type: str | None = "cli",
        runtime_id: str | None = "gemini",
        execution_profile: str | None = "default",
        runtime_policy: str | None = "approved",
    ) -> TaskRecord:
        """Create a new task, insert it into the database, and log the created event."""
        task = TaskRecord(
            title=title,
            description=description,
            status=TaskStatus.CREATED.value,
            priority=priority,
            runtime_type=runtime_type,
            runtime_id=runtime_id,
            execution_profile=execution_profile,
            runtime_policy=runtime_policy,
        )
        self.session.add(task)
        await self.session.flush()

        # Write creation transition event
        from nexus.core.events import NexusEvent
        from nexus.core.types import EventType

        event = NexusEvent(
            event_type=EventType.TASK_CREATED,
            entity_type="task",
            entity_id=task.id,
            data={
                "title": title,
                "priority": priority,
                "status": TaskStatus.CREATED.value,
                "actor": "system",
            },
            source="task_engine",
        )
        await self.memory_service.log_event(event)

        if self.event_gateway is not None:
            await self.event_gateway.publish(event)

        return task

    async def get_task(self, task_id: uuid.UUID) -> TaskRecord | None:
        """Fetch a specific TaskRecord from the database."""
        stmt = select(TaskRecord).where(TaskRecord.id == task_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def change_status(
        self, task_id: uuid.UUID, new_status: TaskStatus, actor: str = "system"
    ) -> TaskRecord:
        """Apply status transition guard checks and commit the task status change atomically."""
        # 1. Acquire transaction lock (with_for_update compiles to database locks in SQLite)
        stmt = select(TaskRecord).where(TaskRecord.id == task_id).with_for_update()
        result = await self.session.execute(stmt)
        task = result.scalar_one_or_none()

        if task is None:
            raise TaskEngineError(f"Task with ID {task_id} not found.")

        current_status = TaskStatus(task.status)

        # 2. Assert transition validity (state machine guards)
        allowed = VALID_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise TaskEngineError(
                f"Invalid task transition from {current_status.value} to {new_status.value}."
            )

        # 3. Commit state column
        task.status = new_status.value
        await self.session.flush()

        # 4. Insert StateTransition AuditLogRecord
        from nexus.core.events import NexusEvent
        from nexus.core.types import EventType

        # Determine target EventType
        if new_status == TaskStatus.QUEUED:
            event_type = EventType.TASK_UPDATED  # Will trigger queue routing
            data = {"task_id": str(task.id), "queue_position": 1, "actor": actor}
        elif new_status == TaskStatus.COMPLETED:
            event_type = EventType.TASK_COMPLETED
            data = {"task_id": str(task.id), "actor": actor}
        elif new_status == TaskStatus.CANCELLED:
            event_type = EventType.TASK_CANCELLED
            data = {"task_id": str(task.id), "actor": actor}
        else:
            event_type = EventType.TASK_UPDATED
            data = {"task_id": str(task.id), "status": new_status.value, "actor": actor}

        event = NexusEvent(
            event_type=event_type,
            entity_type="task",
            entity_id=task.id,
            data=data,
            source="task_engine",
        )
        await self.memory_service.log_event(event)

        # 5. Dispatch Event to EventGateway
        if self.event_gateway is not None:
            await self.event_gateway.publish(event)

        return task
