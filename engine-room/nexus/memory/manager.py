"""Memory Manager for derived state traversal and context compilation.

Traverses checkpoints and plays back audit logs to reconstruct the active
SessionContext / ContextFrame.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from nexus.memory.models import AuditLogRecord, WorkflowCheckpointRecord
from nexus.memory.schemas import ContextFrame

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ContextCompiler:
    """Compiles the ContextFrame from WorkflowCheckpoints and AuditLogs."""

    def __init__(self, db_session: AsyncSession) -> None:
        """Initialize the compiler with an active database session."""
        self.session = db_session

    async def compile_context(
        self,
        workflow_id: uuid.UUID,
        default_model: str = "nvidia/llama-3.1-nemotron-ultra-253b-v1:free",
    ) -> ContextFrame:
        """Reconstruct the derived context state by replaying history log events."""
        # 1. Query latest checkpoint
        stmt = (
            select(WorkflowCheckpointRecord)
            .where(WorkflowCheckpointRecord.workflow_id == workflow_id)
            .order_by(WorkflowCheckpointRecord.created_at.desc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        checkpoint = res.scalar_one_or_none()

        # Initialize from checkpoint if found, otherwise use default empty states
        if checkpoint and checkpoint.state:
            state = checkpoint.state
            messages = list(state.get("messages", []))
            model = state.get("model", default_model)
            thinking_level = state.get("thinking_level")
            active_tools = list(state.get("active_tools", []))
            metadata = dict(state.get("metadata", {}))
            checkpoint_time = checkpoint.created_at
        else:
            messages = []
            model = default_model
            thinking_level = None
            active_tools = []
            metadata = {}
            checkpoint_time = None

        # 2. Query all AuditLogRecords generated AFTER the checkpoint's timestamp
        audit_stmt = select(AuditLogRecord).where(AuditLogRecord.entity_id == workflow_id)
        if checkpoint_time is not None:
            audit_stmt = audit_stmt.where(AuditLogRecord.created_at > checkpoint_time)
        audit_stmt = audit_stmt.order_by(AuditLogRecord.created_at.asc())

        audit_res = await self.session.execute(audit_stmt)
        logs = audit_res.scalars().all()

        # 3. Apply state reductions (PAT-001 Reduction Flow)
        for log in logs:
            event_type = log.event_type
            data = log.data or {}

            if event_type in ("model_change", "config.model"):
                model = str(data.get("model", model))
            elif event_type in ("thinking_level_change", "config.thinking_level"):
                val = data.get("thinking_level")
                thinking_level = int(val) if val is not None else None
            elif event_type in ("active_tools_change", "config.active_tools"):
                active_tools = list(data.get("active_tools", active_tools))
            elif event_type in (
                "message",
                "task.created",
                "task.updated",
                "execution.step.started",
                "execution.step.completed",
            ):
                if "message" in data:
                    messages.append(data["message"])
                elif "logs" in data:
                    messages.append({"role": "system", "content": data["logs"]})

        return ContextFrame(
            workflow_id=workflow_id,
            messages=messages,
            model=model,
            thinking_level=thinking_level,
            active_tools=active_tools,
            metadata=metadata,
        )
