"""Transactional communication outbox loop and adapters (AP-501).

Manages leasing, polling, retrying, and auditing for asynchronous Discord and SMTP dispatches.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nexus.core.events import NexusEvent
from nexus.core.types import EventType
from nexus.database import get_session
from nexus.memory.models import AuditLogRecord, BriefingRecord, SystemOutboxRecord

logger = structlog.get_logger("nexus.gateway.communication_outbox")


async def _deliver_discord_chunks(
    discord_service: Any, content: str, channel_key: str = "summaries"
) -> None:
    """Deliver content to a mapped Discord channel with chunking controls.

    ``channel_key`` defaults to ``"summaries"`` for backward compatibility; the priority feed and
    other roles pass their own key so the same transactional outbox serves every channel.
    """
    max_chunk = 1900
    text = content
    chunks = []

    while len(text) > max_chunk:
        split_idx = text.rfind("\n\n", 0, max_chunk)
        if split_idx == -1:
            split_idx = text.rfind("\n", 0, max_chunk)
        if split_idx == -1:
            split_idx = max_chunk
        chunks.append(text[:split_idx].strip())
        text = text[split_idx:].strip()

    if text:
        chunks.append(text)

    for chunk in chunks:
        await discord_service.post_message(channel_key, content=chunk)


async def _update_source_briefing_status(
    session: AsyncSession, source_type: str, source_id: uuid.UUID | None
) -> None:
    """Update status of the originating briefing record based on associated outbox channels status."""
    if source_type != "briefing" or not source_id:
        return

    # Check if there are other outbox items for the same source_id
    stmt = select(SystemOutboxRecord).where(SystemOutboxRecord.source_id == source_id)
    res = await session.execute(stmt)
    related_items = res.scalars().all()

    # Find the BriefingRecord
    brief_stmt = select(BriefingRecord).where(BriefingRecord.id == source_id)
    brief_res = await session.execute(brief_stmt)
    briefing = brief_res.scalar_one_or_none()
    if not briefing:
        return

    delivered_channels = [item.channel for item in related_items if item.status == "sent"]
    briefing.delivery_channels = list(set(delivered_channels))

    all_completed = all(item.status in ["sent", "dead_letter"] for item in related_items)
    if all_completed:
        any_failed = any(item.status == "dead_letter" for item in related_items)
        if any_failed:
            briefing.status = "partial" if delivered_channels else "failed"
        else:
            briefing.status = "sent"


async def lease_outbox_items(
    session: AsyncSession, worker_id: str, limit: int = 10
) -> list[SystemOutboxRecord]:
    """Lease pending or retrying outbox items to prevent duplicate processing."""
    now = datetime.now(UTC)
    stmt = (
        select(SystemOutboxRecord)
        .where(
            (
                SystemOutboxRecord.status.in_(["pending", "retrying"])
                & ((SystemOutboxRecord.next_retry_at.is_(None)) | (SystemOutboxRecord.next_retry_at <= now))
            )
            | (
                (SystemOutboxRecord.status == "processing")
                & (SystemOutboxRecord.next_retry_at <= now)
            )
        )
        .order_by(SystemOutboxRecord.created_at.asc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    records = res.scalars().all()
    if not records:
        return []

    record_ids = [r.id for r in records]
    lease_expiry = now + timedelta(minutes=5)

    update_stmt = (
        update(SystemOutboxRecord)
        .where(SystemOutboxRecord.id.in_(record_ids))
        .values(
            status="processing",
            worker_id=worker_id,
            next_retry_at=lease_expiry,
            updated_at=now,
        )
    )
    await session.execute(update_stmt)
    await session.commit()

    return list(records)


async def process_outbox_item(
    session_factory: async_sessionmaker[Any],
    item_id: uuid.UUID,
    worker_id: str,
    discord_service: Any,
    email_service: Any,
) -> None:
    """Process a single leased outbox item, handling delivery, retries, and dead-letter queueing."""
    now = datetime.now(UTC)
    async with get_session(session_factory) as session:
        stmt = select(SystemOutboxRecord).where(
            SystemOutboxRecord.id == item_id,
            SystemOutboxRecord.status == "processing",
            SystemOutboxRecord.worker_id == worker_id,
        )
        res = await session.execute(stmt)
        record = res.scalar_one_or_none()
        if not record:
            return

        try:
            # Deliver to target channel
            if record.channel == "discord":
                if not discord_service:
                    raise RuntimeError("Discord service not configured")
                content = record.payload.get("content", "")
                channel_key = record.payload.get("channel_key", "summaries")
                await _deliver_discord_chunks(discord_service, content, channel_key)
            elif record.channel == "email":
                if not email_service:
                    raise RuntimeError("Email service not configured")
                subject = record.payload.get("subject", "Nexus Notification")
                markdown_body = record.payload.get("markdown_body", "")
                html_body = record.payload.get("html_body", "")
                await email_service.send_briefing_email(subject, markdown_body, html_body)
            else:
                raise ValueError(f"Unsupported outbox channel: {record.channel}")

            # On success:
            record.status = "sent"
            record.delivered_at = datetime.now(UTC)
            record.next_retry_at = None
            record.last_error = None
            record.worker_id = None
            await session.flush()

            # Record success event in AuditLogRecord
            success_event = NexusEvent(
                event_type=EventType.NOTIFICATION_SENT,
                entity_type="outbox",
                entity_id=record.id,
                data={
                    "outbox_id": str(record.id),
                    "channel": record.channel,
                    "correlation_id": str(record.correlation_id) if record.correlation_id else None,
                    "source_type": record.source_type,
                    "source_id": str(record.source_id) if record.source_id else None,
                },
                source="communication_outbox",
            )
            audit_rec = AuditLogRecord(
                id=uuid.uuid4(),
                event_type=EventType.NOTIFICATION_SENT.value,
                entity_type="outbox",
                entity_id=record.id,
                data=success_event.data,
                correlation_id=record.correlation_id or uuid.uuid4(),
                component="communication_outbox",
                actor="system",
            )
            session.add(audit_rec)

            await _update_source_briefing_status(session, record.source_type, record.source_id)
            await session.commit()

        except Exception as e:
            logger.error("outbox_item_delivery_failed", id=str(record.id), error=str(e))
            record.attempt_count += 1
            record.last_error = str(e)

            if record.attempt_count >= record.max_attempts:
                record.status = "dead_letter"
                record.worker_id = None
                record.next_retry_at = None
                await session.flush()

                # Dead letter event must generate audit record (Requirement 3)
                fail_event = NexusEvent(
                    event_type=EventType.NOTIFICATION_FAILED,
                    entity_type="outbox",
                    entity_id=record.id,
                    data={
                        "outbox_id": str(record.id),
                        "channel": record.channel,
                        "correlation_id": str(record.correlation_id) if record.correlation_id else None,
                        "source_type": record.source_type,
                        "source_id": str(record.source_id) if record.source_id else None,
                        "error": str(e),
                    },
                    source="communication_outbox",
                )
                audit_rec = AuditLogRecord(
                    id=uuid.uuid4(),
                    event_type=EventType.NOTIFICATION_FAILED.value,
                    entity_type="outbox",
                    entity_id=record.id,
                    data=fail_event.data,
                    correlation_id=record.correlation_id or uuid.uuid4(),
                    component="communication_outbox",
                    actor="system",
                )
                session.add(audit_rec)

                await _update_source_briefing_status(session, record.source_type, record.source_id)
            else:
                backoff_sec = 10 * (2**record.attempt_count) + random.uniform(0, 5)
                record.status = "retrying"
                record.worker_id = None
                record.next_retry_at = now + timedelta(seconds=backoff_sec)
                await session.flush()

            await session.commit()


async def flush_outbox_synchronously(
    session: AsyncSession,
    correlation_id: uuid.UUID,
    discord_service: Any,
    email_service: Any,
) -> None:
    """Synchronously flush outbox items for a specific correlation ID (used for testing)."""
    stmt = select(SystemOutboxRecord).where(
        SystemOutboxRecord.correlation_id == correlation_id,
        SystemOutboxRecord.status == "pending",
    )
    res = await session.execute(stmt)
    records = res.scalars().all()

    for record in records:
        try:
            if record.channel == "discord":
                if discord_service:
                    await _deliver_discord_chunks(
                        discord_service,
                        record.payload.get("content", ""),
                        record.payload.get("channel_key", "summaries"),
                    )
                record.status = "sent"
            elif record.channel == "email":
                if email_service:
                    subject = record.payload.get("subject", "")
                    markdown_body = record.payload.get("markdown_body", "")
                    html_body = record.payload.get("html_body", "")
                    await email_service.send_briefing_email(subject, markdown_body, html_body)
                record.status = "sent"
            record.delivered_at = datetime.now(UTC)
        except Exception as e:
            record.status = "dead_letter"
            record.last_error = str(e)

            audit_rec = AuditLogRecord(
                id=uuid.uuid4(),
                event_type=EventType.NOTIFICATION_FAILED.value,
                entity_type="outbox",
                entity_id=record.id,
                data={
                    "outbox_id": str(record.id),
                    "channel": record.channel,
                    "correlation_id": str(record.correlation_id),
                    "error": str(e),
                },
                correlation_id=record.correlation_id or uuid.uuid4(),
                component="communication_outbox",
                actor="system",
            )
            session.add(audit_rec)

    if records:
        source_id = records[0].source_id
        if source_id:
            delivered_channels = [r.channel for r in records if r.status == "sent"]
            brief_stmt = select(BriefingRecord).where(BriefingRecord.id == source_id)
            brief_res = await session.execute(brief_stmt)
            briefing = brief_res.scalar_one_or_none()
            if briefing:
                current_channels = briefing.delivery_channels or []
                briefing.delivery_channels = list(
                    set(current_channels + delivered_channels)
                )
                any_failed = any(r.status == "dead_letter" for r in records)
                if any_failed:
                    briefing.status = "partial"
                else:
                    briefing.status = "sent"
                await session.flush()



async def run_communication_outbox_loop(
    session_factory: async_sessionmaker[Any],
    discord_service: Any,
    email_service: Any,
    worker_id: str | None = None,
    poll_interval: float = 2.0,
) -> None:
    """Continuously poll, lease, and process pending system_outbox records."""
    w_id = worker_id or f"outbox-worker-{uuid.uuid4()}"
    logger.info("communication_outbox_loop_started", worker_id=w_id, poll_interval=poll_interval)

    while True:
        try:
            async with get_session(session_factory) as session:
                records = await lease_outbox_items(session, w_id, limit=10)

            if records:
                # Process each item in individual transactions
                for record in records:
                    await process_outbox_item(
                        session_factory, record.id, w_id, discord_service, email_service
                    )
        except Exception as e:
            logger.error("communication_outbox_loop_exception", error=str(e))

        await asyncio.sleep(poll_interval)
