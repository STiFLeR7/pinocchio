import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from nexus.approvals.service import ApprovalService
from nexus.core.types import ApprovalStatus, TaskStatus
from nexus.database import Base
from nexus.gateway.gateway import EventGateway
from nexus.intelligence.openrouter import OpenRouterClient
from nexus.memory.models import (
    ApprovalRecord,
    AuditLogRecord,
    ExecutionRecord,
    ExecutionStepRecord,
    TaskRecord,
)
from nexus.memory.service import MemoryService
from nexus.memory.task_service import TaskService
from nexus.scheduling.orchestrator import WorkflowOrchestrator


# SafeSessionWrapper to share single session in SQLite
class SafeSessionWrapper:
    def __init__(self, session):
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    async def commit(self):
        await self._session.flush()

    async def rollback(self):
        await self._session.rollback()

    async def close(self):
        pass


# Setup mock Discord service
class MockDiscordService:
    def __init__(self):
        self.posted_messages = []
        self.approval_requests = []
        self.bot = MagicMock()
        self.bot.settings.discord.owner_ids = [111222333]
        self.bot.session_factory = None

    async def post_message(self, channel_key, content=None, embed=None, view=None):
        self.posted_messages.append(
            {"channel": channel_key, "content": content, "embed": embed, "view": view}
        )
        return MagicMock()

    async def send_approval_request(
        self, task_id, approval_id, task_title, task_description, task_priority
    ):
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


# Setup database helper
async def init_db(engine_url):
    engine = create_async_engine(engine_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    return engine


async def print_task_details(session, task_id):
    stmt = select(TaskRecord).where(TaskRecord.id == task_id)
    res = await session.execute(stmt)
    task = res.scalar_one_or_none()
    if task:
        print(
            f"  [DB TaskRecord] ID: {task.id} | Title: '{task.title}' | "
            f"Status: '{task.status}' | Priority: {task.priority}"
        )
    else:
        print(f"  [DB TaskRecord] NOT FOUND for ID {task_id}")


async def print_approval_details(session, task_id):
    stmt = select(ApprovalRecord).where(ApprovalRecord.task_id == task_id)
    res = await session.execute(stmt)
    approvals = res.scalars().all()
    for app in approvals:
        print(
            f"  [DB ApprovalRecord] ID: {app.id} | Status: '{app.status}' | "
            f"Decided By: {app.decided_by} | Reason: '{app.decision_reason}'"
        )


async def print_execution_details(session, task_id):
    stmt = select(ExecutionRecord).where(ExecutionRecord.task_id == task_id)
    res = await session.execute(stmt)
    executions = res.scalars().all()
    for ex in executions:
        print(
            f"  [DB ExecutionRecord] ID: {ex.id} | "
            f"Runner: {ex.runner} | Exit Status: '{ex.exit_status}'"
        )
        logs = ex.logs or ""
        print(f"    - Logs (truncated): {logs[:120]}...")
        # Step logs
        step_stmt = select(ExecutionStepRecord).where(ExecutionStepRecord.execution_id == ex.id)
        step_res = await session.execute(step_stmt)
        steps = step_res.scalars().all()
        for st in steps:
            print(
                f"      [DB Step] Step ID: {st.id} | "
                f"Status: '{st.status}' | Exit Code: {st.exit_code}"
            )


async def print_audit_logs(session):
    stmt = select(AuditLogRecord).order_by(AuditLogRecord.created_at.asc())
    res = await session.execute(stmt)
    records = res.scalars().all()
    print("  [DB AuditLogRecords] Latest entries:")
    for rec in records[-10:]:
        print(
            f"    - Event: '{rec.event_type}' | Actor: '{rec.actor}' | Component: '{rec.component}'"
        )


async def run_happy_path(engine):
    print("\n=== RUNNING E2E WORKFLOW HAPPY PATH ===")

    root_session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with root_session_factory() as root_session:
        shared_session = SafeSessionWrapper(root_session)

        def session_factory():
            return shared_session

        event_gateway = EventGateway()
        discord_service = MockDiscordService()
        discord_service.bot.session_factory = session_factory

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
            discord_service=discord_service,
            openrouter_client=openrouter_client,
        )
        orchestrator.on_approval_granted = AsyncMock()
        orchestrator.register_listeners()

        memory_service = MemoryService(shared_session)
        task_service = TaskService(shared_session, memory_service, event_gateway)
        approval_service = ApprovalService(
            shared_session, memory_service, [111222333], event_gateway
        )

        # 1. Create task from Discord
        print("\n[Step 1] Ingesting task via Discord Slash command `/task_create`...")
        task = await task_service.create_task(
            title="Deploy Auth Microservice",
            description="cmd:echo 'Building docker container...'\ncmd:echo 'Testing endpoints...'",
            priority=3,
            runtime_type="cli",
            runtime_id="gemini",
        )
        await root_session.flush()
        await print_task_details(shared_session, task.id)

        # 2. Queue Task
        print("\n[Step 2] Queueing task (changing status to QUEUED)...")
        await task_service.change_status(task.id, TaskStatus.QUEUED)
        await root_session.flush()

        # Simulating Outbox dispatch manually
        from nexus.gateway.outbox import dispatch_outbox_event
        from nexus.memory.models import SystemEventRecord

        stmt = select(SystemEventRecord).where(SystemEventRecord.status == "pending")
        res = await root_session.execute(stmt)
        records = res.scalars().all()
        for rec in records:
            await dispatch_outbox_event(rec, discord_service)
            rec.status = "sent"
        await root_session.flush()

        print("\n[Step 3] Verification of Task Persistence and Approval Request Generation...")
        await print_task_details(shared_session, task.id)
        await print_approval_details(shared_session, task.id)
        print(
            f"  - Discord approval request cards posted: {len(discord_service.approval_requests)}"
        )

        # Obtain approval ID
        app_stmt = select(ApprovalRecord).where(ApprovalRecord.task_id == task.id)
        app_res = await root_session.execute(app_stmt)
        approval = app_res.scalar_one()

        # 3. Approve via OWNER_DISCORD_ID
        print(
            "\n[Step 4] Operator approves using OWNER_DISCORD_ID (111222333) "
            "via Discord click button..."
        )
        await approval_service.evaluate_approval(
            approval_id=approval.id,
            decision=ApprovalStatus.APPROVED,
            decided_by="111222333",
            reason="Manual verify via Discord View UI",
        )
        await root_session.flush()

        # State transitions to ACTIVE
        await print_task_details(shared_session, task.id)
        await print_approval_details(shared_session, task.id)

        # 4. Trigger execution flow
        print("\n[Step 5] Triggering execution workflow...")
        await orchestrator.run_execution_flow(task.id)
        await root_session.flush()

        # Verify persistence and results
        print("\n[Step 6] Execution completed. Verifying results and summaries...")
        await print_task_details(shared_session, task.id)
        await print_execution_details(shared_session, task.id)

        # Verify openrouter completion generator
        print(f"  - OpenRouter API complete called: {openrouter_client.complete.called}")
        summary_msgs = [
            m for m in discord_service.posted_messages
            if m['channel'] == 'summaries'
        ]
        print(
            f"  - Summary report messages posted: {len(summary_msgs)}"
        )

        # Print audit logs
        await print_audit_logs(shared_session)

        # Commit all to write to disk
        await root_session.commit()


