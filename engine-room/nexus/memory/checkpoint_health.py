"""Checkpoint / execution-heartbeat health observation service (AP-103 J6).

Read-only observability over workflow checkpoints and in-flight executions. SELECT-only; never
rewrites checkpoints, cleans up, or mutates any state (per AP-103A J6 constraints).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from nexus.memory.models import (
    AgentStepRecord,
    ExecutionRecord,
    WorkflowCheckpointRecord,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CheckpointHealthService:
    """Read-only snapshot of checkpoint volume and stalled in-flight executions."""

    def __init__(self, db_session: AsyncSession) -> None:
        """Initialize with an active database session."""
        self.session = db_session

    async def snapshot(self, stale_minutes: int = 60) -> dict[str, int]:
        """Return read-only health counts.

        Keys: ``total_checkpoints``, ``stale_executions`` (running executions whose
        ``last_heartbeat`` is older than ``stale_minutes``), and ``stale_agent_steps``.
        No rows are modified.
        """
        cutoff = datetime.now(UTC) - timedelta(minutes=stale_minutes)

        total_checkpoints = (
            await self.session.execute(select(func.count()).select_from(WorkflowCheckpointRecord))
        ).scalar_one()

        stale_executions = (
            await self.session.execute(
                select(func.count())
                .select_from(ExecutionRecord)
                .where(ExecutionRecord.completed_at.is_(None))
                .where(ExecutionRecord.last_heartbeat.is_not(None))
                .where(ExecutionRecord.last_heartbeat < cutoff)
            )
        ).scalar_one()

        stale_agent_steps = (
            await self.session.execute(
                select(func.count())
                .select_from(AgentStepRecord)
                .where(AgentStepRecord.last_heartbeat.is_not(None))
                .where(AgentStepRecord.last_heartbeat < cutoff)
            )
        ).scalar_one()

        return {
            "total_checkpoints": int(total_checkpoints),
            "stale_executions": int(stale_executions),
            "stale_agent_steps": int(stale_agent_steps),
        }
