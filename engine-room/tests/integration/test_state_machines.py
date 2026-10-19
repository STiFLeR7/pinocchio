"""Integration tests for the complete Task, Approval, and Execution state machine flow."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from nexus.approvals.service import ApprovalService
from nexus.core.types import ApprovalStatus, ExitStatus, TaskStatus
from nexus.execution.service import ExecutionService
from nexus.gateway.gateway import EventGateway
from nexus.memory.service import MemoryService
from nexus.memory.task_service import TaskService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_end_to_end_state_machine_integration(db_session: AsyncSession) -> None:
    """Verify Task, Approval, and Execution state transitions concurrently under E2E flow."""
    # 1. Initialize services and routers
    event_gateway = EventGateway()
    memory_service = MemoryService(db_session)
    task_service = TaskService(db_session, memory_service, event_gateway)
    approval_service = ApprovalService(
        db_session, memory_service, owner_ids=[98765], event_gateway=event_gateway
    )
    execution_service = ExecutionService(
        db_session, memory_service, approval_service, event_gateway
    )

    # 2. Step 1: Create task
    task = await task_service.create_task(
        title="Deploy auth logic",
        description="Write handlers and test auth flow",
        priority=3,
    )
    await db_session.flush()
    assert task.status == TaskStatus.CREATED.value

    # 3. Step 2: Queue task
    await task_service.change_status(task.id, TaskStatus.QUEUED)
    assert task.status == TaskStatus.QUEUED.value

    # 4. Step 3: Trigger approval request
    approval = await approval_service.create_approval_request(task.id)
    await db_session.flush()
    assert task.status == TaskStatus.BLOCKED.value
    assert approval.status == ApprovalStatus.PENDING.value

    # 5. Step 4: Grant approval via owner
    await approval_service.evaluate_approval(
        approval_id=approval.id,
        decision=ApprovalStatus.APPROVED,
        decided_by="98765",
        reason="Security checklist passed",
    )
    await db_session.flush()
    assert task.status == TaskStatus.ACTIVE.value
    assert approval.status == ApprovalStatus.APPROVED.value

    # 6. Step 5: Start execution run
    execution = await execution_service.start_execution(task.id, runner="claude_code")
    await db_session.flush()
    assert execution.id is not None
    assert execution.approval_id == approval.id

    # 7. Step 6: Spawn execution steps
    step1 = await execution_service.start_step(execution.id, command="pytest tests/unit/auth")
    await db_session.flush()
    assert step1.id is not None
    assert step1.status == "running"

    await execution_service.complete_step(
        step_id=step1.id,
        exit_code=0,
        stdout="All tests passed successfully.",
    )
    await db_session.flush()
    assert step1.status == "completed"

    # 8. Step 7: Finalize execution
    finalized = await execution_service.finalize_execution(
        execution_id=execution.id,
        exit_status=ExitStatus.SUCCESS,
        result_payload={"summary": "Deployment complete", "deploy_url": "https://auth.nexus.test"},
    )
    await db_session.flush()

    # Assert parent task is COMPLETED
    assert task.status == TaskStatus.COMPLETED.value
    assert finalized.exit_status == "success"

    # Assert step logs are aggregated in parent ExecutionRecord
    logs = finalized.logs or ""
    assert "Command: pytest tests/unit/auth" in logs
    assert "STDOUT:\nAll tests passed successfully." in logs

    # Assert JSON payload is stored
    result_data = json.loads(finalized.result or "{}")
    assert result_data["deploy_url"] == "https://auth.nexus.test"