async def run_scenario_a_expiration(engine):
    print("\n=== RUNNING SCENARIO A: APPROVAL EXPIRED ===")
    root_session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with root_session_factory() as root_session:
        shared_session = SafeSessionWrapper(root_session)

        def session_factory():
            return shared_session

        event_gateway = EventGateway()
        discord_service = MockDiscordService()
        discord_service.bot.session_factory = session_factory

        orchestrator = WorkflowOrchestrator(
            session_factory=session_factory,
            event_gateway=event_gateway,
            discord_service=discord_service,
            openrouter_client=MagicMock(),
        )
        orchestrator.register_listeners()

        memory_service = MemoryService(shared_session)
        task_service = TaskService(shared_session, memory_service, event_gateway)
        approval_service = ApprovalService(
            shared_session, memory_service, [111222333], event_gateway
        )

        # Create and queue task
        task = await task_service.create_task(
            title="Temp Task",
            description="cmd:echo 'Runs'",
            priority=2,
            runtime_type="cli",
            runtime_id="gemini",
        )
        await task_service.change_status(task.id, TaskStatus.QUEUED)
        await root_session.flush()

        # Grab approval record and forcefully expire it in DB
        app_stmt = select(ApprovalRecord).where(ApprovalRecord.task_id == task.id)
        app_res = await root_session.execute(app_stmt)
        approval = app_res.scalar_one()

        # Modify expires_at to 1 hour ago
        approval.expires_at = datetime.now(UTC) - timedelta(hours=1)
        await root_session.flush()

        # Check expiration sweep
        print(
            f"  - Prior to expiry check: Task Status: '{task.status}', "
            f"Approval Status: '{approval.status}'"
        )
        await approval_service.sweep_expired_approvals()
        await root_session.flush()

        # Re-fetch task state
        await print_task_details(shared_session, task.id)
        await print_approval_details(shared_session, task.id)
        await root_session.commit()


