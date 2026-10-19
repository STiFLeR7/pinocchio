"""Unit tests for the Claude CLI Runtime Adapter (ClaudeRuntimeAdapter)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.core.types import ExecutionStatus
from nexus.execution.runners.claude import ClaudeRuntimeAdapter
from nexus.memory.models import (
    ApprovalRecord,
    ExecutionArtifactRecord,
    ExecutionRecord,
    ExecutionStepRecord,
    TaskRecord,
    WorkflowCheckpointRecord,
)


@pytest.mark.asyncio
async def test_claude_initialize(db_session: AsyncSession) -> None:
    """Verify initialization checks for ClaudeRuntimeAdapter."""
    adapter = ClaudeRuntimeAdapter(db_session, uuid.uuid4())
    await adapter.initialize()
    # Does not crash or raise exception even without keys


@pytest.mark.asyncio
async def test_claude_validate_fails_no_execution_record(db_session: AsyncSession) -> None:
    """Ensure validate raises error if parent ExecutionRecord does not exist."""
    exec_id = uuid.uuid4()
    adapter = ClaudeRuntimeAdapter(db_session, exec_id)
    from nexus.core.exceptions import ExecutionEngineError

    with pytest.raises(ExecutionEngineError, match=f"Execution record {exec_id} not found"):
        await adapter.validate(repository_path=".", command="echo 'hi'")


@pytest.mark.asyncio
async def test_claude_validate_success(db_session: AsyncSession) -> None:
    """Ensure validate passes when database holds matching execution, task, and approval."""
    task = TaskRecord(
        id=uuid.uuid4(),
        title="Task",
        description="echo 'hi'",
        status="created",
        priority=2,
    )
    db_session.add(task)
    await db_session.flush()

    approval = ApprovalRecord(
        id=uuid.uuid4(),
        task_id=task.id,
        status="approved",
        requested_at=datetime.now(UTC),
        decided_by="111222333",
        decision_reason="Ok",
    )
    db_session.add(approval)
    await db_session.flush()

    exec_record = ExecutionRecord(
        id=uuid.uuid4(),
        task_id=task.id,
        approval_id=approval.id,
        runner="claude",
        repository=".",
    )
    db_session.add(exec_record)
    await db_session.flush()

    adapter = ClaudeRuntimeAdapter(db_session, exec_record.id)
    await adapter.validate(repository_path=".", command="echo 'hi'")


@pytest.mark.asyncio
async def test_claude_execute_and_checkpoint(db_session: AsyncSession) -> None:
    """Verify subprocess execution run and checkpointing states."""
    task = TaskRecord(
        id=uuid.uuid4(),
        title="Execute Task",
        description="echo 'Success Output'",
        status="created",
        priority=1,
    )
    db_session.add(task)
    await db_session.flush()

    exec_record = ExecutionRecord(
        id=uuid.uuid4(),
        task_id=task.id,
        runner="claude",
        repository=".",
    )
    db_session.add(exec_record)
    await db_session.flush()

    adapter = ClaudeRuntimeAdapter(db_session, exec_record.id)

    # Run the echo command execution
    res = await adapter.execute("echo 'Success Output'")
    assert res["exit_code"] == 0
    assert res["duration_seconds"] >= 0
    assert "Success Output" in adapter.stdout_log

    # Check that execution step record was created and updated
    step_stmt = select(ExecutionStepRecord).where(
        ExecutionStepRecord.execution_id == exec_record.id
    )
    step_res = await db_session.execute(step_stmt)
    step = step_res.scalar_one()
    assert step.status == ExecutionStatus.COMPLETED.value
    assert step.exit_code == 0
    assert "Success Output" in (step.stdout or "")

    # Test checkpointing
    checkpoint_state = {"completed_steps": ["step1"]}
    await adapter.checkpoint("test_step", checkpoint_state)

    cp_stmt = select(WorkflowCheckpointRecord).where(
        WorkflowCheckpointRecord.workflow_id == exec_record.id
    )
    cp_res = await db_session.execute(cp_stmt)
    checkpoint = cp_res.scalar_one()
    assert checkpoint.step_name == "test_step"
    assert checkpoint.state == checkpoint_state


@pytest.mark.asyncio
async def test_claude_heartbeat(db_session: AsyncSession) -> None:
    """Ensure heartbeat updates timestamps correctly on execution and steps."""
    task = TaskRecord(
        id=uuid.uuid4(),
        title="Heartbeat Task",
        description="echo 'pulse'",
        status="created",
        priority=1,
    )
    db_session.add(task)
    await db_session.flush()

    exec_record = ExecutionRecord(
        id=uuid.uuid4(),
        task_id=task.id,
        runner="claude",
        repository=".",
    )
    db_session.add(exec_record)
    await db_session.flush()

    adapter = ClaudeRuntimeAdapter(db_session, exec_record.id)

    # Run execute so a step record is instantiated
    await adapter.execute("echo 'pulse'")

    # Set heartbeat
    await adapter.heartbeat()

    # Re-fetch step and execution
    await db_session.refresh(exec_record)
    assert exec_record.last_heartbeat is not None


@pytest.mark.asyncio
async def test_claude_summarize_and_persist(db_session: AsyncSession) -> None:
    """Ensure execute outcomes write standard and summary artifacts to storage."""
    task = TaskRecord(
        id=uuid.uuid4(),
        title="Task to persist",
        description="echo 'output stream'",
        status="created",
        priority=1,
    )
    db_session.add(task)
    await db_session.flush()

    exec_record = ExecutionRecord(
        id=uuid.uuid4(),
        task_id=task.id,
        runner="claude",
        repository=".",
    )
    db_session.add(exec_record)
    await db_session.flush()

    mock_openrouter = MagicMock()
    mock_openrouter.complete = AsyncMock(return_value="Model synthesized execution report summary")

    adapter = ClaudeRuntimeAdapter(
        db_session=db_session,
        execution_id=exec_record.id,
        openrouter_client=mock_openrouter,
    )

    await adapter.execute("echo 'output stream'")
    await adapter.persist()

    # Query persisted artifacts
    stmt = select(ExecutionArtifactRecord).where(
        ExecutionArtifactRecord.execution_id == exec_record.id
    )
    res = await db_session.execute(stmt)
    artifacts = res.scalars().all()

    # We expect: stdout, summary
    # stderr is empty so not persisted. diff might be empty (size 0) or skipped if not a git diff
    artifact_types = [a.artifact_type for a in artifacts]
    assert "stdout" in artifact_types
    assert "summary" in artifact_types

    summary_art = next(a for a in artifacts if a.artifact_type == "summary")
    assert summary_art.content == "Model synthesized execution report summary"
    assert summary_art.data is not None
    assert summary_art.data["exit_code"] == 0
