"""H-4 (Pilot) — Nexus lifecycle safety tests: fail-fast init, configurable budget, terminate,
cancellation, TIMED_OUT lifecycle, and resume_goal.

Uses injected fakes via the existing constructor seam (no in-module mocks), consistent with H-2.
"""

from __future__ import annotations

import types
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.core.exceptions import ConfigurationError, ExecutionEngineError
from nexus.core.types import ExecutionStatus, ExitStatus
from nexus.execution.governance import RepositoryGovernanceError
from nexus.execution.runners.nexus_agent import NexusRuntimeAdapter
from nexus.memory.models import (
    AgentStepRecord,
    ApprovalRecord,
    ExecutionRecord,
    TaskRecord,
    WorkflowCheckpointRecord,
)
from nexus.scheduling.orchestrator import resolve_exit_status
from tests.unit.execution.test_nexus_agent_honesty import (
    FakeLLMClient,
    FakeSearchProvider,
    _finish,
    _make_execution,
)


async def _make_approved_execution(db_session: AsyncSession) -> ExecutionRecord:
    """Create a task + approved approval + execution (governance-passing) for resume tests."""
    task = TaskRecord(
        id=uuid.uuid4(), title="Resume Task", description="goal:Resume", status="created", priority=2
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
        id=uuid.uuid4(), task_id=task.id, approval_id=approval.id, runner="nexus", repository="."
    )
    db_session.add(exec_record)
    await db_session.flush()
    return exec_record

_SEARCH = '{"thought": "search", "tool_name": "web_search", "tool_arguments": {"query": "x"}}'


class LoopingLLMClient:
    """Injected client that always issues a web_search call (never finishes) — for budget/timeout."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        return _SEARCH


def _settings_with_budget(max_steps: int) -> types.SimpleNamespace:
    return types.SimpleNamespace(execution=types.SimpleNamespace(agent_max_steps=max_steps))


def _settings(max_steps: int = 5, research_timeout: int | None = None) -> types.SimpleNamespace:
    execution = types.SimpleNamespace(agent_max_steps=max_steps)
    if research_timeout is not None:
        execution.research_timeout = research_timeout
    return types.SimpleNamespace(execution=execution)


# --------------------------------------------------------------------------- Step 1: fail-fast init


@pytest.mark.asyncio
async def test_init_fails_without_client_or_key(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """initialize() must fail closed when no LLM client and no API key are available."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    adapter = NexusRuntimeAdapter(db_session, uuid.uuid4())
    with pytest.raises(ConfigurationError):
        await adapter.initialize()


@pytest.mark.asyncio
async def test_init_proceeds_with_injected_client(db_session: AsyncSession) -> None:
    """initialize() proceeds when an LLM client is injected (the run is capable)."""
    adapter = NexusRuntimeAdapter(
        db_session, uuid.uuid4(), openrouter_client=FakeLLMClient([_finish()])
    )
    await adapter.initialize()  # must not raise


