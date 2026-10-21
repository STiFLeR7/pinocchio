"""Execution service managing subprocess tool runs, heartbeats, and results."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from nexus.core.exceptions import ExecutionEngineError
from nexus.core.types import ExecutionStatus, TaskStatus
from nexus.memory.models import ExecutionRecord, ExecutionStepRecord, TaskRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from nexus.approvals.service import ApprovalService
    from nexus.core.types import ExitStatus
    from nexus.gateway.gateway import EventGateway
    from nexus.memory.service import MemoryService


class ExecutionService:
    """Manages executing runner processes and tracking incremental stdout/stderr streams."""

    def __init__(
        self,
        db_session: AsyncSession,
        memory_service: MemoryService,
        approval_service: ApprovalService,
        event_gateway: EventGateway | None = None,
    ) -> None:
        """Initialize the ExecutionService with database access and approval gates."""
        self.session = db_session
        self.memory_service = memory_service
        self.approval_service = approval_service
        self.event_gateway = event_gateway

    async def start_execution(self, task_id: uuid.UUID, runner: str) -> ExecutionRecord:
        """Assert approval status is met, and initialize a new task ExecutionRecord."""
        gated = await self.approval_service.check_approval_gate(task_id)
        if not gated:
            raise ExecutionEngineError("Task does not have an active approved status.")

        # Find the latest approval gate record to link it
        from nexus.memory.models import ApprovalRecord

        stmt = (
            select(ApprovalRecord)
            .where(ApprovalRecord.task_id == task_id)
            .order_by(ApprovalRecord.created_at.desc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        approval = res.scalar_one_or_none()
        approval_id = approval.id if approval else None

        execution = ExecutionRecord(
            task_id=task_id,
            approval_id=approval_id,
            runner=runner,
            started_at=datetime.now(UTC),
        )
        self.session.add(execution)
        await self.session.flush()

        # Calculate and log execution start latency from approval decision (AP-317)
        if approval and approval.decided_at and execution.started_at:
            decided_at = approval.decided_at.replace(tzinfo=None)
            started_at = execution.started_at.replace(tzinfo=None)
            latency = (started_at - decided_at).total_seconds() * 1000.0
            from nexus.core.metrics import record_metric
            record_metric("execution_start_latency_ms", latency)
            import structlog
            structlog.get_logger("nexus.execution.service").info(
                "execution_started",
                execution_id=str(execution.id),
                execution_start_latency_ms=round(latency, 2),
            )

        # Emit ExecutionStarted event
        from nexus.core.events import NexusEvent
        from nexus.core.types import EventType

        event = NexusEvent(
            event_type=EventType.EXECUTION_STARTED,
            entity_type="execution",
            entity_id=execution.id,
            data={
                "execution_id": str(execution.id),
                "runner": runner,
            },
            source="execution_engine",
        )
        await self.memory_service.log_event(event)

        if self.event_gateway is not None:
            await self.event_gateway.publish(event)

        return execution

    async def start_step(
        self,
        execution_id: uuid.UUID,
        command: str,
        timeout_threshold: int = 300,
    ) -> ExecutionStepRecord:
        """Register the start of an atomic subprocess step under an execution."""
        step = ExecutionStepRecord(
            execution_id=execution_id,
            command=command,
            status=ExecutionStatus.RUNNING.value,
            timeout_threshold=timeout_threshold,
            last_heartbeat=datetime.now(UTC),
        )
        self.session.add(step)

        # Update parent execution heartbeat timestamp
        stmt = select(ExecutionRecord).where(ExecutionRecord.id == execution_id).with_for_update()
        res = await self.session.execute(stmt)
        execution = res.scalar_one_or_none()
        if execution:
            execution.last_heartbeat = step.last_heartbeat

        await self.session.flush()
        return step

    async def complete_step(
        self,
        step_id: uuid.UUID,
        exit_code: int = 0,
        stdout: str | None = None,
        stderr: str | None = None,
    ) -> ExecutionStepRecord:
        """Finalize details of a completed execution step."""
        stmt = (
            select(ExecutionStepRecord).where(ExecutionStepRecord.id == step_id).with_for_update()
        )
        res = await self.session.execute(stmt)
        step = res.scalar_one_or_none()

        if step is None:
            raise ExecutionEngineError(f"Execution step {step_id} not found.")

        step.status = ExecutionStatus.COMPLETED.value
        step.exit_code = exit_code
        step.stdout = stdout
        step.stderr = stderr
        step.last_heartbeat = datetime.now(UTC)

        await self.session.flush()
        return step

    async def finalize_execution(
        self,
        execution_id: uuid.UUID,
        exit_status: ExitStatus,
        result_payload: dict[str, Any] | None = None,
    ) -> ExecutionRecord:
        """Compile stdout/stderr logs from all steps, write results, and finalize task state."""
        stmt = select(ExecutionRecord).where(ExecutionRecord.id == execution_id).with_for_update()
        res = await self.session.execute(stmt)
        execution = res.scalar_one_or_none()

        if execution is None:
            raise ExecutionEngineError(f"Execution record {execution_id} not found.")

        execution.completed_at = datetime.now(UTC)
        execution.exit_status = exit_status.value

        # Aggregate logs from all subprocess steps
        step_stmt = select(ExecutionStepRecord).where(
            ExecutionStepRecord.execution_id == execution_id
        )
        step_res = await self.session.execute(step_stmt)
        steps = step_res.scalars().all()

        log_buffer = []
        for s in steps:
            log_buffer.append(
                f"Command: {s.command}\nStatus: {s.status}\nExit Code: {s.exit_code}\n"
            )
            if s.stdout:
                log_buffer.append(f"STDOUT:\n{s.stdout}\n")
            if s.stderr:
                log_buffer.append(f"STDERR:\n{s.stderr}\n")

        execution.logs = "\n".join(log_buffer)

        if result_payload is not None:
            execution.result = json.dumps(result_payload)

        # Transition task status based on success/failure
        task_stmt = select(TaskRecord).where(TaskRecord.id == execution.task_id).with_for_update()
        task_res = await self.session.execute(task_stmt)
        task = task_res.scalar_one_or_none()

        if task:
            if task.status == TaskStatus.CANCELLED.value:
                # Retain cancelled status if aborted by owner
                pass
            elif exit_status.value == "success":
                task.status = TaskStatus.COMPLETED.value
            else:
                task.status = TaskStatus.FAILED.value

        await self.session.flush()

        # Emit execution completion/failure events
        from nexus.core.events import NexusEvent
        from nexus.core.types import EventType

        event_type = (
            EventType.EXECUTION_COMPLETED
            if exit_status.value == "success"
            else EventType.EXECUTION_FAILED
        )
        event = NexusEvent(
            event_type=event_type,
            entity_type="execution",
            entity_id=execution.id,
            data={
                "execution_id": str(execution.id),
                "exit_status": exit_status.value,
            },
            source="execution_engine",
        )
        await self.memory_service.log_event(event)

        if self.event_gateway is not None:
            await self.event_gateway.publish(event)

        return execution
