"""Service layer for persistence operations in the memory layer.

Provides transaction-locked writes, append-only audit logs, outbox queue entries,
and state checkpointing.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from nexus.memory.models import (
    AuditLogRecord,
    SystemEventRecord,
    WorkflowCheckpointRecord,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from nexus.core.events import NexusEvent


class MemoryService:
    """Service class encapsulating audit log and checkpoint persistence operations."""

    def __init__(self, db_session: AsyncSession) -> None:
        """Initialize the service with an active database session."""
        self.session = db_session

    async def log_event(self, event: NexusEvent, enqueue_outbox: bool = True) -> None:
        """Persist a canonical event to the append-only, immutable audit ledger."""
        actor = event.data.get("actor") or event.data.get("decided_by")
        audit_record = AuditLogRecord(
            id=event.id,
            event_type=(
                event.event_type.value
                if hasattr(event.event_type, "value")
                else str(event.event_type)
            ),
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            data=event.data,
            correlation_id=event.correlation_id,
            component=event.source,
            actor=str(actor) if actor is not None else None,
            created_at=event.timestamp,
        )
        self.session.add(audit_record)
        if enqueue_outbox:
            await self.enqueue_outbox_event(event)
        await self.session.flush()

    async def enqueue_outbox_event(self, event: NexusEvent) -> None:
        """Enqueue an event in the system_events outbox cache table for processing."""
        outbox_record = SystemEventRecord(
            id=event.id,
            event_type=(
                event.event_type.value
                if hasattr(event.event_type, "value")
                else str(event.event_type)
            ),
            payload=event.model_dump(mode="json"),
            status="pending",
        )
        self.session.add(outbox_record)
        await self.session.flush()

    async def create_checkpoint(
        self, workflow_id: uuid.UUID, step_name: str, state: dict[str, Any]
    ) -> uuid.UUID:
        """Create a state checkpoint snapshot for a resumable workflow."""
        checkpoint = WorkflowCheckpointRecord(
            workflow_id=workflow_id,
            step_name=step_name,
            state=state,
        )
        self.session.add(checkpoint)
        await self.session.flush()
        return checkpoint.id

    async def restore_checkpoint(self, workflow_id: uuid.UUID) -> dict[str, Any] | None:
        """Restore the latest checkpoint state snapshot for a workflow."""
        stmt = (
            select(WorkflowCheckpointRecord)
            .where(WorkflowCheckpointRecord.workflow_id == workflow_id)
            .order_by(WorkflowCheckpointRecord.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()
        return record.state if record else None
