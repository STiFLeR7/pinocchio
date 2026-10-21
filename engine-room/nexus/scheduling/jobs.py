"""Scheduler job wrappers (AP-103).

Each job is a *thin* wrapper that contains NO business logic: it opens a session, constructs an
existing service, and invokes a single service method. The audited runner (``run_scheduled_job``)
emits the SCHEDULER_JOB_* lifecycle audit events and a duration metric. Jobs never import ORM
models directly — services own all model access (service-boundary constraint).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from nexus.core.events import NexusEvent
from nexus.core.metrics import record_metric, run_aggregation_and_retention
from nexus.core.types import EventType
from nexus.database import get_session
from nexus.memory.service import MemoryService


class JobSkippedError(Exception):
    """Raised by a job body to signal an intentional no-op (audited as SCHEDULER_JOB_SKIPPED)."""


async def _audit(
    session_factory: Any,
    job_id: str,
    event_type: EventType,
    correlation_id: uuid.UUID,
    data: dict[str, Any],
) -> None:
    """Write a scheduler lifecycle event to the immutable audit log (component='scheduler')."""
    async with get_session(session_factory) as session:
        memory_service = MemoryService(session)
        event = NexusEvent(
            event_type=event_type,
            entity_type="scheduler_job",
            entity_id=None,
            data={"job_id": job_id, **data},
            correlation_id=correlation_id,
            source="scheduler",
        )
        await memory_service.log_event(event, enqueue_outbox=False)


async def run_scheduled_job(
    job_id: str,
    session_factory: Any,
    func: Callable[[], Awaitable[Any]],
) -> None:
    """Run a job body with start/complete/fail/skip auditing and a duration metric.

    Never raises — a job failure is contained and audited so it cannot crash the scheduler or
    other jobs (failure-isolation requirement).
    """
    correlation_id = uuid.uuid4()
    await _audit(session_factory, job_id, EventType.SCHEDULER_JOB_STARTED, correlation_id, {})
    start = time.monotonic()
    try:
        result = await func()
    except JobSkippedError as skip:
        await _audit(
            session_factory,
            job_id,
            EventType.SCHEDULER_JOB_SKIPPED,
            correlation_id,
            {"reason": str(skip)},
        )
        return
    except Exception as exc:
        # Jobs must never propagate to the scheduler — contain and audit every failure.
        duration_ms = (time.monotonic() - start) * 1000.0
        record_metric("scheduler_job_failed", 1.0)
        await _audit(
            session_factory,
            job_id,
            EventType.SCHEDULER_JOB_FAILED,
            correlation_id,
            {"error": str(exc), "duration_ms": round(duration_ms, 2)},
        )
        return

    duration_ms = (time.monotonic() - start) * 1000.0
    record_metric("scheduler_job_duration_ms", duration_ms)
    data: dict[str, Any] = {"duration_ms": round(duration_ms, 2)}
    if isinstance(result, dict):
        data["result"] = result
    await _audit(session_factory, job_id, EventType.SCHEDULER_JOB_COMPLETED, correlation_id, data)


# ---------------------------------------------------------------------------
# Job bodies — invoke existing services only
# ---------------------------------------------------------------------------


async def run_research_job(session_factory: Any, openrouter_client: Any, settings: Any) -> None:
    """J1 — crawl configured research feeds via ResearchService, then push the high-importance
    new findings to the proactive Priority Feed. Skips if no feeds configured.

    Composition only: ResearchService persists findings (Discord-agnostic), then
    PriorityFeedService routes the high-signal subset via the channel harness onto the outbox.
    """
    feeds = dict(settings.scheduling.research_feeds or {})
    if not feeds:
        raise JobSkippedError("no research feeds configured")
    from nexus.intelligence.feed import PriorityFeedService
    from nexus.intelligence.research import ResearchService

    async with get_session(session_factory) as session:
        memory_service = MemoryService(session)
        service = ResearchService(session, openrouter_client, memory_service)
        persisted_ids = await service.execute_research_run(feeds)

        if settings.scheduling.priority_feed_enabled and persisted_ids:
            feed = PriorityFeedService(session, settings)
            await feed.dispatch_new_findings(persisted_ids)


async def run_briefing_job(
    session_factory: Any, discord_service: Any, email_service: Any
) -> None:
    """J2 — generate and dispatch the daily briefing via BriefingService."""
    from nexus.intelligence.briefing import BriefingService

    async with get_session(session_factory) as session:
        memory_service = MemoryService(session)
        service = BriefingService(session, memory_service, discord_service, email_service)
        await service.generate_and_dispatch_briefing()


async def run_approval_expiry_job(
    session_factory: Any, owner_ids: Any, event_gateway: Any
) -> None:
    """J3 — sweep expired approvals via ApprovalService."""
    from nexus.approvals.service import ApprovalService

    async with get_session(session_factory) as session:
        memory_service = MemoryService(session)
        service = ApprovalService(session, memory_service, owner_ids, event_gateway)
        await service.sweep_expired_approvals()


async def run_metrics_aggregation_job(session_factory: Any) -> None:
    """J4 — roll raw metrics into hourly aggregates and apply retention."""
    async with get_session(session_factory) as session:
        await run_aggregation_and_retention(session)


async def run_outbox_health_job(session_factory: Any) -> dict[str, int]:
    """J5 — read-only outbox health snapshot; records metrics. No mutation/repair/retry."""
    from nexus.gateway.outbox_health import OutboxHealthService

    async with get_session(session_factory) as session:
        snapshot = await OutboxHealthService(session).snapshot()
    for key, value in snapshot.items():
        record_metric(f"outbox_{key}", float(value))
    return snapshot


async def run_checkpoint_health_job(
    session_factory: Any, stale_minutes: int = 60
) -> dict[str, int]:
    """J6 — read-only checkpoint/heartbeat health snapshot; records metrics. No mutation/cleanup."""
    from nexus.memory.checkpoint_health import CheckpointHealthService

    async with get_session(session_factory) as session:
        snapshot = await CheckpointHealthService(session).snapshot(stale_minutes=stale_minutes)
    for key, value in snapshot.items():
        record_metric(f"checkpoint_{key}", float(value))
    return snapshot
