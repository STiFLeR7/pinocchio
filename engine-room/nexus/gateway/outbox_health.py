"""Outbox health observation service (AP-103 J5).

Read-only observability over the transactional outboxes. This service performs SELECT-only
aggregate queries and returns counts; it never mutates, retries, repairs, or remediates anything
(per AP-103A J5 constraints).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from nexus.memory.models import SystemEventRecord, SystemOutboxRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class OutboxHealthService:
    """Read-only snapshot of outbox backlog and dead-letter counts."""

    def __init__(self, db_session: AsyncSession) -> None:
        """Initialize with an active database session."""
        self.session = db_session

    async def snapshot(self) -> dict[str, int]:
        """Return read-only counts for the communication and system-event outboxes.

        Keys: ``pending``, ``retrying``, ``processing``, ``sent``, ``dead_letter`` (from
        ``system_outbox``) and ``events_pending`` (from ``system_events``). No rows are modified.
        """
        snapshot: dict[str, int] = {
            "pending": 0,
            "retrying": 0,
            "processing": 0,
            "sent": 0,
            "dead_letter": 0,
        }

        stmt = select(SystemOutboxRecord.status, func.count()).group_by(SystemOutboxRecord.status)
        for status, count in (await self.session.execute(stmt)).all():
            snapshot[str(status)] = int(count)

        events_pending = await self.session.execute(
            select(func.count()).where(SystemEventRecord.status == "pending")
        )
        snapshot["events_pending"] = int(events_pending.scalar_one())

        return snapshot
