"""H-2 (P0) — Nexus honesty tests: structured tool-calls, SearchProvider, goal-derived
planning, truthful exit status, and absence of production mock paths.

These tests drive the Prototype -> Experimental promotion. They use *injected* fakes via the
existing constructor seam (no in-module ``unittest.mock``), so green tests evidence the real
decision/search/plan/exit-status paths — not the mock branch.
"""

from __future__ import annotations

import inspect
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.core.types import ExecutionStatus
from nexus.execution.runners.nexus_agent import NexusRuntimeAdapter
from nexus.memory.models import AgentStepRecord, ExecutionRecord, TaskRecord

# --------------------------------------------------------------------------- fakes (injected)


class FakeLLMClient:
    """Injected LLM client returning scripted completions in order (no AsyncMock)."""

    def __init__(self, completions: list[str]):
        self._completions = list(completions)
        self.calls: list[str] = []

    async def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        if self._completions:
            return self._completions.pop(0)
        return '{"thought": "done", "tool_name": "finish", "tool_arguments": {}}'


class FailingLLMClient:
    """Injected LLM client whose completion always raises (drives the FAILED path)."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        raise RuntimeError("model transport failure")


class FakeSearchProvider:
    """Injected SearchProvider test double returning a deterministic result."""

    def __init__(self, result: str = "FAKE_SEARCH_RESULT") -> None:
        self.result = result
        self.queries: list[str] = []

    async def search(self, query: str) -> str:
        self.queries.append(query)
        return self.result


# --------------------------------------------------------------------------- helpers


async def _make_execution(db_session: AsyncSession) -> ExecutionRecord:
    task = TaskRecord(
        id=uuid.uuid4(),
        title="Honesty Task",
        description="goal:Honest run",
        status="created",
        priority=2,
    )
    db_session.add(task)
    await db_session.flush()
    exec_record = ExecutionRecord(
        id=uuid.uuid4(), task_id=task.id, runner="nexus", repository="."
    )
    db_session.add(exec_record)
    await db_session.flush()
    return exec_record


def _finish(thought: str = "done") -> str:
    return f'{{"thought": "{thought}", "tool_name": "finish", "tool_arguments": {{}}}}'


# --------------------------------------------------------------------------- P0-1 mock removal


def test_no_unittest_mock_import_in_runtime() -> None:
    """The Nexus runtime module must not import unittest.mock (no prod test scaffolding)."""
    from nexus.execution.runners import nexus_agent as nexus_agent_module

    src = inspect.getsource(nexus_agent_module)
    assert "unittest.mock" not in src
    assert "AsyncMock" not in src
    assert "is_mocked" not in src


def test_no_canned_search_literal_in_runtime() -> None:
    """The canned MCP search text and decorative plan literal must be gone from the runtime."""
    from nexus.execution.runners import nexus_agent as nexus_agent_module

    src = inspect.getsource(nexus_agent_module)
    assert "Model Context Protocol (MCP) is widely adopted" not in src
    assert "Search web for MCP ecosystem developments" not in src


@pytest.mark.asyncio
async def test_execute_uses_injected_client_real_branch(db_session: AsyncSession) -> None:
    """execute_goal must drive the loop via the injected client (real branch), not a mock branch."""
    exec_record = await _make_execution(db_session)
    client = FakeLLMClient(['["plan a"]', _finish()])
    adapter = NexusRuntimeAdapter(
        db_session, exec_record.id, openrouter_client=client
    )
    await adapter.execute_goal("Do the thing")
    assert client.calls  # the injected client was actually used


# --------------------------------------------------------------------------- P0-2 structured calls


def test_parse_valid_structured_toolcall() -> None:
    from nexus.execution.runners.nexus_agent_tools import parse_tool_call

    call = parse_tool_call(
        '{"thought": "t", "tool_name": "web_search", "tool_arguments": {"query": "x"}}'
    )
    assert call.tool_name == "web_search"
    assert call.tool_arguments == {"query": "x"}


def test_parse_toolcall_with_code_fence() -> None:
    from nexus.execution.runners.nexus_agent_tools import parse_tool_call

    call = parse_tool_call('```json\n{"thought": "", "tool_name": "finish"}\n```')
    assert call.tool_name == "finish"


def test_parse_malformed_toolcall_raises() -> None:
    from nexus.execution.runners.nexus_agent_tools import ToolCallParseError, parse_tool_call

    with pytest.raises(ToolCallParseError):
        parse_tool_call("this is not json at all")


def test_parse_unknown_tool_raises() -> None:
    from nexus.execution.runners.nexus_agent_tools import ToolCallParseError, parse_tool_call

    with pytest.raises(ToolCallParseError):
        parse_tool_call('{"thought": "", "tool_name": "rm_rf_root", "tool_arguments": {}}')


@pytest.mark.asyncio
async def test_malformed_call_fails_not_silent_finish(db_session: AsyncSession) -> None:
    """A malformed tool call must produce a FAILED outcome, never a silent success."""
    exec_record = await _make_execution(db_session)
    client = FakeLLMClient(['["plan"]', "garbage not-json output"])
    adapter = NexusRuntimeAdapter(db_session, exec_record.id, openrouter_client=client)
    res = await adapter.execute_goal("Do the thing")
    assert res["exit_code"] != 0
    assert res["status"] == "failed"


# --------------------------------------------------------------------------- P0-3 goal-derived plan


@pytest.mark.asyncio
async def test_plan_is_goal_derived_not_literal(db_session: AsyncSession) -> None:
    """The plan must come from the model/goal, not the old hardcoded MCP literal."""
    exec_record = await _make_execution(db_session)
    client = FakeLLMClient(['["Investigate the widget subsystem"]', _finish()])
    adapter = NexusRuntimeAdapter(db_session, exec_record.id, openrouter_client=client)
    await adapter.execute_goal("Investigate widgets")
    descriptions = " ".join(str(s.get("description", "")) for s in adapter.plan)
    assert "Investigate the widget subsystem" in descriptions
    assert "MCP ecosystem developments" not in descriptions


@pytest.mark.asyncio
async def test_plan_without_client_is_goal_derived_fallback(db_session: AsyncSession) -> None:
    """With no model client, the plan still derives from the goal text (no MCP literal)."""
    exec_record = await _make_execution(db_session)
    adapter = NexusRuntimeAdapter(db_session, exec_record.id)
    await adapter.execute_goal("Unique-Goal-Token-XYZ")
    descriptions = " ".join(str(s.get("description", "")) for s in adapter.plan)
    assert "Unique-Goal-Token-XYZ" in descriptions


# --------------------------------------------------------------------------- P0-5 SearchProvider


@pytest.mark.asyncio
async def test_web_search_uses_injected_provider(db_session: AsyncSession) -> None:
    exec_record = await _make_execution(db_session)
    provider = FakeSearchProvider(result="PROVIDER_BACKED_RESULT")
    adapter = NexusRuntimeAdapter(
        db_session, exec_record.id, search_provider=provider
    )
    result = await adapter._execute_tool("web_search", {"query": "widgets"})
    assert result == "PROVIDER_BACKED_RESULT"
    assert provider.queries == ["widgets"]


@pytest.mark.asyncio
async def test_web_search_without_provider_is_honest_error(db_session: AsyncSession) -> None:
    """No provider configured -> honest error, never canned results."""
    exec_record = await _make_execution(db_session)
    adapter = NexusRuntimeAdapter(db_session, exec_record.id)
    result = await adapter._execute_tool("web_search", {"query": "widgets"})
    assert "MCP" not in result
    assert "error" in result.lower()


def test_search_provider_is_abstract() -> None:
    from nexus.execution.runners.search_provider import SearchProvider

    with pytest.raises(TypeError):
        SearchProvider()  # type: ignore[abstract]


# --------------------------------------------------------------------------- P0-4 exit status


@pytest.mark.asyncio
async def test_success_yields_zero_exit(db_session: AsyncSession) -> None:
    exec_record = await _make_execution(db_session)
    client = FakeLLMClient(['["plan"]', _finish()])
    adapter = NexusRuntimeAdapter(db_session, exec_record.id, openrouter_client=client)
    res = await adapter.execute_goal("Finish cleanly")
    assert res["exit_code"] == 0
    assert res["status"] == "completed"


@pytest.mark.asyncio
async def test_failure_yields_nonzero_exit(db_session: AsyncSession) -> None:
    exec_record = await _make_execution(db_session)
    adapter = NexusRuntimeAdapter(
        db_session, exec_record.id, openrouter_client=FailingLLMClient()
    )
    res = await adapter.execute_goal("This will fail")
    assert res["exit_code"] != 0
    assert res["status"] == "failed"


@pytest.mark.asyncio
async def test_failed_step_persisted_with_truthful_status(db_session: AsyncSession) -> None:
    exec_record = await _make_execution(db_session)
    adapter = NexusRuntimeAdapter(
        db_session, exec_record.id, openrouter_client=FailingLLMClient()
    )
    await adapter.execute_goal("This will fail")
    step_stmt = select(AgentStepRecord).where(
        AgentStepRecord.execution_id == exec_record.id
    )
    steps = (await db_session.execute(step_stmt)).scalars().all()
    assert any(s.status == ExecutionStatus.FAILED.value for s in steps)
