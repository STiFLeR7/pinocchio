"""Verification script for Hermes agent runtime validation.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from nexus.approvals.service import ApprovalService
from nexus.core.types import ApprovalStatus, TaskStatus
from nexus.database import Base
from nexus.gateway.gateway import EventGateway
from nexus.intelligence.openrouter import OpenRouterClient
from nexus.memory.models import (
    AgentStepRecord,
    ApprovalRecord,
    ExecutionArtifactRecord,
    ExecutionRecord,
    RepositoryRegistryRecord,
    TaskRecord,
)
from nexus.memory.service import MemoryService
from nexus.memory.task_service import TaskService
from nexus.scheduling.orchestrator import WorkflowOrchestrator


class SafeSessionWrapper:
    def __init__(self, session: Any) -> None:
        self._session = session

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)

    async def commit(self) -> None:
        await self._session.flush()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def close(self) -> None:
        pass


class MockDiscordService:
    def __init__(self) -> None:
        self.posted_messages: list[dict[str, Any]] = []
        self.approval_requests: list[dict[str, Any]] = []
        self.bot = MagicMock()
        self.bot.settings.discord.owner_ids = [111222333]
        self.bot.session_factory = None

    async def post_message(
        self,
        channel_key: str,
        content: str | None = None,
        embed: Any = None,
        view: Any = None,
    ) -> Any:
        self.posted_messages.append({
            "channel": channel_key,
            "content": content,
            "embed": embed,
            "view": view,
        })
        return MagicMock()

    async def send_approval_request(
        self,
        task_id: uuid.UUID,
        approval_id: uuid.UUID,
        task_title: str,
        task_description: str | None,
        task_priority: int,
    ) -> Any:
        self.approval_requests.append({
            "task_id": task_id,
            "approval_id": approval_id,
            "title": task_title,
            "description": task_description,
            "priority": task_priority,
        })
        return MagicMock()


async def init_db(engine_url: str) -> Any:
    engine = create_async_engine(engine_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    return engine


async def print_task_details(session: Any, task_id: uuid.UUID) -> None:
    stmt = select(TaskRecord).where(TaskRecord.id == task_id)
    res = await session.execute(stmt)
    task = res.scalar_one_or_none()
    if task:
        print(f"  [DB TaskRecord] ID: {task.id} | Title: '{task.title}' | Status: '{task.status}'")
    else:
        print(f"  [DB TaskRecord] NOT FOUND for ID {task_id}")


async def print_agent_steps(session: Any, exec_id: uuid.UUID) -> None:
    stmt = (
        select(AgentStepRecord)
        .where(AgentStepRecord.execution_id == exec_id)
        .order_by(AgentStepRecord.step_index.asc())
    )
    res = await session.execute(stmt)
    steps = res.scalars().all()
    print(f"  [DB AgentStepRecords] Captured {len(steps)} steps:")
    for st in steps:
        print(f"    - Step {st.step_index} ({st.status}): Thought: '{st.thought}'")
        print(
            f"      Tool: {st.tool_name}({st.tool_arguments}) -> "
            f"Outcome: '{str(st.tool_result)[:100]}...' "
        )


async def print_artifacts(session: Any, exec_id: uuid.UUID) -> None:
    stmt = select(ExecutionArtifactRecord).where(ExecutionArtifactRecord.execution_id == exec_id)
    res = await session.execute(stmt)
    artifacts = res.scalars().all()
    print(f"  [DB ExecutionArtifactRecords] Captured {len(artifacts)} artifacts:")
    for art in artifacts:
        print(
            f"    - Type: '{art.artifact_type}' | Name: '{art.name}' | "
            f"Size: {len(art.content or '')} bytes"
        )


async def run_hermes_validation(engine: Any) -> None:
    print("\n=== RUNNING HERMES AGENT WORKFLOW ACCEPTANCE ===")
    root_session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with root_session_factory() as root_session:
        shared_session = SafeSessionWrapper(root_session)

        def session_factory() -> Any:
            return shared_session

        event_gateway = EventGateway()
        discord_service = MockDiscordService()
        discord_service.bot.session_factory = session_factory

        openrouter_client = MagicMock(spec=OpenRouterClient)
        openrouter_client.complete = AsyncMock(
            return_value=(
                "**Execution Success Report**\n"
                "- Completed research on MCP.\n"
                "- Findings saved."
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

        memory_service = MemoryService(shared_session)
        task_service = TaskService(shared_session, memory_service, event_gateway)
        approval_service = ApprovalService(
            shared_session, memory_service, [111222333], event_gateway
        )

        # 1. Ingest task with goal prefix
        print("\n[Step 1] Creating goal-driven task 'goal:Research latest MCP developments'...")
        task = await task_service.create_task(
            title="MCP Ecosystem Research",
            description="goal:Research latest MCP ecosystem developments",
            priority=3,
            runtime_type="agent",
            runtime_id="hermes",
            execution_profile="research",
            runtime_policy="approved",
        )
        await root_session.flush()
        await print_task_details(shared_session, task.id)

        # 2. Queue Task (creates approval gate)
        print("\n[Step 2] Queueing task to trigger approval gate...")
        await task_service.change_status(task.id, TaskStatus.QUEUED)
        await root_session.flush()

        # Simulate outbox dispatcher
        from nexus.gateway.outbox import dispatch_outbox_event
        from nexus.memory.models import SystemEventRecord

        stmt = select(SystemEventRecord).where(SystemEventRecord.status == "pending")
        res = await root_session.execute(stmt)
        records = res.scalars().all()
        for rec in records:
            await dispatch_outbox_event(rec, discord_service)  # type: ignore[arg-type]
            rec.status = "sent"
        await root_session.flush()

        print(
            f"  - Discord approval request cards posted: "
            f"{len(discord_service.approval_requests)}"
        )

        # 3. Operator Approves
        app_stmt = select(ApprovalRecord).where(ApprovalRecord.task_id == task.id)
        app_res = await root_session.execute(app_stmt)
        approval = app_res.scalar_one()

        print("\n[Step 3] Operator grants approval via Discord owner click...")
        await approval_service.evaluate_approval(
            approval_id=approval.id,
            decision=ApprovalStatus.APPROVED,
            decided_by="111222333",
            reason="Approved research goal",
        )
        await root_session.flush()

        # 4. Trigger Execution
        print("\n[Step 4] Dispatching run_execution_flow using Hermes Adapter...")
        await orchestrator.run_execution_flow(task.id)
        await root_session.flush()

        # 5. Verify outcomes
        print("\n[Step 5] Workflow execution completed. Querying SQLite database records...")
        await print_task_details(shared_session, task.id)

        exec_stmt = select(ExecutionRecord).where(ExecutionRecord.task_id == task.id)
        exec_res = await root_session.execute(exec_stmt)
        execution = exec_res.scalar_one()

        await print_agent_steps(shared_session, execution.id)
        await print_artifacts(shared_session, execution.id)

        await root_session.commit()


async def main() -> None:
    db_url = "sqlite+aiosqlite:///data/hermes_acceptance.db"
    if os.path.exists("data/hermes_acceptance.db"):
        with contextlib.suppress(Exception):
            os.remove("data/hermes_acceptance.db")

    engine = await init_db(db_url)

    # Seed registry
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add(
            RepositoryRegistryRecord(
                id=uuid.uuid4(),
                name="workspace_root",
                absolute_path=os.path.abspath("."),
                allowed_branches=["*"],
                allowed_commands=["*"],
                is_active=True,
            )
        )
        await session.commit()

    try:
        await run_hermes_validation(engine)
    finally:
        await engine.dispose()
        print("\nHermes validation complete.")


if __name__ == "__main__":
    asyncio.run(main())
