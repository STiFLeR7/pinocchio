"""AP-103B tests: Scheduler Foundation (Nexus v1.0.1 Alignment).

Covers: new scheduler EventTypes, SchedulingConfig cadences, read-only health services
(J5/J6), the audited job runner lifecycle, per-job service invocation (no business logic in jobs),
and scheduler registration honoring config toggles. No real timers are started in these tests.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from nexus.config import (
    DiscordConfig,
    ExecutionConfig,
    NexusSettings,
    SchedulingConfig,
)
from nexus.core.types import EventType
from nexus.memory.models import AuditLogRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


@pytest.fixture
def session_factory(db_engine: AsyncEngine) -> async_sessionmaker:  # type: ignore[type-arg]
    """A real session factory (separate sessions commit to the shared test DB)."""
    return async_sessionmaker(db_engine, expire_on_commit=False)


async def _audit_events(session_factory: async_sessionmaker, job_id: str) -> list[str]:  # type: ignore[type-arg]
    from nexus.database import get_session

    async with get_session(session_factory) as session:
        res = await session.execute(
            select(AuditLogRecord).where(AuditLogRecord.entity_type == "scheduler_job")
        )
        return [r.event_type for r in res.scalars().all() if (r.data or {}).get("job_id") == job_id]


# ---------------------------------------------------------------------------
# Event types + config
# ---------------------------------------------------------------------------


def test_scheduler_event_types_exist() -> None:
    assert EventType.SCHEDULER_JOB_STARTED.value == "scheduler.job.started"
    assert EventType.SCHEDULER_JOB_COMPLETED.value == "scheduler.job.completed"
    assert EventType.SCHEDULER_JOB_FAILED.value == "scheduler.job.failed"
    assert EventType.SCHEDULER_JOB_SKIPPED.value == "scheduler.job.skipped"


def test_scheduling_config_cadence_defaults() -> None:
    sc = SchedulingConfig()
    assert sc.enabled is True
    assert sc.timezone == "Asia/Kolkata"
    assert sc.research_interval_hours == 2
    assert (sc.briefing_hour, sc.briefing_minute) == (8, 0)
    assert sc.approval_sweep_interval_minutes == 15
    assert sc.metrics_aggregation_interval_minutes == 5
    assert sc.outbox_health_interval_minutes == 10
    assert sc.checkpoint_health_interval_minutes == 30


def test_scheduling_config_attached_to_settings() -> None:
    settings = NexusSettings(discord=DiscordConfig(owner_ids=[1]))
    assert isinstance(settings.scheduling, SchedulingConfig)


# ---------------------------------------------------------------------------
# Read-only health services (J5 / J6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_outbox_health_service_snapshot_readonly(db_session: AsyncSession) -> None:
    from nexus.gateway.outbox_health import OutboxHealthService
    from nexus.memory.models import SystemEventRecord, SystemOutboxRecord

    db_session.add(
        SystemOutboxRecord(channel="discord", payload={}, status="pending", source_type="briefing")
    )
    db_session.add(
        SystemOutboxRecord(
            channel="email", payload={}, status="dead_letter", source_type="briefing"
        )
    )
    db_session.add(SystemEventRecord(event_type="task.created", payload={}, status="pending"))
    await db_session.flush()

    before = (
        await db_session.execute(select(SystemOutboxRecord))
    ).scalars().all()

    snap = await OutboxHealthService(db_session).snapshot()

    assert snap["dead_letter"] >= 1
    assert snap["pending"] >= 1
    assert snap["events_pending"] >= 1

    # Read-only: snapshot must not mutate, add, or delete rows.
    after = (await db_session.execute(select(SystemOutboxRecord))).scalars().all()
    assert len(after) == len(before)


@pytest.mark.asyncio
async def test_checkpoint_health_service_snapshot_readonly(db_session: AsyncSession) -> None:
    from nexus.gateway.outbox_health import OutboxHealthService  # noqa: F401 (import parity)
    from nexus.memory.checkpoint_health import CheckpointHealthService
    from nexus.memory.models import ExecutionRecord, TaskRecord, WorkflowCheckpointRecord

    task = TaskRecord(id=uuid.uuid4(), title="t", status="active", priority=1)
    db_session.add(task)
    await db_session.flush()

    # Stale, still-running execution (old heartbeat, not completed)
    db_session.add(
        ExecutionRecord(
            id=uuid.uuid4(),
            task_id=task.id,
            runner="claude",
            repository=".",
            last_heartbeat=datetime.now(UTC) - timedelta(hours=5),
            completed_at=None,
        )
    )
    # Fresh execution (recent heartbeat)
    db_session.add(
        ExecutionRecord(
            id=uuid.uuid4(),
            task_id=task.id,
            runner="claude",
            repository=".",
            last_heartbeat=datetime.now(UTC),
            completed_at=None,
        )
    )
    db_session.add(
        WorkflowCheckpointRecord(workflow_id=uuid.uuid4(), step_name="s", state={})
    )
    await db_session.flush()

    snap = await CheckpointHealthService(db_session).snapshot(stale_minutes=60)
    assert snap["stale_executions"] >= 1
    assert snap["total_checkpoints"] >= 1


# ---------------------------------------------------------------------------
# Audited job runner lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_scheduled_job_audits_started_and_completed(
    session_factory: async_sessionmaker,  # type: ignore[type-arg]
) -> None:
    from nexus.scheduling.jobs import run_scheduled_job

    async def ok() -> dict[str, int]:
        return {"items": 3}

    await run_scheduled_job("unit_ok", session_factory, ok)
    events = await _audit_events(session_factory, "unit_ok")
    assert EventType.SCHEDULER_JOB_STARTED.value in events
    assert EventType.SCHEDULER_JOB_COMPLETED.value in events


@pytest.mark.asyncio
async def test_run_scheduled_job_audits_failure(
    session_factory: async_sessionmaker,  # type: ignore[type-arg]
) -> None:
    from nexus.scheduling.jobs import run_scheduled_job

    async def boom() -> None:
        raise RuntimeError("kaboom")

    await run_scheduled_job("unit_fail", session_factory, boom)  # must NOT raise
    events = await _audit_events(session_factory, "unit_fail")
    assert EventType.SCHEDULER_JOB_FAILED.value in events


@pytest.mark.asyncio
async def test_run_scheduled_job_audits_skip(
    session_factory: async_sessionmaker,  # type: ignore[type-arg]
) -> None:
    from nexus.scheduling.jobs import JobSkippedError, run_scheduled_job

    async def skip() -> None:
        raise JobSkippedError("nothing to do")

    await run_scheduled_job("unit_skip", session_factory, skip)
    events = await _audit_events(session_factory, "unit_skip")
    assert EventType.SCHEDULER_JOB_SKIPPED.value in events


# ---------------------------------------------------------------------------
# Per-job service invocation (jobs contain no business logic)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_research_job_skips_without_feeds(
    session_factory: async_sessionmaker,  # type: ignore[type-arg]
) -> None:
    from nexus.scheduling.jobs import JobSkippedError, run_research_job

    settings = NexusSettings(scheduling=SchedulingConfig(research_feeds={}))
    with pytest.raises(JobSkippedError):
        await run_research_job(session_factory, None, settings)


@pytest.mark.asyncio
async def test_research_job_invokes_service(
    session_factory: async_sessionmaker,  # type: ignore[type-arg]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nexus.intelligence.research import ResearchService
    from nexus.scheduling.jobs import run_research_job

    captured: dict[str, object] = {}

    async def fake(self: object, feeds: dict[str, str], workflow_id: object = None) -> list:
        captured["feeds"] = feeds
        return []

    monkeypatch.setattr(ResearchService, "execute_research_run", fake)
    settings = NexusSettings(scheduling=SchedulingConfig(research_feeds={"ai": "http://x/rss"}))
    await run_research_job(session_factory, None, settings)
    assert captured["feeds"] == {"ai": "http://x/rss"}


@pytest.mark.asyncio
async def test_approval_expiry_job_invokes_service(
    session_factory: async_sessionmaker,  # type: ignore[type-arg]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nexus.approvals.service import ApprovalService
    from nexus.scheduling.jobs import run_approval_expiry_job

    called = {"n": 0}

    async def fake_sweep(self: object) -> list:
        called["n"] += 1
        return []

    monkeypatch.setattr(ApprovalService, "sweep_expired_approvals", fake_sweep)
    await run_approval_expiry_job(session_factory, owner_ids=[123], event_gateway=None)
    assert called["n"] == 1


@pytest.mark.asyncio
async def test_metrics_job_invokes_aggregation(
    session_factory: async_sessionmaker,  # type: ignore[type-arg]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import nexus.scheduling.jobs as jobs_mod

    called = {"n": 0}

    async def fake_agg(session: object, baseline_ver: str = "x") -> None:
        called["n"] += 1

    monkeypatch.setattr(jobs_mod, "run_aggregation_and_retention", fake_agg)
    await jobs_mod.run_metrics_aggregation_job(session_factory)
    assert called["n"] == 1


@pytest.mark.asyncio
async def test_outbox_health_job_records_metrics(
    session_factory: async_sessionmaker,  # type: ignore[type-arg]
) -> None:
    from nexus.scheduling.jobs import run_outbox_health_job

    snap = await run_outbox_health_job(session_factory)
    assert isinstance(snap, dict)
    assert "dead_letter" in snap


@pytest.mark.asyncio
async def test_checkpoint_health_job_returns_snapshot(
    session_factory: async_sessionmaker,  # type: ignore[type-arg]
) -> None:
    from nexus.scheduling.jobs import run_checkpoint_health_job

    snap = await run_checkpoint_health_job(session_factory, stale_minutes=60)
    assert isinstance(snap, dict)
    assert "stale_executions" in snap


# ---------------------------------------------------------------------------
# Scheduler registration honors config toggles (no timers started)
# ---------------------------------------------------------------------------


def test_build_scheduler_registers_enabled_jobs() -> None:
    from nexus.scheduling.scheduler import build_scheduler

    settings = NexusSettings(
        discord=DiscordConfig(owner_ids=[1]),
        execution=ExecutionConfig(),
        scheduling=SchedulingConfig(research_feeds={"ai": "http://x"}),
    )
    scheduler = build_scheduler(
        settings,
        session_factory=None,
        openrouter_client=None,
        discord_service=None,
        email_service=None,
        owner_ids=[1],
        event_gateway=None,
    )
    assert scheduler is not None
    ids = set(scheduler.job_ids)
    assert {
        "research_collection",
        "daily_briefing",
        "approval_expiration_sweep",
        "metrics_aggregation",
        "outbox_health",
        "checkpoint_health",
    } <= ids


def test_build_scheduler_omits_disabled_jobs() -> None:
    from nexus.scheduling.scheduler import build_scheduler

    settings = NexusSettings(
        discord=DiscordConfig(owner_ids=[1]),
        scheduling=SchedulingConfig(
            research_enabled=False,
            outbox_health_enabled=False,
        ),
    )
    scheduler = build_scheduler(
        settings,
        session_factory=None,
        openrouter_client=None,
        discord_service=None,
        email_service=None,
        owner_ids=[1],
        event_gateway=None,
    )
    assert scheduler is not None
    ids = set(scheduler.job_ids)
    assert "research_collection" not in ids
    assert "outbox_health" not in ids
    assert "daily_briefing" in ids


def test_build_scheduler_disabled_globally_returns_none() -> None:
    from nexus.scheduling.scheduler import build_scheduler

    settings = NexusSettings(scheduling=SchedulingConfig(enabled=False))
    scheduler = build_scheduler(
        settings,
        session_factory=None,
        openrouter_client=None,
        discord_service=None,
        email_service=None,
        owner_ids=[1],
        event_gateway=None,
    )
    assert scheduler is None
