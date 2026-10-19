"""Unit tests for the AP-501 Decoupled Communication Outbox."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nexus.communication.discord.service import DiscordService
from nexus.communication.email.service import EmailService
from nexus.gateway.communication_outbox import (
    lease_outbox_items,
    process_outbox_item,
)
from nexus.memory.models import AuditLogRecord, BriefingRecord, SystemOutboxRecord


@pytest.fixture
def mock_discord() -> DiscordService:
    service = MagicMock(spec=DiscordService)
    service.post_message = AsyncMock(return_value=MagicMock())
    return service


@pytest.fixture
def mock_email() -> EmailService:
    service = MagicMock(spec=EmailService)
    service.send_briefing_email = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_outbox_processing_success(
    db_session: AsyncSession,
    mock_discord: DiscordService,
) -> None:
    """Verify that a pending outbox item is leased, processed successfully, and status updated."""
    # Seed a BriefingRecord
    briefing_id = uuid.uuid4()
    briefing = BriefingRecord(
        id=briefing_id,
        briefing_type="morning",
        generated_at=datetime.now(UTC),
        delivery_channels=[],
        content_hash="hash123",
        finding_count=0,
        status="pending",
        summary="Briefing Content",
    )
    db_session.add(briefing)

    # Seed Outbox record
    item_id = uuid.uuid4()
    correlation_id = uuid.uuid4()
    outbox_item = SystemOutboxRecord(
        id=item_id,
        channel="discord",
        payload={"content": "Hello Discord"},
        status="pending",
        correlation_id=correlation_id,
        source_type="briefing",
        source_id=briefing_id,
        max_attempts=5,
    )
    db_session.add(outbox_item)
    await db_session.commit()

    # Create session factory
    class MockEngine:
        pass
    MockEngine()
    session_maker = async_sessionmaker(db_session.bind, expire_on_commit=False)

    # Lease
    worker_id = "worker-1"
    leased = await lease_outbox_items(db_session, worker_id, limit=5)
    assert len(leased) == 1
    assert leased[0].id == item_id
    assert leased[0].status == "processing"
    assert leased[0].worker_id == worker_id

    # Process
    await process_outbox_item(
        session_maker, item_id, worker_id, mock_discord, None
    )

    # Reload under fresh query
    db_session.expire_all()
    stmt = select(SystemOutboxRecord).where(SystemOutboxRecord.id == item_id)
    res = await db_session.execute(stmt)
    record = res.scalar_one()

    assert record.status == "sent"
    assert record.delivered_at is not None
    mock_discord.post_message.assert_called_once()

    # Verify briefing status updated to sent
    stmt_b = select(BriefingRecord).where(BriefingRecord.id == briefing_id)
    res_b = await db_session.execute(stmt_b)
    briefing_reloaded = res_b.scalar_one()
    await db_session.refresh(briefing_reloaded)
    assert briefing_reloaded.status == "sent"
    assert "discord" in briefing_reloaded.delivery_channels



@pytest.mark.asyncio
async def test_outbox_processing_retry(
    db_session: AsyncSession,
    mock_discord: DiscordService,
) -> None:
    """Verify that a delivery failure increments attempt_count and transitions status to retrying."""
    mock_discord.post_message.side_effect = Exception("Rate limit reached")

    item_id = uuid.uuid4()
    outbox_item = SystemOutboxRecord(
        id=item_id,
        channel="discord",
        payload={"content": "Retry Me"},
        status="pending",
        correlation_id=uuid.uuid4(),
        source_type="briefing",
        source_id=uuid.uuid4(),
        max_attempts=5,
    )
    db_session.add(outbox_item)
    await db_session.commit()

    session_maker = async_sessionmaker(db_session.bind, expire_on_commit=False)

    # Lease
    worker_id = "worker-2"
    leased = await lease_outbox_items(db_session, worker_id)
    assert len(leased) == 1

    # Process
    await process_outbox_item(
        session_maker, item_id, worker_id, mock_discord, None
    )

    # Reload
    db_session.expire_all()
    stmt = select(SystemOutboxRecord).where(SystemOutboxRecord.id == item_id)
    res = await db_session.execute(stmt)
    record = res.scalar_one()

    assert record.status == "retrying"
    assert record.attempt_count == 1
    assert "Rate limit" in record.last_error
    assert record.next_retry_at is not None
    assert record.worker_id is None


@pytest.mark.asyncio
async def test_outbox_processing_dead_letter(
    db_session: AsyncSession,
    mock_discord: DiscordService,
) -> None:
    """Verify that exceeding max_attempts flags the message as dead_letter and records an audit failure."""
    mock_discord.post_message.side_effect = Exception("Permanent failure")

    briefing_id = uuid.uuid4()
    briefing = BriefingRecord(
        id=briefing_id,
        briefing_type="morning",
        generated_at=datetime.now(UTC),
        delivery_channels=[],
        content_hash="hash_dl",
        finding_count=0,
        status="pending",
        summary="Dead letter briefing summary",
    )
    db_session.add(briefing)

    item_id = uuid.uuid4()
    outbox_item = SystemOutboxRecord(
        id=item_id,
        channel="discord",
        payload={"content": "Dead Letter"},
        status="pending",
        attempt_count=4,  # Current attempt + 1 will hit max_attempts
        max_attempts=5,
        correlation_id=uuid.uuid4(),
        source_type="briefing",
        source_id=briefing_id,
    )
    db_session.add(outbox_item)
    await db_session.commit()

    session_maker = async_sessionmaker(db_session.bind, expire_on_commit=False)

    # Lease
    worker_id = "worker-3"
    await lease_outbox_items(db_session, worker_id)

    # Process
    await process_outbox_item(
        session_maker, item_id, worker_id, mock_discord, None
    )

    # Reload outbox
    db_session.expire_all()
    stmt = select(SystemOutboxRecord).where(SystemOutboxRecord.id == item_id)
    res = await db_session.execute(stmt)
    record = res.scalar_one()

    assert record.status == "dead_letter"
    assert record.attempt_count == 5

    # Verify audit failure logged
    audit_stmt = select(AuditLogRecord).where(
        AuditLogRecord.event_type == "notification.failed"
    )
    audit_res = await db_session.execute(audit_stmt)
    audit_records = audit_res.scalars().all()
    assert len(audit_records) > 0
    assert audit_records[0].entity_id == item_id

    # Verify briefing status updated
    briefing_stmt = select(BriefingRecord).where(BriefingRecord.id == briefing_id)
    briefing_res = await db_session.execute(briefing_stmt)
    briefing_reloaded = briefing_res.scalar_one()
    await db_session.refresh(briefing_reloaded)
    assert briefing_reloaded.status == "failed"



@pytest.mark.asyncio
async def test_outbox_leasing_duplicate_prevention(
    db_session: AsyncSession,
) -> None:
    """Verify that multiple concurrent workers cannot lease the same outbox item."""
    item_id = uuid.uuid4()
    outbox_item = SystemOutboxRecord(
        id=item_id,
        channel="discord",
        payload={"content": "Concur Test"},
        status="pending",
        correlation_id=uuid.uuid4(),
        source_type="briefing",
        source_id=uuid.uuid4(),
        max_attempts=5,
    )
    db_session.add(outbox_item)
    await db_session.commit()

    # Worker A leases
    worker_a = "worker-a"
    leased_a = await lease_outbox_items(db_session, worker_a)
    assert len(leased_a) == 1
    assert leased_a[0].id == item_id

    # Worker B tries to lease
    worker_b = "worker-b"
    leased_b = await lease_outbox_items(db_session, worker_b)
    assert len(leased_b) == 0  # Already leased by worker-a


@pytest.mark.asyncio
async def test_outbox_lease_expiry_recovery(
    db_session: AsyncSession,
) -> None:
    """Verify that an expired processing lease is recovered and can be leased by a new worker."""
    item_id = uuid.uuid4()
    # Seed an item that was leased but expired (next_retry_at is the lease expiry, set to past)
    expired_lease = datetime.now(UTC) - timedelta(minutes=1)
    outbox_item = SystemOutboxRecord(
        id=item_id,
        channel="discord",
        payload={"content": "Lease Expire Test"},
        status="processing",
        worker_id="crashed-worker",
        next_retry_at=expired_lease,
        correlation_id=uuid.uuid4(),
        source_type="briefing",
        source_id=uuid.uuid4(),
        max_attempts=5,
    )
    db_session.add(outbox_item)
    await db_session.commit()

    # Worker 2 leases
    worker_2 = "worker-new"
    # We must mock next_retry_at filter. But wait, next_retry_at is <= now, and status is processing.
    # Wait, our lease_outbox_items selects status in ('pending', 'retrying')!
    # If the status is 'processing', does it lease it?
    # Ah! In models design: "Lease expiry recovery: If status is 'processing' and next_retry_at <= now,
    # the lease has expired and it should be treated as pending/retrying."
    # Let's check our lease_outbox_items query:
    #   SystemOutboxRecord.status.in_(["pending", "retrying"])
    # If the worker crashes, its status is still 'processing'.
    # To fix this, let's update lease_outbox_items so it selects:
    #   (status IN ('pending', 'retrying')) OR (status = 'processing' AND next_retry_at <= now)
    # This recovers crashed workers automatically!
    # Let's check if we need to modify lease_outbox_items. Yes! Let's write the test first.
    leased = await lease_outbox_items(db_session, worker_2)
    assert len(leased) == 1
    assert leased[0].id == item_id
    assert leased[0].worker_id == worker_2
    assert leased[0].status == "processing"