async def run_scenario_b_execution_failure(engine):
    print("\n=== RUNNING SCENARIO B: RUNNER EXECUTION FAILS ===")
    root_session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with root_session_factory() as root_session:
        shared_session = SafeSessionWrapper(root_session)

        def session_factory():
            return shared_session

        event_gateway = EventGateway()
        discord_service = MockDiscordService()
        discord_service.bot.session_factory = session_factory

        openrouter_client = MagicMock(spec=OpenRouterClient)
        openrouter_client.complete = AsyncMock(
            return_value="**Execution Failure Report**\n- Runner returned failure code."
        )

        orchestrator = WorkflowOrchestrator(
            session_factory=session_factory,
            event_gateway=event_gateway,
            discord_service=discord_service,
            openrouter_client=openrouter_client,
        )
        orchestrator.on_approval_granted = AsyncMock()
        orchestrator.register_listeners()

        memory_service = MemoryService(shared_session)
        task_service = TaskService(shared_session, memory_service, event_gateway)
        approval_service = ApprovalService(
            shared_session, memory_service, [111222333], event_gateway
        )

        # Create task with a failing command
        task = await task_service.create_task(
            title="Compile Broken Code",
            description="cmd:exit 42",
            priority=4,
            runtime_type="cli",
            runtime_id="gemini",
        )
        await task_service.change_status(task.id, TaskStatus.QUEUED)
        await root_session.flush()

        # Obtain approval ID
        app_stmt = select(ApprovalRecord).where(ApprovalRecord.task_id == task.id)
        app_res = await root_session.execute(app_stmt)
        approval = app_res.scalar_one()

        # Approve task
        await approval_service.evaluate_approval(
            approval_id=approval.id,
            decision=ApprovalStatus.APPROVED,
            decided_by="111222333",
            reason="Approve failing execution",
        )
        await root_session.flush()

        # Run execution flow
        await orchestrator.run_execution_flow(task.id)
        await root_session.flush()

        # Verify results
        await print_task_details(shared_session, task.id)
        await print_execution_details(shared_session, task.id)
        await root_session.commit()


async def run_scenario_d_restart_recovery(engine_url):
    print("\n=== RUNNING SCENARIO D: RESTART RECOVERY ===")

    # 1. Initialize first run engine and block a task
    print("\n[Engine #1] Starting system and creating a queued task...")
    engine1 = create_async_engine(engine_url, echo=False)
    session_factory1 = async_sessionmaker(engine1, expire_on_commit=False)

    async with session_factory1() as root_session1:
        shared_session1 = SafeSessionWrapper(root_session1)

        def session_factory1_wrapped():
            return shared_session1

        event_gateway1 = EventGateway()
        discord_service1 = MockDiscordService()
        discord_service1.bot.session_factory = session_factory1_wrapped

        orchestrator1 = WorkflowOrchestrator(
            session_factory=session_factory1_wrapped,
            event_gateway=event_gateway1,
            discord_service=discord_service1,
            openrouter_client=MagicMock(),
        )
        orchestrator1.register_listeners()

        memory_service1 = MemoryService(shared_session1)
        task_service1 = TaskService(shared_session1, memory_service1, event_gateway1)

        task = await task_service1.create_task(
            title="Recoverable Deploy",
            description="cmd:echo 'Ready'",
            priority=3,
            runtime_type="cli",
            runtime_id="gemini",
        )
        await task_service1.change_status(task.id, TaskStatus.QUEUED)
        await root_session1.commit()

        print(f"  - Prior to shutdown: Task '{task.title}' status is '{task.status}'")

    await engine1.dispose()
    print("  - Engine #1 completely shutdown/disposed.")

    # 2. Restart and boot Engine #2 mapping the same file database
    print("\n[Engine #2] Booting new engine instance and initializing recovery sweep...")
    engine2 = create_async_engine(engine_url, echo=False)
    session_factory2 = async_sessionmaker(engine2, expire_on_commit=False)

    # Verify we can reload task and state from DB
    async with session_factory2() as root_session2:
        # Verify state is re-loaded correctly
        stmt = select(TaskRecord).where(TaskRecord.title == "Recoverable Deploy")
        res = await root_session2.execute(stmt)
        recovered_task = res.scalar_one()
        print(f"  - Recovered task ID: {recovered_task.id} | Status: '{recovered_task.status}'")

        # Verify state matches and we can resume workflow
        assert recovered_task.status == TaskStatus.BLOCKED.value
        print("  - State consistency verified: Task remained safely BLOCKED in sqlite.")

    await engine2.dispose()


async def main():
    db_url = "sqlite+aiosqlite:///data/acceptance_test.db"
    engine = await init_db(db_url)

    # Seed repository registry to pass governance checks
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        import os

        from nexus.memory.models import RepositoryRegistryRecord

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
        await run_happy_path(engine)
        await run_scenario_a_expiration(engine)
        await run_scenario_b_execution_failure(engine)
        await run_scenario_d_restart_recovery(db_url)
    finally:
        await engine.dispose()
        print("\nVerification execution complete.")


if __name__ == "__main__":
    asyncio.run(main())