@pytest.mark.asyncio
async def test_init_proceeds_with_env_key(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """initialize() proceeds when an API key is present in the environment."""
    monkeypatch.setenv("GEMINI_API_KEY", "real-key-value")
    adapter = NexusRuntimeAdapter(db_session, uuid.uuid4())
    await adapter.initialize()  # must not raise


# --------------------------------------------------------------------------- Step 2: budget


@pytest.mark.asyncio
async def test_step_budget_configurable(db_session: AsyncSession) -> None:
    """A configured agent_max_steps caps the number of executed steps."""
    exec_record = await _make_execution(db_session)
    adapter = NexusRuntimeAdapter(
        db_session,
        exec_record.id,
        openrouter_client=LoopingLLMClient(),
        settings=_settings_with_budget(2),
        search_provider=FakeSearchProvider(),
    )
    res = await adapter.execute_goal("Never finishes")
    assert res["steps_executed"] == 2


@pytest.mark.asyncio
async def test_step_budget_default_is_five(db_session: AsyncSession) -> None:
    """With no configured budget, the default of 5 steps is preserved."""
    exec_record = await _make_execution(db_session)
    adapter = NexusRuntimeAdapter(
        db_session,
        exec_record.id,
        openrouter_client=LoopingLLMClient(),
        search_provider=FakeSearchProvider(),
    )
    res = await adapter.execute_goal("Never finishes")
    assert res["steps_executed"] == 5


# --------------------------------------------------------------------------- Step 3: terminate()


class CancellingLLMClient:
    """Client that requests cancellation (via the adapter) during its first decision call."""

    def __init__(self) -> None:
        self.adapter: NexusRuntimeAdapter | None = None
        self.calls = 0

    async def complete(self, prompt: str) -> str:
        self.calls += 1
        if self.adapter is not None:
            await self.adapter.terminate()
        return _SEARCH


class FakeProcess:
    """Stand-in for an in-flight SandboxProcess to verify terminate() kills it."""

    def __init__(self) -> None:
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True


@pytest.mark.asyncio
async def test_terminate_sets_cancel_signal(db_session: AsyncSession) -> None:
    adapter = NexusRuntimeAdapter(db_session, uuid.uuid4())
    assert adapter._cancel_requested is False
    await adapter.terminate()
    assert adapter._cancel_requested is True


@pytest.mark.asyncio
async def test_terminate_kills_inflight_process(db_session: AsyncSession) -> None:
    adapter = NexusRuntimeAdapter(db_session, uuid.uuid4())
    proc = FakeProcess()
    adapter._active_process = proc
    await adapter.terminate()
    assert proc.terminated is True


@pytest.mark.asyncio
async def test_cancel_before_run_yields_cancelled(db_session: AsyncSession) -> None:
    exec_record = await _make_execution(db_session)
    adapter = NexusRuntimeAdapter(
        db_session, exec_record.id, openrouter_client=FakeLLMClient([_finish()])
    )
    await adapter.terminate()
    res = await adapter.execute_goal("Cancel before start")
    assert res["status"] == "cancelled"
    assert res["exit_code"] != 0


@pytest.mark.asyncio
async def test_cancel_mid_run_persists_cancelled_step(db_session: AsyncSession) -> None:
    exec_record = await _make_execution(db_session)
    client = CancellingLLMClient()
    adapter = NexusRuntimeAdapter(
        db_session,
        exec_record.id,
        openrouter_client=client,
        search_provider=FakeSearchProvider(),
    )
    client.adapter = adapter
    res = await adapter.execute_goal("Cancel mid run")
    assert res["status"] == "cancelled"
    steps = (
        await db_session.execute(
            select(AgentStepRecord).where(AgentStepRecord.execution_id == exec_record.id)
        )
    ).scalars().all()
    assert any(s.status == ExecutionStatus.CANCELLED.value for s in steps)


# --------------------------------------------------------------------------- Step 4: cancellation wiring


@pytest.mark.asyncio
async def test_operator_cancel_via_db_signal(db_session: AsyncSession) -> None:
    """Setting the execution's exit_status to cancelled (the orchestration path) cancels the run."""
    exec_record = await _make_execution(db_session)
    # Operator / orchestration path requests cancellation via the DB-observable signal.
    exec_record.exit_status = ExitStatus.CANCELLED.value
    await db_session.flush()

    adapter = NexusRuntimeAdapter(
        db_session,
        exec_record.id,
        openrouter_client=LoopingLLMClient(),
        search_provider=FakeSearchProvider(),
    )
    res = await adapter.execute_goal("Operator cancels")
    assert res["status"] == "cancelled"
    steps = (
        await db_session.execute(
            select(AgentStepRecord).where(AgentStepRecord.execution_id == exec_record.id)
        )
    ).scalars().all()
    assert any(s.status == ExecutionStatus.CANCELLED.value for s in steps)


def test_resolve_exit_status_maps_agent_status() -> None:
    """Orchestrator maps the agent's terminal status to the correct ExitStatus."""
    assert resolve_exit_status({"status": "completed", "exit_code": 0}) == ExitStatus.SUCCESS
    assert resolve_exit_status({"status": "failed", "exit_code": 1}) == ExitStatus.FAILURE
    assert resolve_exit_status({"status": "timed_out", "exit_code": 1}) == ExitStatus.TIMEOUT
    assert resolve_exit_status({"status": "cancelled", "exit_code": 1}) == ExitStatus.CANCELLED


def test_resolve_exit_status_falls_back_to_exit_code() -> None:
    """CLI runtimes (no 'status') still map via exit_code."""
    assert resolve_exit_status({"exit_code": 0}) == ExitStatus.SUCCESS
    assert resolve_exit_status({"exit_code": 1}) == ExitStatus.FAILURE


# --------------------------------------------------------------------------- Step 5: TIMED_OUT


async def _timed_out_steps(db_session: AsyncSession, exec_id: object) -> list[AgentStepRecord]:
    rows = (
        await db_session.execute(
            select(AgentStepRecord).where(AgentStepRecord.execution_id == exec_id)
        )
    ).scalars().all()
    return [s for s in rows if s.status == ExecutionStatus.TIMED_OUT.value]


@pytest.mark.asyncio
async def test_budget_exhaustion_times_out(db_session: AsyncSession) -> None:
    """Exhausting the step budget without a genuine finish yields TIMED_OUT (not failed)."""
    exec_record = await _make_execution(db_session)
    adapter = NexusRuntimeAdapter(
        db_session,
        exec_record.id,
        openrouter_client=LoopingLLMClient(),
        settings=_settings(max_steps=2),
        search_provider=FakeSearchProvider(),
    )
    res = await adapter.execute_goal("Never finishes")
    assert res["status"] == "timed_out"
    assert res["exit_code"] != 0
    assert len(await _timed_out_steps(db_session, exec_record.id)) >= 1


@pytest.mark.asyncio
async def test_wallclock_timeout_times_out(db_session: AsyncSession) -> None:
    """A zero wall-clock budget times the run out immediately as TIMED_OUT."""
    exec_record = await _make_execution(db_session)
    adapter = NexusRuntimeAdapter(
        db_session,
        exec_record.id,
        openrouter_client=LoopingLLMClient(),
        settings=_settings(max_steps=5, research_timeout=0),
        search_provider=FakeSearchProvider(),
    )
    res = await adapter.execute_goal("Times out by wall clock")
    assert res["status"] == "timed_out"
    assert len(await _timed_out_steps(db_session, exec_record.id)) >= 1


@pytest.mark.asyncio
async def test_timed_out_distinct_from_failed(db_session: AsyncSession) -> None:
    """A real error is 'failed'; a budget/wall-clock exhaustion is 'timed_out' — distinct."""
    from tests.unit.execution.test_nexus_agent_honesty import FailingLLMClient

    exec_a = await _make_execution(db_session)
    failed = await NexusRuntimeAdapter(
        db_session, exec_a.id, openrouter_client=FailingLLMClient()
    ).execute_goal("fail")
    assert failed["status"] == "failed"

    exec_b = await _make_execution(db_session)
    timed = await NexusRuntimeAdapter(
        db_session,
        exec_b.id,
        openrouter_client=LoopingLLMClient(),
        settings=_settings(max_steps=1),
        search_provider=FakeSearchProvider(),
    ).execute_goal("never finishes")
    assert timed["status"] == "timed_out"


# --------------------------------------------------------------------------- Step 6: resume_goal()


@pytest.mark.asyncio
async def test_resume_continues_from_checkpoint(db_session: AsyncSession) -> None:
    """resume_goal rebuilds the trajectory from steps + checkpoint and continues to completion."""
    exec_record = await _make_approved_execution(db_session)

    # First (partial) run: a 2-step budget that times out, persisting steps + checkpoints.
    first = NexusRuntimeAdapter(
        db_session,
        exec_record.id,
        openrouter_client=LoopingLLMClient(),
        settings=_settings(max_steps=2),
        search_provider=FakeSearchProvider(),
    )
    first_res = await first.execute_goal("Resume")
    assert first_res["status"] == "timed_out"
    prior_steps = len(first.trajectory)
    assert prior_steps >= 2

    # Resume with a finishing client on a fresh adapter for the same execution.
    resumed = NexusRuntimeAdapter(
        db_session, exec_record.id, openrouter_client=FakeLLMClient([_finish()])
    )
    res = await resumed.resume_goal("Resume")
    assert res["status"] == "completed"
    # The reconstructed trajectory carried prior steps forward, then continued.
    assert len(resumed.trajectory) > prior_steps


@pytest.mark.asyncio
async def test_resume_fails_closed_without_prior_steps(db_session: AsyncSession) -> None:
    """resume_goal fails closed when there is no prior agent-step state to resume from."""
    exec_record = await _make_approved_execution(db_session)
    adapter = NexusRuntimeAdapter(
        db_session, exec_record.id, openrouter_client=FakeLLMClient([_finish()])
    )
    with pytest.raises(ExecutionEngineError):
        await adapter.resume_goal("Resume")


@pytest.mark.asyncio
async def test_resume_revalidates_governance(db_session: AsyncSession) -> None:
    """resume_goal re-runs governance — an unapproved execution cannot resume (no bypass)."""
    # Execution WITHOUT an approval, but with prior step + checkpoint state present.
    exec_record = await _make_execution(db_session)
    db_session.add(
        AgentStepRecord(
            execution_id=exec_record.id,
            step_index=0,
            thought="prior",
            tool_name="web_search",
            tool_arguments={"query": "x"},
            tool_result="result",
            status=ExecutionStatus.COMPLETED.value,
            last_heartbeat=datetime.now(UTC),
        )
    )
    db_session.add(
        WorkflowCheckpointRecord(
            workflow_id=exec_record.id,
            step_name="agent_step_0",
            state={"step": {}, "plan": [{"step": 1, "description": "x"}]},
            completed_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    adapter = NexusRuntimeAdapter(
        db_session, exec_record.id, openrouter_client=FakeLLMClient([_finish()])
    )
    with pytest.raises(RepositoryGovernanceError):
        await adapter.resume_goal("Resume")


# --------------------------------------------------------------------------- Step 7: audited run


@pytest.mark.asyncio
async def test_audited_real_run(db_session: AsyncSession) -> None:
    """End-to-end governed Nexus run: governance, tool execution, checkpoints, completion, artifacts."""
    from nexus.memory.models import ExecutionArtifactRecord

    exec_record = await _make_approved_execution(db_session)
    client = FakeLLMClient(
        [
            '["Search the topic", "Report findings"]',  # plan
            _SEARCH,  # tool execution (provider-backed search)
            _finish(),  # completion
            "Audited run synthesis report.",  # summarize()
        ]
    )
    adapter = NexusRuntimeAdapter(
        db_session,
        exec_record.id,
        openrouter_client=client,
        search_provider=FakeSearchProvider(result="AUDITED_PROVIDER_RESULT"),
    )

    # Governance gate (real validation against the approved execution).
    await adapter.validate_goal("Audited run")

    res = await adapter.execute_goal("Audited run")
    await adapter.persist()

    # Completion state
    assert res["status"] == "completed"
    assert res["exit_code"] == 0

    # Tool execution captured (provider-backed search ran)
    steps = (
        await db_session.execute(
            select(AgentStepRecord)
            .where(AgentStepRecord.execution_id == exec_record.id)
            .order_by(AgentStepRecord.step_index)
        )
    ).scalars().all()
    assert any(s.tool_name == "web_search" for s in steps)
    assert any("AUDITED_PROVIDER_RESULT" in (s.tool_result or "") for s in steps)
    assert any(s.tool_name == "finish" for s in steps)

    # Checkpoints captured
    checkpoints = (
        await db_session.execute(
            select(WorkflowCheckpointRecord).where(
                WorkflowCheckpointRecord.workflow_id == exec_record.id
            )
        )
    ).scalars().all()
    assert len(checkpoints) >= 1

    # Audit artifacts captured
    artifacts = (
        await db_session.execute(
            select(ExecutionArtifactRecord).where(
                ExecutionArtifactRecord.execution_id == exec_record.id
            )
        )
    ).scalars().all()
    types_present = {a.artifact_type for a in artifacts}
    assert {"agent_plan", "agent_trajectory", "summary"} <= types_present


# --------------------------------------------------------------------------- Branding: back-compat


def test_registry_resolves_nexus_and_hermes_alias() -> None:
    """The renamed runtime registers as 'nexus'; the legacy 'hermes' id still resolves (alias)."""
    from nexus.execution.runners import runtime_registry
    from nexus.execution.runners.nexus_agent import (
        HermesRuntimeAdapter,
        NexusRuntimeAdapter,
    )

    assert runtime_registry.get_adapter_cls("nexus") is NexusRuntimeAdapter
    # Legacy codename id (and its enum form) resolve to the renamed runtime — no orphaned records.
    assert runtime_registry.get_adapter_cls("hermes") is NexusRuntimeAdapter
    assert runtime_registry.get_adapter_cls("hermes_agent") is NexusRuntimeAdapter
    # The legacy class symbol remains importable for back-compat.
    assert HermesRuntimeAdapter is NexusRuntimeAdapter
