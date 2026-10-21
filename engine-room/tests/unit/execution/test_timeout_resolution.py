"""A-002 tests: runtime execution timeouts honor configuration and the hard limit (v1.0.1).

Validates the shared timeout resolver and that each runtime adapter (Claude, Gemini, Nexus) uses
its ADR-010 configured timeout, clamped by ``hard_limit``. Replaces the v1.0.0 defect where every
runner silently read a non-existent ``research_timeout_seconds`` field and fell back to 300s.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from nexus.config import ExecutionConfig, NexusSettings, SandboxConfig
from nexus.execution.runners.base import resolve_execution_timeout
from nexus.execution.runners.claude import ClaudeRuntimeAdapter
from nexus.execution.runners.gemini import GeminiRuntimeAdapter
from nexus.execution.runners.nexus_agent import NexusRuntimeAdapter
from nexus.memory.models import ExecutionRecord, ExecutionStepRecord, TaskRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Pure resolver unit tests
# ---------------------------------------------------------------------------


def test_resolve_claude_timeout() -> None:
    settings = NexusSettings(execution=ExecutionConfig())
    assert resolve_execution_timeout(settings, "claude_timeout") == 2700


def test_resolve_gemini_timeout() -> None:
    settings = NexusSettings(execution=ExecutionConfig())
    assert resolve_execution_timeout(settings, "gemini_timeout") == 1800


def test_resolve_research_timeout_for_nexus() -> None:
    settings = NexusSettings(execution=ExecutionConfig())
    assert resolve_execution_timeout(settings, "research_timeout") == 900


def test_hard_limit_is_impossible_to_exceed() -> None:
    settings = NexusSettings(execution=ExecutionConfig(claude_timeout=99999, hard_limit=3600))
    assert resolve_execution_timeout(settings, "claude_timeout") == 3600


def test_unknown_field_falls_back_to_default() -> None:
    # The old broken field name must now resolve safely to the default, never crash.
    settings = NexusSettings(execution=ExecutionConfig())
    assert resolve_execution_timeout(settings, "research_timeout_seconds") == 300


def test_none_settings_returns_default() -> None:
    assert resolve_execution_timeout(None, "claude_timeout") == 300


# ---------------------------------------------------------------------------
# Per-runtime behavioral tests (timeout written onto the step record)
# ---------------------------------------------------------------------------


async def _make_exec(db_session: AsyncSession, runner: str) -> ExecutionRecord:
    task = TaskRecord(
        id=uuid.uuid4(),
        title=f"{runner} timeout task",
        description="echo hi",
        status="created",
        priority=1,
    )
    db_session.add(task)
    await db_session.flush()
    exec_record = ExecutionRecord(
        id=uuid.uuid4(),
        task_id=task.id,
        runner=runner,
        repository=".",
    )
    db_session.add(exec_record)
    await db_session.flush()
    return exec_record


async def _step_timeout(db_session: AsyncSession, exec_id: uuid.UUID) -> int:
    res = await db_session.execute(
        select(ExecutionStepRecord).where(ExecutionStepRecord.execution_id == exec_id)
    )
    step = res.scalar_one()
    return int(step.timeout_threshold)


@pytest.mark.asyncio
async def test_claude_execute_uses_claude_timeout(
    db_session: AsyncSession, test_settings: NexusSettings
) -> None:
    exec_record = await _make_exec(db_session, "claude")
    adapter = ClaudeRuntimeAdapter(db_session, exec_record.id, settings=test_settings)
    await adapter.execute("echo hi")
    assert await _step_timeout(db_session, exec_record.id) == test_settings.execution.claude_timeout


@pytest.mark.asyncio
async def test_gemini_execute_uses_gemini_timeout(
    db_session: AsyncSession, test_settings: NexusSettings
) -> None:
    exec_record = await _make_exec(db_session, "gemini")
    adapter = GeminiRuntimeAdapter(db_session, exec_record.id, settings=test_settings)
    await adapter.execute("echo hi")
    assert await _step_timeout(db_session, exec_record.id) == test_settings.execution.gemini_timeout


@pytest.mark.asyncio
async def test_claude_execute_clamps_to_hard_limit(db_session: AsyncSession) -> None:
    settings = NexusSettings(execution=ExecutionConfig(claude_timeout=99999, hard_limit=120))
    exec_record = await _make_exec(db_session, "claude")
    adapter = ClaudeRuntimeAdapter(db_session, exec_record.id, settings=settings)
    await adapter.execute("echo hi")
    assert await _step_timeout(db_session, exec_record.id) == 120


@pytest.mark.asyncio
async def test_nexus_execute_command_uses_research_timeout(
    db_session: AsyncSession, test_settings: NexusSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nexus' execute_command tool must use the configured research_timeout, not a hardcoded 300."""
    exec_record = await _make_exec(db_session, "nexus")
    # S-2: sandbox must be explicitly enabled for execution to resolve a provider (fail-closed
    # default). Provider is irrelevant here since SandboxManager.execute is monkeypatched below.
    test_settings.sandbox = SandboxConfig(enabled=True, provider="mock")
    adapter = NexusRuntimeAdapter(db_session, exec_record.id, settings=test_settings)

    captured: dict[str, int] = {}

    class _FakeProc:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"ok", b""

    async def _fake_execute(
        self: object,
        command: str,
        cwd: str = ".",
        timeout: int = 300,
        correlation_id: object = None,
    ) -> _FakeProc:
        captured["timeout"] = timeout
        return _FakeProc()

    monkeypatch.setattr(
        "nexus.execution.sandbox.manager.SandboxManager.execute", _fake_execute
    )

    await adapter._execute_tool("execute_command", {"command": "echo hi"})
    assert captured["timeout"] == test_settings.execution.research_timeout
