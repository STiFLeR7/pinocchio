"""Unit tests for the Nexus Agent Runtime Adapter (NexusRuntimeAdapter)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.execution.runners.nexus_agent import NexusRuntimeAdapter
from nexus.memory.models import (
    AgentStepRecord,
    ApprovalRecord,
    ExecutionArtifactRecord,
    ExecutionRecord,
    TaskRecord,
    WorkflowCheckpointRecord,
)
from tests.unit.execution.test_nexus_agent_honesty import FakeLLMClient, FakeSearchProvider

# Structured tool-call completions used to drive the real (injected) decision branch.
_FINISH = '{"thought": "done", "tool_name": "finish", "tool_arguments": {}}'
_SEARCH = '{"thought": "search", "tool_name": "web_search", "tool_arguments": {"query": "x"}}'


@pytest.mark.asyncio
async def test_nexus_initialize(db_session: AsyncSession) -> None:
    """Initialization proceeds when an LLM client is injected (fail-fast otherwise — see lifecycle tests)."""
    adapter = NexusRuntimeAdapter(
        db_session, uuid.uuid4(), openrouter_client=FakeLLMClient([_FINISH])
    )
    await adapter.initialize()
    # Should not crash with a usable LLM capability present.


@pytest.mark.asyncio
async def test_nexus_validate_fails_no_execution(db_session: AsyncSession) -> None:
    """Ensure validate raises error if parent ExecutionRecord does not exist."""
    exec_id = uuid.uuid4()
    adapter = NexusRuntimeAdapter(db_session, exec_id)
    from nexus.core.exceptions import ExecutionEngineError

    with pytest.raises(ExecutionEngineError, match=f"Execution record {exec_id} not found"):
        await adapter.validate_goal("Research MCP Developments")


@pytest.mark.asyncio
async def test_nexus_validate_success(db_session: AsyncSession) -> None:
    """Ensure validate passes when database holds matching task, approval, and execution."""
    task = TaskRecord(
        id=uuid.uuid4(),
        title="Research Task",
        description="goal:Research MCP Developments",
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
        decision_reason="Approved",
    )
    db_session.add(approval)
    await db_session.flush()

    exec_record = ExecutionRecord(
        id=uuid.uuid4(),
        task_id=task.id,
        approval_id=approval.id,
        runner="nexus",
        repository=".",
    )
    db_session.add(exec_record)
    await db_session.flush()

    adapter = NexusRuntimeAdapter(db_session, exec_record.id)
    await adapter.validate_goal("Research MCP Developments")


@pytest.mark.asyncio
async def test_nexus_execute_and_checkpoint(db_session: AsyncSession) -> None:
    """Verify Nexus autonomous tool executions and agent_steps updates."""
    task = TaskRecord(
        id=uuid.uuid4(),
        title="Agent Task",
        description="goal:Research developments",
        status="created",
        priority=2,
    )
    db_session.add(task)
    await db_session.flush()

    exec_record = ExecutionRecord(
        id=uuid.uuid4(),
        task_id=task.id,
        runner="nexus",
        repository=".",
    )
    db_session.add(exec_record)
    await db_session.flush()

    # Inject a scripted client + search provider so the real decision branch drives a genuine
    # multi-step run (web_search -> finish), then assert persistence.
    client = FakeLLMClient(['["Investigate developments"]', _SEARCH, _FINISH])
    adapter = NexusRuntimeAdapter(
        db_session,
        exec_record.id,
        openrouter_client=client,
        search_provider=FakeSearchProvider(),
    )

    # Run execution goal
    res = await adapter.execute_goal("Research developments")
    assert res["steps_executed"] > 0
    assert res["trajectory_len"] > 0
    assert res["exit_code"] == 0
    assert res["status"] == "completed"

    # Verify agent steps persisted
    step_stmt = select(AgentStepRecord).where(AgentStepRecord.execution_id == exec_record.id)
    step_res = await db_session.execute(step_stmt)
    steps = step_res.scalars().all()
    assert len(steps) == res["steps_executed"]

    # Verify checkpoint table entries exist
    cp_stmt = select(WorkflowCheckpointRecord).where(
        WorkflowCheckpointRecord.workflow_id == exec_record.id
    )
    cp_res = await db_session.execute(cp_stmt)
    checkpoints = cp_res.scalars().all()
    assert len(checkpoints) == res["steps_executed"]


@pytest.mark.asyncio
async def test_nexus_summarize_and_persist(db_session: AsyncSession) -> None:
    """Verify trajectory summarization and persistence of plan, summary, and trajectories."""
    task = TaskRecord(
        id=uuid.uuid4(),
        title="Research Task to Persist",
        description="goal:Verify persistence",
        status="created",
        priority=2,
    )
    db_session.add(task)
    await db_session.flush()

    exec_record = ExecutionRecord(
        id=uuid.uuid4(),
        task_id=task.id,
        runner="nexus",
        repository=".",
    )
    db_session.add(exec_record)
    await db_session.flush()

    # Scripted completions: plan, finish (execute_goal), then the summary text (summarize()).
    client = FakeLLMClient(
        ['["Verify persistence step"]', _FINISH, "Synthesized Brief of MCP Research results"]
    )

    adapter = NexusRuntimeAdapter(
        db_session=db_session,
        execution_id=exec_record.id,
        openrouter_client=client,
    )

    await adapter.execute_goal("Verify persistence")
    await adapter.persist()

    # Query artifacts
    art_stmt = select(ExecutionArtifactRecord).where(
        ExecutionArtifactRecord.execution_id == exec_record.id
    )
    art_res = await db_session.execute(art_stmt)
    artifacts = art_res.scalars().all()

    artifact_types = [a.artifact_type for a in artifacts]
    assert "agent_plan" in artifact_types
    assert "agent_trajectory" in artifact_types
    assert "summary" in artifact_types

    summary_art = next(a for a in artifacts if a.artifact_type == "summary")
    assert summary_art.content == "Synthesized Brief of MCP Research results"
