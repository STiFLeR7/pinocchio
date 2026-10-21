"""Scheduler foundation (AP-103).

Provides a replaceable ``SchedulerPort`` abstraction with an APScheduler-backed implementation, and
``build_scheduler`` which registers the enabled jobs from configuration. The scheduler only wires
jobs (declared in ``nexus.scheduling.jobs``) to triggers — it contains no business logic and never
imports ORM models.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

import structlog

from nexus.scheduling import jobs

logger = structlog.get_logger("nexus.scheduling.scheduler")


@runtime_checkable
class SchedulerPort(Protocol):
    """Replaceable scheduler contract (keeps the engine swappable for future distributed use)."""

    @property
    def job_ids(self) -> list[str]:
        """Return the IDs of currently-registered jobs."""
        ...

    def start(self) -> None:
        """Start firing jobs (requires a running event loop)."""
        ...

    def shutdown(self) -> None:
        """Stop the scheduler without waiting for in-flight jobs."""
        ...


class APSchedulerAdapter:
    """``SchedulerPort`` implementation backed by APScheduler's AsyncIOScheduler."""

    def __init__(self, timezone: str = "UTC") -> None:
        """Create the underlying AsyncIOScheduler bound to the given timezone."""
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        self._scheduler = AsyncIOScheduler(timezone=timezone)

    def add_interval_job(
        self,
        job_id: str,
        func: Callable[[], Awaitable[None]],
        *,
        minutes: int | None = None,
        hours: int | None = None,
    ) -> None:
        """Register an interval-triggered job (coalesced, single-instance, restart-safe)."""
        from apscheduler.triggers.interval import IntervalTrigger

        kwargs: dict[str, int] = {}
        if minutes is not None:
            kwargs["minutes"] = minutes
        if hours is not None:
            kwargs["hours"] = hours
        self._scheduler.add_job(
            func,
            IntervalTrigger(**kwargs),
            id=job_id,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=300,
            replace_existing=True,
        )

    def add_cron_job(
        self,
        job_id: str,
        func: Callable[[], Awaitable[None]],
        *,
        hour: int,
        minute: int,
        timezone: str | None = None,
    ) -> None:
        """Register a cron-triggered job at a fixed time-of-day."""
        from apscheduler.triggers.cron import CronTrigger

        trigger = CronTrigger(hour=hour, minute=minute, timezone=timezone)
        self._scheduler.add_job(
            func,
            trigger,
            id=job_id,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=300,
            replace_existing=True,
        )

    @property
    def job_ids(self) -> list[str]:
        """Return IDs of registered (including pending) jobs."""
        return [str(job.id) for job in self._scheduler.get_jobs()]

    def start(self) -> None:
        """Start the scheduler on the current event loop."""
        self._scheduler.start()

    def shutdown(self) -> None:
        """Shut the scheduler down without blocking on in-flight jobs."""
        self._scheduler.shutdown(wait=False)


def build_scheduler(
    settings: Any,
    session_factory: Any,
    *,
    openrouter_client: Any,
    discord_service: Any,
    email_service: Any,
    owner_ids: Any,
    event_gateway: Any,
) -> APSchedulerAdapter | None:
    """Build an APScheduler adapter with the enabled jobs registered (NOT started).

    Returns ``None`` when scheduling is globally disabled. Each registered job is wrapped by
    ``run_scheduled_job`` so every fire is audited and isolated.
    """
    sc = settings.scheduling
    if not sc.enabled:
        return None

    adapter = APSchedulerAdapter(timezone=sc.timezone)

    def _entry(job_id: str, body: Callable[[], Awaitable[Any]]) -> Callable[[], Awaitable[None]]:
        async def _run() -> None:
            await jobs.run_scheduled_job(job_id, session_factory, body)

        return _run

    if sc.research_enabled:
        adapter.add_interval_job(
            "research_collection",
            _entry(
                "research_collection",
                lambda: jobs.run_research_job(session_factory, openrouter_client, settings),
            ),
            hours=sc.research_interval_hours,
        )

    if sc.briefing_enabled:
        adapter.add_cron_job(
            "daily_briefing",
            _entry(
                "daily_briefing",
                lambda: jobs.run_briefing_job(session_factory, discord_service, email_service),
            ),
            hour=sc.briefing_hour,
            minute=sc.briefing_minute,
            timezone=sc.timezone,
        )

    if sc.approval_sweep_enabled:
        adapter.add_interval_job(
            "approval_expiration_sweep",
            _entry(
                "approval_expiration_sweep",
                lambda: jobs.run_approval_expiry_job(session_factory, owner_ids, event_gateway),
            ),
            minutes=sc.approval_sweep_interval_minutes,
        )

    if sc.metrics_aggregation_enabled:
        adapter.add_interval_job(
            "metrics_aggregation",
            _entry("metrics_aggregation", lambda: jobs.run_metrics_aggregation_job(session_factory)),
            minutes=sc.metrics_aggregation_interval_minutes,
        )

    if sc.outbox_health_enabled:
        adapter.add_interval_job(
            "outbox_health",
            _entry("outbox_health", lambda: jobs.run_outbox_health_job(session_factory)),
            minutes=sc.outbox_health_interval_minutes,
        )

    if sc.checkpoint_health_enabled:
        adapter.add_interval_job(
            "checkpoint_health",
            _entry(
                "checkpoint_health",
                lambda: jobs.run_checkpoint_health_job(
                    session_factory, sc.checkpoint_stale_minutes
                ),
            ),
            minutes=sc.checkpoint_health_interval_minutes,
        )

    return adapter
