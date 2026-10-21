"""E2E tests for the wired chat executors: create_task, run_research, show_status.

Drives the full pipeline (Planner → Validator → Executor) with a scripted fake LLM and a REAL
database session factory, then asserts the side effects landed in the database — no Discord, no
network, no mocks of the domain services.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from nexus.communication.chat import ChatActionType, ChatService
from nexus.database import get_session
from nexus.memory.models import ResearchFindingRecord, TaskRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


class FakeLLM:
    """Returns one scripted JSON plan."""

    def __init__(self, response: str) -> None:
        self._response = response

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        return self._response


def _factory(db_engine: AsyncEngine) -> async_sessionmaker[Any]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


def _service(db_engine: AsyncEngine, response: str) -> ChatService:
    return ChatService.build(
        llm_client=FakeLLM(response),
        session_factory=_factory(db_engine),
        event_gateway=None,
    )


async def test_owner_create_task_persists_and_queues(db_engine: AsyncEngine) -> None:
    svc = _service(
        db_engine,
        '{"type": "create_task", "title": "Ship the feed", "description": "wire it", "priority": 1}',
    )
    resp = await svc.handle_text(conversation_id="c1", text="create a task to ship the feed", is_owner=True)

    assert resp.action_type is ChatActionType.CREATE_TASK
    assert resp.executed is True
    assert any(p.card and p.card["verification"] == "queued" for p in resp.posts)

    factory = _factory(db_engine)
    async with factory() as session:
        rows = (await session.execute(select(TaskRecord).where(TaskRecord.title == "Ship the feed"))).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "queued"
    assert rows[0].priority == 1


async def test_non_owner_create_task_denied_and_persists_nothing(db_engine: AsyncEngine) -> None:
    svc = _service(db_engine, '{"type": "create_task", "title": "sneaky", "priority": 2}')
    resp = await svc.handle_text(conversation_id="c1", text="make a task", is_owner=False)

    assert resp.executed is False
    assert "owner" in (resp.reply or "").lower()
    factory = _factory(db_engine)
    async with factory() as session:
        rows = (await session.execute(select(TaskRecord).where(TaskRecord.title == "sneaky"))).scalars().all()
    assert rows == []


async def test_create_task_missing_title_fails_schema(db_engine: AsyncEngine) -> None:
    svc = _service(db_engine, '{"type": "create_task", "description": "no title here"}')
    resp = await svc.handle_text(conversation_id="c1", text="create a task", is_owner=True)

    assert resp.executed is False
    assert "missing" in (resp.reply or "").lower()


async def test_owner_run_research_queues_task_for_agent(db_engine: AsyncEngine) -> None:
    svc = _service(db_engine, '{"type": "run_research", "topic": "RISC-V accelerators"}')
    resp = await svc.handle_text(conversation_id="c1", text="research risc-v accelerators", is_owner=True)

    assert resp.action_type is ChatActionType.RUN_RESEARCH
    assert resp.executed is True

    factory = _factory(db_engine)
    async with factory() as session:
        row = (
            (await session.execute(select(TaskRecord).where(TaskRecord.title == "Research: RISC-V accelerators")))
            .scalars()
            .one()
        )
    assert row.status == "queued"
    assert row.runtime_id == "nexus"  # routed to the research-capable agent
    assert row.description == "RISC-V accelerators"


async def test_show_status_reports_counts(db_engine: AsyncEngine) -> None:
    # Seed one open task and one recent finding so the status reflects real DB state.
    factory = _factory(db_engine)
    async with get_session(factory) as session:
        session.add(TaskRecord(id=uuid.uuid4(), title="open one", status="queued", priority=2))
        session.add(
            ResearchFindingRecord(
                id=uuid.uuid4(), source="hn", title="a finding", url="https://x.test/1",
                summary="s", tags=["ai"], importance_score=5,
            )
        )

    svc = _service(db_engine, '{"type": "show_status"}')
    resp = await svc.handle_text(conversation_id="c1", text="status?", is_owner=False)

    assert resp.action_type is ChatActionType.SHOW_STATUS
    assert resp.executed is True
    assert "status" in (resp.reply or "").lower()
    assert "Open tasks: `1`" in (resp.reply or "")
    assert "Research findings (24h): `1`" in (resp.reply or "")
    assert any(p.card and p.card["tools"] == "show_status" for p in resp.posts)
