"""E2E workflow test validating the complete user lifecycle in a test environment."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.approvals.service import ApprovalService
from nexus.core.types import ApprovalStatus, TaskStatus
from nexus.gateway.gateway import EventGateway
from nexus.intelligence.openrouter import OpenRouterClient
from nexus.memory.models import ExecutionRecord, ExecutionStepRecord
from nexus.memory.service import MemoryService
from nexus.memory.task_service import TaskService
from nexus.scheduling.orchestrator import WorkflowOrchestrator


class MockDiscordService:
    """Mock implementation of DiscordService to collect notifications in unit tests."""

    def __init__(self) -> None:
        self.posted_messages: list[dict[str, Any]] = []
        self.approval_requests: list[dict[str, Any]] = []
        # Setup mock bot attributes to avoid AttributeError
        self.bot = MagicMock()
        self.bot.settings.discord.owner_ids = [111222333]
        # Session factory is set by tests
        self.bot.session_factory = None

    async def post_message(
        self,
        channel_key: str,
        content: str | None = None,
        embed: Any = None,
        view: Any = None,
    ) -> Any:
        self.posted_messages.append(
            {
                "channel": channel_key,
                "content": content,
                "embed": embed,
                "view": view,
            }
        )
        return MagicMock()

    async def send_approval_request(
        self,
        task_id: uuid.UUID,
        approval_id: uuid.UUID,
        task_title: str,
        task_description: str | None,
        task_priority: int,
    ) -> Any:
        self.approval_requests.append(
            {
                "task_id": task_id,
                "approval_id": approval_id,
                "title": task_title,
                "description": task_description,
                "priority": task_priority,
            }
        )
        return MagicMock()


@pytest.mark.asyncio
async def test_complete_mvp_workflow_e2e(
    db_engine: Any,
    db_session: AsyncSession,
) -> None:
    """Validate E2E MVP task workflow: ingest, block, approve, run command, and summarize."""

    class SafeSessionWrapper:
        def __init__(self, session: AsyncSession) -> None:
            self._session = session

        def __getattr__(self, name: str) -> Any:
            return getattr(self._session, name)

        async def commit(self) -> None:
            await self._session.flush()

        async def rollback(self) -> None:
            await self._session.rollback()

        async def close(self) -> None:
            pass

    def session_factory() -> SafeSessionWrapper:
        return SafeSessionWrapper(db_session)

    event_gateway = EventGateway()
    memory_service = MemoryService(db_session)
    task_service = TaskService(db_session, memory_service, event_gateway)
    approval_service = ApprovalService(
        db_session, memory_service, owner_ids=[111222333], event_gateway=event_gateway
    )

    discord_service = MockDiscordService()
    discord_service.bot.session_factory = session_factory

    # Mock OpenRouter client
    openrouter_client = MagicMock(spec=OpenRouterClient)
    openrouter_client.complete = AsyncMock(
        return_value=(
            "**Execution Success Report**\n"
            "- Spawned echo command successfully.\n"
            "- Completed in 1 step."
        )
    )

    orchestrator = WorkflowOrchestrator(
        session_factory=session_factory,
        event_gateway=event_gateway,
        discord_service=discord_service,  # type: ignore[arg-type]
        openrouter_client=openrouter_client,
    )
    orchestrator.on_approval_granted = AsyncMock()  # type: ignore[method-assign]
    orchestrator.register_listeners()

    # 2. Ingest task through service (simulating Slash command /task_create)
    task = await task_service.create_task(
        title="Compile binary",
        description="cmd:echo 'Step 1: building code...'",
        priority=3,
    )
    await db_session.flush()
    assert task.status == TaskStatus.CREATED.value

    # 3. Transition status to QUEUED
    await task_service.change_status(task.id, TaskStatus.QUEUED)
    await db_session.flush()

    # Define helper to manually simulate the background outbox sweeper
    async def sweep_outbox() -> None:
        from nexus.gateway.outbox import dispatch_outbox_event
        from nexus.memory.models import SystemEventRecord

        stmt = select(SystemEventRecord).where(SystemEventRecord.status == "pending")
        res = await db_session.execute(stmt)
        records = res.scalars().all()
        for record in records:
            await dispatch_outbox_event(record, discord_service)  # type: ignore[arg-type]
            record.status = "sent"
        await db_session.flush()

    # Run the outbox sweep to dispatch TASK_CREATED, TASK_UPDATED, and APPROVAL_REQUESTED
    await sweep_outbox()

    # Verify task state is now BLOCKED because orchestrator created approval gate
    assert task.status == TaskStatus.BLOCKED.value
    assert len(discord_service.approval_requests) == 1

    approval_request = discord_service.approval_requests[0]
    approval_id = approval_request["approval_id"]

    # 4. Operator clicks Approve in Discord (Simulating button click)
    await approval_service.evaluate_approval(
        approval_id=approval_id,
        decision=ApprovalStatus.APPROVED,
        decided_by="111222333",
        reason="Manual owner verification",
    )
    await db_session.flush()

    # Task transitions to ACTIVE
    assert task.status == TaskStatus.ACTIVE.value

    # 5. Let the concurrent execution tasks process
    # To keep test deterministic, we directly trigger the orchestrator flow
    await orchestrator.run_execution_flow(task.id)

    # Refresh task from database
    await db_session.refresh(task)
    assert task.status == TaskStatus.COMPLETED.value

    # 6. Verify Execution log records
    exec_stmt = select(ExecutionRecord).where(ExecutionRecord.task_id == task.id)
    exec_res = await db_session.execute(exec_stmt)
    execution = exec_res.scalar_one()

    assert execution.exit_status == "success"
    assert "Step 1: building code..." in (execution.logs or "")

    # Verify steps
    step_stmt = select(ExecutionStepRecord).where(ExecutionStepRecord.execution_id == execution.id)
    step_res = await db_session.execute(step_stmt)
    steps = step_res.scalars().all()
    assert len(steps) == 1
    assert steps[0].status == "completed"
    assert steps[0].exit_code == 0

    # 7. Check if summary was generated and routed
    # Handled automatically via event gateway subscriptions

    assert openrouter_client.complete.called
    assert len(discord_service.posted_messages) > 0

    # Locate summary embed post
    summary_messages = [m for m in discord_service.posted_messages if m["channel"] == "summaries"]
    assert len(summary_messages) == 1
    embed = summary_messages[0]["embed"]
    assert embed.title == "Task Run Report"
    assert embed.description == (
        "**Execution Success Report**\n- Spawned echo command successfully.\n- Completed in 1 step."
    )
