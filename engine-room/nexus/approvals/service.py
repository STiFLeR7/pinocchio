"""Approval engine service managing governance gate states and sweeps."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from nexus.core.exceptions import ApprovalEngineError
from nexus.core.types import ApprovalStatus, TaskStatus
from nexus.memory.models import ApprovalRecord, TaskRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from nexus.gateway.gateway import EventGateway
    from nexus.memory.service import MemoryService


class ApprovalService:
    """Manages creation, evaluation, gates validation, and expiration of manual approvals."""

    def __init__(
        self,
        db_session: AsyncSession,
        memory_service: MemoryService,
        owner_ids: list[int] | list[str] | None = None,
        event_gateway: EventGateway | None = None,
    ) -> None:
        """Initialize the ApprovalService with database access and owner auth config."""
        self.session = db_session
        self.memory_service = memory_service
        self.owner_ids = [str(x) for x in (owner_ids or [])]
        self.event_gateway = event_gateway

    async def create_approval_request(
        self,
        task_id: uuid.UUID,
        expires_in_hours: int = 24,
    ) -> ApprovalRecord:
        """Create a new manual approval gate for a task, defaulting to a 24-hour expiration."""
        now = datetime.now(UTC)
        approval = ApprovalRecord(
            task_id=task_id,
            status=ApprovalStatus.PENDING.value,
            requested_at=now,
            expires_at=now + timedelta(hours=expires_in_hours),
        )
        self.session.add(approval)

        # Force parent task status to BLOCKED if not already
        stmt = select(TaskRecord).where(TaskRecord.id == task_id).with_for_update()
        res = await self.session.execute(stmt)
        task = res.scalar_one_or_none()
        if task:
            task.status = TaskStatus.BLOCKED.value

        await self.session.flush()

        # Emit ApprovalRequested event
        from nexus.core.events import NexusEvent
        from nexus.core.types import EventType

        event = NexusEvent(
            event_type=EventType.APPROVAL_REQUESTED,
            entity_type="approval",
            entity_id=approval.id,
            data={
                "task_id": str(task_id),
                "approval_id": str(approval.id),
                "requester": "system",
                "expires_at": (now + timedelta(hours=expires_in_hours)).isoformat(),
            },
            source="approval_engine",
        )
        await self.memory_service.log_event(event)

        if self.event_gateway is not None:
            await self.event_gateway.publish(event)

        return approval

    async def evaluate_approval(
        self,
        approval_id: uuid.UUID,
        decision: ApprovalStatus,
        decided_by: str,
        reason: str | None = None,
    ) -> ApprovalRecord:
        """Authorize or reject a pending approval request, enforcing owner credentials."""
        # Validate owner permission (A-001 defense-in-depth: fail closed).
        # An empty owner configuration must DENY all authorization, never allow it. This guards the
        # gate even if the startup validation in nexus.api is somehow bypassed.
        if not self.owner_ids:
            raise ApprovalEngineError(
                "Approval authorization is disabled: no owner IDs are configured. "
                "Refusing to authorize (fail-closed)."
            )
        if str(decided_by) not in self.owner_ids:
            raise ApprovalEngineError(f"User {decided_by} is not authorized to grant approvals.")

        stmt = select(ApprovalRecord).where(ApprovalRecord.id == approval_id).with_for_update()
        res = await self.session.execute(stmt)
        approval = res.scalar_one_or_none()

        if approval is None:
            raise ApprovalEngineError(f"Approval gate {approval_id} not found.")

        if approval.status != ApprovalStatus.PENDING.value:
            raise ApprovalEngineError(f"Approval gate {approval_id} is already decided.")

        now = datetime.now(UTC)
        if approval.expires_at:
            # Normalize both to naive UTC datetimes to prevent type errors in SQLite environments
            now_naive = now.replace(tzinfo=None)
            expires_naive = approval.expires_at
            if expires_naive.tzinfo is not None:
                expires_naive = expires_naive.astimezone(UTC).replace(tzinfo=None)

            if now_naive > expires_naive:
                approval.status = ApprovalStatus.EXPIRED.value
                await self.session.flush()
                raise ApprovalEngineError(f"Approval gate {approval_id} has expired.")

        if decision not in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
            raise ApprovalEngineError(f"Invalid approval decision value: {decision.value}")

        approval.status = decision.value
        approval.decided_at = now
        approval.decided_by = decided_by
        approval.decision_reason = reason

        # Calculate and log approval latency metric (AP-317)
        import structlog

        decided_naive = approval.decided_at.replace(tzinfo=None) if approval.decided_at.tzinfo is not None else approval.decided_at
        requested_naive = approval.requested_at.replace(tzinfo=None) if approval.requested_at.tzinfo is not None else approval.requested_at
        latency_ms = (decided_naive - requested_naive).total_seconds() * 1000.0

        from nexus.core.metrics import record_metric
        record_metric("approval_latency_ms", latency_ms)
        structlog.get_logger("nexus.approvals.service").info(
            "approval_decided",
            approval_id=str(approval.id),
            decision=decision.value,
            approval_latency_ms=round(latency_ms, 2),
        )

        # Transition parent task depending on decision
        task_stmt = select(TaskRecord).where(TaskRecord.id == approval.task_id).with_for_update()
        task_res = await self.session.execute(task_stmt)
        task = task_res.scalar_one_or_none()

        if task:
            if decision == ApprovalStatus.APPROVED:
                task.status = TaskStatus.ACTIVE.value
            else:
                task.status = TaskStatus.CANCELLED.value

        await self.session.flush()

        # Emit events
        from nexus.core.events import NexusEvent
        from nexus.core.types import EventType

        event_type = (
            EventType.APPROVAL_GRANTED
            if decision == ApprovalStatus.APPROVED
            else EventType.APPROVAL_REJECTED
        )
        event = NexusEvent(
            event_type=event_type,
            entity_type="approval",
            entity_id=approval.id,
            data={
                "approval_id": str(approval.id),
                "decided_by": decided_by,
                "reason": reason,
            },
            source="approval_engine",
        )
        await self.memory_service.log_event(event)

        if self.event_gateway is not None:
            await self.event_gateway.publish(event)

        return approval

    async def sweep_expired_approvals(self) -> list[uuid.UUID]:
        """Query and mark all pending approvals that have exceeded expiration times as expired."""
        now = datetime.now(UTC)
        stmt = (
            select(ApprovalRecord)
            .where(ApprovalRecord.status == ApprovalStatus.PENDING.value)
            .where(ApprovalRecord.expires_at < now)
            .with_for_update()
        )
        res = await self.session.execute(stmt)
        expired_records = res.scalars().all()

        swept_ids = []
        from nexus.core.events import NexusEvent
        from nexus.core.types import EventType

        for approval in expired_records:
            approval.status = ApprovalStatus.EXPIRED.value

            # Cancel parent task on approval expiration
            task_stmt = (
                select(TaskRecord).where(TaskRecord.id == approval.task_id).with_for_update()
            )
            task_res = await self.session.execute(task_stmt)
            task = task_res.scalar_one_or_none()
            if task:
                task.status = TaskStatus.CANCELLED.value

            swept_ids.append(approval.id)

            event = NexusEvent(
                event_type=EventType.APPROVAL_EXPIRED,
                entity_type="approval",
                entity_id=approval.id,
                data={
                    "approval_id": str(approval.id),
                    "expired_at": (
                        approval.expires_at.isoformat() if approval.expires_at else now.isoformat()
                    ),
                },
                source="approval_engine",
            )
            await self.memory_service.log_event(event)

            if self.event_gateway is not None:
                await self.event_gateway.publish(event)

        if swept_ids:
            await self.session.flush()

        return swept_ids

    async def check_approval_gate(self, task_id: uuid.UUID) -> bool:
        """Return True if the task has an active APPROVED record.

        Indicates execution is permitted.
        """
        stmt = (
            select(ApprovalRecord)
            .where(ApprovalRecord.task_id == task_id)
            .where(ApprovalRecord.status == ApprovalStatus.APPROVED.value)
        )
        res = await self.session.execute(stmt)
        record = res.scalar_one_or_none()
        return record is not None
