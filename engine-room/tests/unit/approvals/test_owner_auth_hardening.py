"""A-001 regression tests: fail-closed owner authentication (Nexus v1.0.1 Alignment).

These tests assert the defense-in-depth behavior of ``ApprovalService``: when no owner IDs are
configured, the service must DENY all authorization (fail closed) rather than allow it (the
v1.0.0 fail-open defect). Valid owner configuration must behave exactly as before.
"""

from __future__ import annotations

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
async def test_evaluate_approval_denied_when_owner_ids_empty(db_session: AsyncSession) -> None:
    """Empty owner_ids must fail closed: evaluate_approval raises and the gate stays closed."""
    memory_service = MemoryService(db_session)
    task_service = TaskService(db_session, memory_service)
    approval_service = ApprovalService(db_session, memory_service, owner_ids=[])

    task = await task_service.create_task("Fail-closed task")
    await db_session.flush()
    approval = await approval_service.create_approval_request(task.id)
    await db_session.flush()

    with pytest.raises(ApprovalEngineError) as exc_info:
        await approval_service.evaluate_approval(
            approval_id=approval.id,
            decision=ApprovalStatus.APPROVED,
            decided_by="111222333",
        )

    assert "owner" in str(exc_info.value).lower()
    # Task must remain BLOCKED — it must NOT be promoted to ACTIVE.
    assert task.status == TaskStatus.BLOCKED.value
    # The execution gate must remain closed.
    assert await approval_service.check_approval_gate(task.id) is False


@pytest.mark.asyncio
async def test_evaluate_approval_denied_when_owner_ids_none(db_session: AsyncSession) -> None:
    """owner_ids defaulting to None normalizes to [] and must also fail closed."""
    memory_service = MemoryService(db_session)
    task_service = TaskService(db_session, memory_service)
    approval_service = ApprovalService(db_session, memory_service)  # owner_ids omitted -> None -> []

    task = await task_service.create_task("Fail-closed task (None)")
    await db_session.flush()
    approval = await approval_service.create_approval_request(task.id)
    await db_session.flush()

    with pytest.raises(ApprovalEngineError):
        await approval_service.evaluate_approval(
            approval_id=approval.id,
            decision=ApprovalStatus.APPROVED,
            decided_by="anyone",
        )
    assert task.status == TaskStatus.BLOCKED.value


@pytest.mark.asyncio
async def test_valid_owner_behaves_unchanged(db_session: AsyncSession) -> None:
    """Regression: a configured owner can still approve and the task becomes ACTIVE."""
    memory_service = MemoryService(db_session)
    task_service = TaskService(db_session, memory_service)
    approval_service = ApprovalService(db_session, memory_service, owner_ids=[99999])

    task = await task_service.create_task("Valid owner task")
    await db_session.flush()
    approval = await approval_service.create_approval_request(task.id)
    await db_session.flush()

    evaluated = await approval_service.evaluate_approval(
        approval_id=approval.id,
        decision=ApprovalStatus.APPROVED,
        decided_by="99999",
        reason="ok",
    )
    assert evaluated.status == ApprovalStatus.APPROVED.value
    assert task.status == TaskStatus.ACTIVE.value
    assert await approval_service.check_approval_gate(task.id) is True


@pytest.mark.asyncio
async def test_non_owner_still_rejected_with_configured_owners(db_session: AsyncSession) -> None:
    """Regression: with owners configured, a non-owner is still rejected (unchanged behavior)."""
    memory_service = MemoryService(db_session)
    task_service = TaskService(db_session, memory_service)
    approval_service = ApprovalService(db_session, memory_service, owner_ids=[99999])

    task = await task_service.create_task("Non-owner task")
    await db_session.flush()
    approval = await approval_service.create_approval_request(task.id)
    await db_session.flush()

    with pytest.raises(ApprovalEngineError, match="is not authorized to grant approvals"):
        await approval_service.evaluate_approval(
            approval_id=approval.id,
            decision=ApprovalStatus.APPROVED,
            decided_by="11111",
        )
