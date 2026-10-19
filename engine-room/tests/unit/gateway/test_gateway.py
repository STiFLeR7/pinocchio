"""Unit tests for the EventGateway and event persistence mechanisms."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from nexus.core.events import NexusEvent
from nexus.core.types import EventType
from nexus.gateway.gateway import EventGateway
from nexus.memory.models import AuditLogRecord, SystemEventRecord
from nexus.memory.service import MemoryService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_event_gateway_routing() -> None:
    """Verify that EventGateway invokes subscriber callbacks on published events."""
    gateway = EventGateway()
    received_events = []

    async def sample_subscriber(event: NexusEvent) -> None:
        received_events.append(event)

    gateway.subscribe(EventType.TASK_CREATED, sample_subscriber)

    test_event = NexusEvent(
        event_type=EventType.TASK_CREATED,
        entity_type="task",
        entity_id=uuid.uuid4(),
        data={"title": "Verify gateway"},
        correlation_id=uuid.uuid4(),
        source="test",
    )

    await gateway.publish(test_event)

    assert len(received_events) == 1
    assert received_events[0].id == test_event.id
    assert received_events[0].data["title"] == "Verify gateway"


@pytest.mark.asyncio
async def test_event_persistence_in_audit_and_outbox(db_session: AsyncSession) -> None:
    """Verify that log_event and enqueue_outbox_event correctly populate the database."""
    service = MemoryService(db_session)
    corr_id = uuid.uuid4()
    entity_id = uuid.uuid4()

    event = NexusEvent(
        event_type=EventType.TASK_CREATED,
        entity_type="task",
        entity_id=entity_id,
        data={"title": "Test task title", "actor": " hill_patel"},
        correlation_id=corr_id,
        source="test_source",
    )

    # Persist the event to both audit_log and outbox
    await service.log_event(event, enqueue_outbox=False)
    await service.enqueue_outbox_event(event)
    await db_session.flush()

    # Query audit record
    from sqlalchemy import select

    audit_stmt = select(AuditLogRecord).where(AuditLogRecord.id == event.id)
    audit_res = await db_session.execute(audit_stmt)
    audit_record = audit_res.scalar_one()

    assert audit_record.event_type == "task.created"
    assert audit_record.entity_type == "task"
    assert audit_record.entity_id == entity_id
    assert audit_record.correlation_id == corr_id
    assert audit_record.component == "test_source"
    assert audit_record.actor == " hill_patel"
    assert audit_record.data == {"title": "Test task title", "actor": " hill_patel"}

    # Query outbox record
    outbox_stmt = select(SystemEventRecord).where(SystemEventRecord.id == event.id)
    outbox_res = await db_session.execute(outbox_stmt)
    outbox_record = outbox_res.scalar_one()

    assert outbox_record.event_type == "task.created"
    assert outbox_record.status == "pending"
    assert outbox_record.payload["id"] == str(event.id)
    assert outbox_record.payload["correlation_id"] == str(corr_id)
