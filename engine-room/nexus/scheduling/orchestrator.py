"""Event-driven workflow orchestrator coordination layer.

Subscribes to system state transition events and executes the appropriate step
in the task/approval/execution pipeline.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any

import discord
import structlog
from sqlalchemy import select

from nexus.core.types import EventType, ExitStatus, TaskStatus
from nexus.database import get_session
from nexus.intelligence.summary import SummaryEngine

if TYPE_CHECKING:
    from nexus.communication.discord.service import DiscordService
    from nexus.core.events import NexusEvent
    from nexus.intelligence.openrouter import OpenRouterClient

logger = structlog.get_logger("nexus.scheduling.orchestrator")


def resolve_exit_status(result: dict[str, Any]) -> ExitStatus:
    """Map a runtime result to a final ExitStatus, honoring agent terminal status (H-4).

    Agent runtimes (the Nexus agent) report a truthful terminal ``status`` (completed/failed/timed_out/
    cancelled) which maps to the corresponding ``ExitStatus`` so timeouts and cancellations are
    finalized distinctly from generic failures. CLI runtimes report only ``exit_code`` and fall back
    to the success/failure mapping — preserving prior behavior.
    """
    data = result or {}
    status = data.get("status")
    mapping = {
        "completed": ExitStatus.SUCCESS,
        "failed": ExitStatus.FAILURE,
        "timed_out": ExitStatus.TIMEOUT,
        "cancelled": ExitStatus.CANCELLED,
    }
    if status in mapping:
        return mapping[status]
    return ExitStatus.SUCCESS if data.get("exit_code", 0) == 0 else ExitStatus.FAILURE


class WorkflowOrchestrator:
    """Subscribes to system events and drives the E2E lifecycle workflows."""

    def __init__(
        self,
        session_factory: Any,
        event_gateway: Any,
        discord_service: DiscordService,
        openrouter_client: OpenRouterClient,
    ) -> None:
        """Initialize the orchestrator with required shared adapters."""
        self.session_factory = session_factory
        self.event_gateway = event_gateway
        self.discord_service = discord_service
        self.openrouter_client = openrouter_client
        self._tasks: set[asyncio.Task[Any]] = set()

    def register_listeners(self) -> None:
        """Register asynchronous event handler subscription callbacks."""
        self.event_gateway.subscribe(EventType.TASK_UPDATED, self.on_task_updated)
        self.event_gateway.subscribe(EventType.APPROVAL_GRANTED, self.on_approval_granted)
        self.event_gateway.subscribe(EventType.EXECUTION_COMPLETED, self.on_execution_finished)
        self.event_gateway.subscribe(EventType.EXECUTION_FAILED, self.on_execution_finished)
        logger.info("orchestrator_listeners_registered")

    async def on_task_updated(self, event: NexusEvent) -> None:
        """Evaluate task queue transitions to trigger manual approvals."""
        task_id = event.entity_id
        if not task_id:
            return

        status = event.data.get("status")
        # Check either event data status OR check if task is queued via queue_position flag
        is_queued = (status == TaskStatus.QUEUED.value) or ("queue_position" in event.data)

        if is_queued:
            logger.info("orchestrator_handling_queued_task", task_id=str(task_id))
            async with get_session(self.session_factory) as session:
                from nexus.approvals.service import ApprovalService
                from nexus.memory.service import MemoryService

                memory_service = MemoryService(session)
                approval_service = ApprovalService(
                    session,
                    memory_service,
                    self.discord_service.bot.settings.discord.owner_ids,
                    self.event_gateway,
                )
                await approval_service.create_approval_request(task_id)

    async def on_approval_granted(self, event: NexusEvent) -> None:
        """Resolve parent task linked to approval and spawn execution background loop."""
        approval_id = event.entity_id
        if not approval_id:
            return

        logger.info("orchestrator_handling_approved_gate", approval_id=str(approval_id))

        async with get_session(self.session_factory) as session:
            from nexus.memory.models import ApprovalRecord

            stmt = select(ApprovalRecord).where(ApprovalRecord.id == approval_id)
            res = await session.execute(stmt)
            approval = res.scalar_one_or_none()
            if not approval:
                logger.error("orchestrator_approval_record_not_found", approval_id=str(approval_id))
                return
            task_id = approval.task_id

        # Execute the workflow asynchronously in a background task
        run_task = asyncio.create_task(self.run_execution_flow(task_id))
        self._tasks.add(run_task)
        run_task.add_done_callback(self._tasks.discard)

    async def run_execution_flow(self, task_id: uuid.UUID) -> None:
        """Run terminal commands inside a subprocess and streams output to Discord."""
        from nexus.core import health
        if not health.is_healthy():
            logger.error("orchestrator_execution_blocked_unhealthy_control_plane", task_id=str(task_id), reason=health.get_health_reason())
            async with get_session(self.session_factory) as session:
                from nexus.memory.models import TaskRecord
                task_stmt = select(TaskRecord).where(TaskRecord.id == task_id)
                res = await session.execute(task_stmt)
                t = res.scalar_one_or_none()
                if t:
                    t.status = TaskStatus.FAILED.value
                    await session.flush()
            return

        logger.info("orchestrator_starting_execution_pipeline", task_id=str(task_id))
        try:
            # 1. Start parent ExecutionRecord
            async with get_session(self.session_factory) as session:
                from nexus.approvals.service import ApprovalService
                from nexus.execution.service import ExecutionService
                from nexus.memory.models import TaskRecord
                from nexus.memory.service import MemoryService

                memory_service = MemoryService(session)
                approval_service = ApprovalService(
                    session,
                    memory_service,
                    self.discord_service.bot.settings.discord.owner_ids,
                    self.event_gateway,
                )
                execution_service = ExecutionService(
                    session, memory_service, approval_service, self.event_gateway
                )

                task_stmt = select(TaskRecord).where(TaskRecord.id == task_id)
                task_res = await session.execute(task_stmt)
                task = task_res.scalar_one()

                # Determine runner and command explicitly from task columns
                runner = task.runtime_id or "gemini"

                command = "echo 'Hello from Nexus Control Plane!'"
                if task.description:
                    if task.description.startswith("cmd:"):
                        command = task.description[4:].strip()
                    elif task.description.startswith("goal:"):
                        command = task.description[5:].strip()
                    else:
                        command = task.description.strip()

                execution = await execution_service.start_execution(task_id, runner=runner)
                execution_id = execution.id
                repository_path = execution.repository or "."

            logger.info(
                "spawning_subprocess_command",
                command=command,
                execution_id=str(execution_id),
            )

            # Invoke adapter contract
            async with get_session(self.session_factory) as session:
                from nexus.execution.runners import get_runtime_adapter

                adapter = get_runtime_adapter(
                    runner_name=runner,
                    db_session=session,
                    execution_id=execution_id,
                    event_gateway=self.event_gateway,
                    openrouter_client=self.openrouter_client,
                    settings=self.discord_service.bot.settings,
                )

                from nexus.execution.runners.base import AgentRuntimeAdapter, CLIRuntimeAdapter

                # Initialize
                await adapter.initialize()

                result = {}
                exit_code = 0

                if isinstance(adapter, CLIRuntimeAdapter):
                    # Validate (Governance checks)
                    await adapter.validate(repository_path=repository_path, command=command)

                    # Execute
                    await self.discord_service.post_message(
                        "execution_log",
                        content=f"💻 **Spawning Command**: `{command}`",
                    )
                    result = await adapter.execute(command)
                    exit_code = result.get("exit_code", 0)

                    # Post streams to Discord
                    stdout = adapter.stdout_log
                    stderr = adapter.stderr_log
                    if stdout:
                        await self.discord_service.post_message(
                            "execution_log",
                            content=f"📄 **STDOUT output**:\n```\n{stdout[:1800]}\n```",
                        )
                    if stderr:
                        await self.discord_service.post_message(
                            "execution_log",
                            content=f"⚠️ **STDERR output**:\n```\n{stderr[:1800]}\n```",
                        )
                elif isinstance(adapter, AgentRuntimeAdapter):
                    # Validate goal
                    await adapter.validate_goal(command)

                    # Execute goal
                    result = await adapter.execute_goal(command)
                    exit_code = result.get("exit_code", 0)
                else:
                    raise TypeError(f"Adapter {adapter} is of unsupported runtime type.")

                # Checkpoint
                await adapter.checkpoint(step_name="command_execution", state=result)

                # Persist artifacts (stdout, stderr, summary, diff)
                await adapter.persist()

                # Finalize parent execution (H-4: honor agent terminal status — timeout/cancel).
                exit_status = resolve_exit_status(result)
                from nexus.approvals.service import ApprovalService
                from nexus.execution.service import ExecutionService
                from nexus.memory.service import MemoryService

                memory_service = MemoryService(session)
                approval_service = ApprovalService(
                    session,
                    memory_service,
                    self.discord_service.bot.settings.discord.owner_ids,
                    self.event_gateway,
                )
                execution_service = ExecutionService(
                    session, memory_service, approval_service, self.event_gateway
                )
                await execution_service.finalize_execution(
                    execution_id=execution_id,
                    exit_status=exit_status,
                    result_payload=result,
                )

            logger.info(
                "orchestrator_execution_pipeline_finished",
                task_id=str(task_id),
                exit_code=exit_code,
            )

        except Exception as e:
            logger.error(
                "orchestrator_execution_pipeline_failed",
                task_id=str(task_id),
                error=str(e),
                exc_info=True,
            )
            try:
                async with get_session(self.session_factory) as session:
                    from nexus.memory.models import TaskRecord

                    task_stmt = select(TaskRecord).where(TaskRecord.id == task_id).with_for_update()
                    res = await session.execute(task_stmt)
                    rollback_task = res.scalar_one_or_none()
                    if rollback_task and rollback_task.status != TaskStatus.COMPLETED.value:
                        rollback_task.status = TaskStatus.FAILED.value
                        await session.flush()
            except Exception as rollback_err:
                logger.error("failed_task_rollback", error=str(rollback_err))

    async def on_execution_finished(self, event: NexusEvent) -> None:
        """Replay logs and query SummaryEngine to generate and post report summaries."""
        execution_id = event.entity_id
        if not execution_id:
            return

        logger.info("orchestrator_handling_finished_execution", execution_id=str(execution_id))

        try:
            async with get_session(self.session_factory) as session:
                from nexus.memory.models import ExecutionRecord

                stmt = select(ExecutionRecord).where(ExecutionRecord.id == execution_id)
                res = await session.execute(stmt)
                execution = res.scalar_one_or_none()
                if not execution:
                    logger.error(
                        "orchestrator_execution_record_not_found",
                        execution_id=str(execution_id),
                    )
                    return
                task_id = execution.task_id

            # Compile text summary
            async with get_session(self.session_factory) as session:
                summary_engine = SummaryEngine(session, self.openrouter_client)
                summary = await summary_engine.generate_task_summary(task_id)

            # Route to summaries Discord channel
            embed = discord.Embed(
                title="Task Run Report",
                description=summary,
                color=discord.Color.blue(),
            )
            embed.add_field(name="Task ID", value=f"`{task_id}`", inline=True)
            embed.add_field(name="Execution ID", value=f"`{execution_id}`", inline=True)

            await self.discord_service.post_message("summaries", embed=embed)
            logger.info("orchestrator_summary_report_delivered", task_id=str(task_id))

        except Exception as e:
            logger.error(
                "orchestrator_summary_dispatch_failed",
                execution_id=str(execution_id),
                error=str(e),
                exc_info=True,
            )
