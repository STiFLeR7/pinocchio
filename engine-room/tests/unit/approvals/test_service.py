"""Unit tests for the ApprovalService governance workflows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from nexus.approvals.service import ApprovalService
from nexus.core.exceptions import ApprovalEngineError
from nexus.core.types import ApprovalStatus, TaskStatus
from nexus.memory.service import MemoryService
from nexus.memory.task_service import TaskService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_create_approval_request(db_session: AsyncSession) -> None:
    """Verify that creating an approval blocks the parent task and sets 24-hour expiration."""
    memory_service = MemoryService(db_session)
    task_service = TaskService(db_session, memory_service)
    approval_service = ApprovalService(db_session, memory_service, owner_ids=[12345])

    task = await task_service.create_task("Protected Task")
    await db_session.flush()

    approval = await approval_service.create_approval_request(task.id)
    await db_session.flush()

    # Verify task was transitioned to BLOCKED
    assert task.status == TaskStatus.BLOCKED.value

    # Verify approval properties
    assert approval.id is not None
    assert approval.status == ApprovalStatus.PENDING.value
    assert approval.expires_at is not None

    # Expiration delta check (should be approx 24 hours)
    delta = approval.expires_at - approval.requested_at
    assert abs(delta.total_seconds() - 86400) < 5


@pytest.mark.asyncio
async def test_evaluate_approval_authorized(db_session: AsyncSession) -> None:
    """Verify owner approval grants permission and shifts task back to ACTIVE."""
    memory_service = MemoryService(db_session)
    task_service = TaskService(db_session, memory_service)
    approval_service = ApprovalService(db_session, memory_service, owner_ids=[99999])

    task = await task_service.create_task("Lock Box Task")
    await db_session.flush()

    approval = await approval_service.create_approval_request(task.id)
    await db_session.flush()

    # Evaluate approval as authorized owner
    evaluated = await approval_service.evaluate_approval(
        approval_id=approval.id,
        decision=ApprovalStatus.APPROVED,
        decided_by="99999",
        reason="Looks safe",
    )
    await db_session.flush()

    assert evaluated.status == ApprovalStatus.APPROVED.value
    assert evaluated.decided_by == "99999"
    assert evaluated.decision_reason == "Looks safe"

    # Task must transition to ACTIVE
    assert task.status == TaskStatus.ACTIVE.value

    # Gate check
    gated = await approval_service.check_approval_gate(task.id)
    assert gated is True


@pytest.mark.asyncio
async def test_evaluate_approval_unauthorized(db_session: AsyncSession) -> None:
    """Verify unauthorized users are blocked from granting approvals."""
    memory_service = MemoryService(db_session)
    task_service = TaskService(db_session, memory_service)
    approval_service = ApprovalService(db_session, memory_service, owner_ids=[99999])

    task = await task_service.create_task("Lock Box Task 2")
    await db_session.flush()

    approval = await approval_service.create_approval_request(task.id)
    await db_session.flush()

    # Evaluate as rogue user
    with pytest.raises(ApprovalEngineError) as exc_info:
        await approval_service.evaluate_approval(
            approval_id=approval.id,
            decision=ApprovalStatus.APPROVED,
            decided_by="11111",
        )
    assert "is not authorized to grant approvals" in str(exc_info.value)


@pytest.mark.asyncio
async def test_sweep_expired_approvals(db_session: AsyncSession) -> None:
    """Verify sweeps catch and transition expired approvals to EXPIRED and cancel task."""
    memory_service = MemoryService(db_session)
    task_service = TaskService(db_session, memory_service)
    approval_service = ApprovalService(db_session, memory_service)

    task = await task_service.create_task("Expired Task Workflow")
    await db_session.flush()

    approval = await approval_service.create_approval_request(task.id)
    await db_session.flush()

    # Manually backdate expires_at to mock expiration
    approval.expires_at = datetime.now(UTC) - timedelta(hours=1)
    await db_session.flush()

    swept = await approval_service.sweep_expired_approvals()

    assert len(swept) == 1
    assert swept[0] == approval.id
    assert approval.status == ApprovalStatus.EXPIRED.value

    # Parent task must be cancelled
    assert task.status == TaskStatus.CANCELLED.value
