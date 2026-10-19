"""Transactional outbox publisher loop.

Asynchronously sweeps pending system events from the database outbox and routes
them to Discord channels.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from nexus.core.types import EventType
from nexus.database import get_session
from nexus.memory.models import SystemEventRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from nexus.communication.discord.service import DiscordService

logger = structlog.get_logger("nexus.gateway.outbox")


async def dispatch_outbox_event(
    record: SystemEventRecord,
    discord_service: DiscordService,
) -> bool:
    """Translate system outbox event into Discord notifications and embeds."""
    payload = record.payload
    event_type_str = record.event_type

    try:
        event_type = EventType(event_type_str)
    except ValueError:
        logger.error("unknown_outbox_event_type", event_type=event_type_str)
        return True  # Mark sent so we discard unsupported events

    entity_id = payload.get("entity_id")
    data = payload.get("data", {})

    try:
        # Route depending on event type
        if event_type == EventType.TASK_CREATED:
            title = data.get("title", "No Title")
            priority = data.get("priority", 2)
            await discord_service.post_message(
                "tasks",
                content=(
                    f"🆕 **Task Created**: **{title}** (Priority: {priority})\nID: `{entity_id}`"
                ),
            )

        elif event_type == EventType.TASK_UPDATED:
            status = data.get("status")
            if status:
                await discord_service.post_message(
                    "tasks",
                    content=(
                        f"🔄 **Task Status Updated**: Task `{entity_id}` transitioned to `{status}`"
                    ),
                )

        elif event_type == EventType.TASK_COMPLETED:
            task_id = data.get("task_id") or entity_id
            await discord_service.post_message(
                "tasks",
                content=f"✅ **Task Completed**: Task `{task_id}` has been completed successfully.",
            )

        elif event_type == EventType.TASK_CANCELLED:
            task_id = data.get("task_id") or entity_id
            await discord_service.post_message(
                "tasks",
                content=f"❌ **Task Cancelled**: Task `{task_id}` was cancelled.",
            )

        elif event_type == EventType.APPROVAL_REQUESTED:
            # Query task info from DB inside a separate session block
            task_id_str = data.get("task_id")
            approval_id_str = data.get("approval_id")
            if not task_id_str or not approval_id_str:
                logger.error("missing_approval_data_in_event", data=data)
                return True

            task_id = uuid.UUID(task_id_str)
            approval_id = uuid.UUID(approval_id_str)

            # Use bot's session factory
            async with get_session(discord_service.bot.session_factory) as session:
                from nexus.memory.models import TaskRecord

                task_stmt = select(TaskRecord).where(TaskRecord.id == task_id)
                res = await session.execute(task_stmt)
                task = res.scalar_one_or_none()

                if task:
                    await discord_service.send_approval_request(
                        task_id=task_id,
                        approval_id=approval_id,
                        task_title=task.title,
                        task_description=task.description,
                        task_priority=task.priority,
                    )
                else:
                    logger.error("task_not_found_for_approval_request", task_id=task_id)

        elif event_type == EventType.APPROVAL_GRANTED:
            decided_by = data.get("decided_by", "Owner")
            app_id = data.get("approval_id")
            await discord_service.post_message(
                "alerts",
                content=(
                    f"🟢 **Approval Granted**: Approval gate `{app_id}` "
                    f"authorized by <@{decided_by}>."
                ),
            )

        elif event_type == EventType.APPROVAL_REJECTED:
            decided_by = data.get("decided_by", "Owner")
            reason = data.get("reason", "No reason provided")
            app_id = data.get("approval_id")
            await discord_service.post_message(
                "alerts",
                content=(
                    f"🔴 **Approval Rejected**: Approval gate `{app_id}` "
                    f"rejected by <@{decided_by}>. Reason: *{reason}*"
                ),
            )

        elif event_type == EventType.EXECUTION_STARTED:
            runner = data.get("runner", "unknown")
            await discord_service.post_message(
                "execution_log",
                content=(
                    f"🚀 **Execution Started**: Run `{entity_id}` "
                    f"initiated using runner `{runner}`."
                ),
            )

        elif event_type == EventType.EXECUTION_COMPLETED:
            await discord_service.post_message(
                "execution_log",
                content=f"🏁 **Execution Completed**: Run `{entity_id}` finished successfully.",
            )

        elif event_type == EventType.EXECUTION_FAILED:
            await discord_service.post_message(
                "alerts",
                content=(
                    f"⚠️ **Execution Failed**: Run `{entity_id}` failed. "
                    f"Check execution log channels."
                ),
            )

        return True

    except Exception as e:
        logger.error(
            "dispatch_outbox_event_exception",
            record_id=str(record.id),
            error=str(e),
            exc_info=True,
        )
        return False


async def publish_outbox_loop(
    session_factory: async_sessionmaker[Any],
    discord_service: DiscordService,
    poll_interval: float = 2.0,
) -> None:
    """Continuously sweep system_events database outbox table for pending notifications."""
    logger.info("outbox_publisher_loop_started", poll_interval=poll_interval)
    while True:
        try:
            async with get_session(session_factory) as session:
                # Query oldest 20 pending events
                stmt = (
                    select(SystemEventRecord)
                    .where(SystemEventRecord.status == "pending")
                    .order_by(SystemEventRecord.created_at.asc())
                    .limit(20)
                )
                res = await session.execute(stmt)
                records = res.scalars().all()

                for record in records:
                    success = await dispatch_outbox_event(record, discord_service)
                    if success:
                        record.status = "sent"

                if records:
                    import time
                    flush_start = time.perf_counter()
                    await session.flush()
                    flush_duration = (time.perf_counter() - flush_start) * 1000.0
                    from nexus.core.metrics import record_metric
                    record_metric("event_flush_duration_ms", flush_duration)
                    logger.info(
                        "outbox_events_flushed",
                        count=len(records),
                        event_flush_duration_ms=round(flush_duration, 2),
                    )

        except Exception as e:
            logger.error("outbox_publisher_loop_failed", error=str(e))

        await asyncio.sleep(poll_interval)
