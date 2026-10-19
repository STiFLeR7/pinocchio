"""Unit tests for the ContextCompiler memory state traversal."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from nexus.memory.manager import ContextCompiler
from nexus.memory.models import AuditLogRecord, WorkflowCheckpointRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_compile_context_defaults(db_session: AsyncSession) -> None:
    """Verify context compiler handles tasks with no history by returning defaults."""
    compiler = ContextCompiler(db_session)
    workflow_id = uuid.uuid4()

    frame = await compiler.compile_context(workflow_id)

    assert frame.workflow_id == workflow_id
    assert frame.messages == []
    assert frame.model == "nvidia/llama-3.1-nemotron-ultra-253b-v1:free"
    assert frame.thinking_level is None
    assert frame.active_tools == []


@pytest.mark.asyncio
async def test_compile_context_audit_reduction(db_session: AsyncSession) -> None:
    """Verify that compiling context plays back audit logs sequentially (reductions)."""
    compiler = ContextCompiler(db_session)
    workflow_id = uuid.uuid4()
    base_time = datetime.now(UTC)

    # 1. Add model change event
    event1 = AuditLogRecord(
        event_type="model_change",
        entity_type="task",
        entity_id=workflow_id,
        data={"model": "anthropic/claude-3-opus"},
        created_at=base_time,
    )

    # 2. Add message event
    event2 = AuditLogRecord(
        event_type="message",
        entity_type="task",
        entity_id=workflow_id,
        data={"message": {"role": "user", "content": "Hello Nexus"}},
        created_at=base_time + timedelta(seconds=1),
    )

    # 3. Add thinking level change event
    event3 = AuditLogRecord(
        event_type="thinking_level_change",
        entity_type="task",
        entity_id=workflow_id,
        data={"thinking_level": 3},
        created_at=base_time + timedelta(seconds=2),
    )

    # 4. Add another model change event (should overwrite previous)
    event4 = AuditLogRecord(
        event_type="model_change",
        entity_type="task",
        entity_id=workflow_id,
        data={"model": "google/gemini-2-pro"},
        created_at=base_time + timedelta(seconds=3),
    )

    db_session.add_all([event1, event2, event3, event4])
    await db_session.flush()

    frame = await compiler.compile_context(workflow_id)

    assert frame.workflow_id == workflow_id
    assert frame.model == "google/gemini-2-pro"
    assert frame.thinking_level == 3
    assert len(frame.messages) == 1
    assert frame.messages[0] == {"role": "user", "content": "Hello Nexus"}


@pytest.mark.asyncio
async def test_compile_context_with_checkpoint_and_logs(db_session: AsyncSession) -> None:
    """Verify that ContextCompiler loads a checkpoint state and appends subsequent logs."""
    compiler = ContextCompiler(db_session)
    workflow_id = uuid.uuid4()
    base_time = datetime.now(UTC)

    # 1. Add older checkpoint
    checkpoint = WorkflowCheckpointRecord(
        workflow_id=workflow_id,
        step_name="planning_phase",
        state={
            "messages": [{"role": "system", "content": "Compact history log"}],
            "model": "nvidia/llama-3.1-nemotron-ultra-253b-v1:free",
            "thinking_level": 1,
            "active_tools": ["git_status"],
            "metadata": {},
        },
        created_at=base_time - timedelta(minutes=10),
    )
    db_session.add(checkpoint)

    # 2. Add an audit log event older than the checkpoint (must be ignored)
    ignored_event = AuditLogRecord(
        event_type="model_change",
        entity_type="task",
        entity_id=workflow_id,
        data={"model": "ignored-model"},
        created_at=base_time - timedelta(minutes=15),
    )

    # 3. Add subsequent model change event
    event = AuditLogRecord(
        event_type="model_change",
        entity_type="task",
        entity_id=workflow_id,
        data={"model": "anthropic/claude-3-sonnet"},
        created_at=base_time,
    )

    # 4. Add subsequent message event
    msg_event = AuditLogRecord(
        event_type="message",
        entity_type="task",
        entity_id=workflow_id,
        data={"message": {"role": "assistant", "content": "Executing changes"}},
        created_at=base_time + timedelta(seconds=1),
    )

    db_session.add_all([ignored_event, event, msg_event])
    await db_session.flush()

    frame = await compiler.compile_context(workflow_id)

    assert frame.workflow_id == workflow_id
    assert frame.model == "anthropic/claude-3-sonnet"
    assert frame.thinking_level == 1
    assert frame.active_tools == ["git_status"]
    assert len(frame.messages) == 2
    assert frame.messages[0] == {"role": "system", "content": "Compact history log"}
    assert frame.messages[1] == {"role": "assistant", "content": "Executing changes"}
