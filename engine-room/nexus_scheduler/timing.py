"""Deterministic schedule timing — occurrence computation as a pure function of injected time.

The Scheduler never reads a wall clock: it is driven by an injected ``now`` (an ISO-8601 string), and every
occurrence is a pure function of the schedule's timing spec and that ``now``. ``datetime.fromisoformat`` +
``timedelta`` do the arithmetic on given data only — no non-determinism — so replay and restart reproduce
the identical occurrence set. Occurrence indices are stable (0-based from the anchor), which is what keys a
dispatch on the durable log and prevents duplicate dispatch across a restart.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from nexus_scheduler.model import CRON_ALIASES, ScheduleKind, ScheduleTrigger

# Recurring backstop: never generate more than this many occurrences in one due-check (no silent
# unbounded loop). A real scheduler ticks often, so the per-tick window is small; the cap is a safety net.
SAFETY_CAP = 1000


def effective_interval(trigger: ScheduleTrigger) -> int | None:
    """The recurrence interval in seconds for INTERVAL/CRON (a cron alias maps to a fixed interval)."""
    if trigger.kind is ScheduleKind.INTERVAL:
        return trigger.interval_seconds
    if trigger.kind is ScheduleKind.CRON:
        return CRON_ALIASES.get(trigger.cron or "", trigger.interval_seconds)
    return None


def due_occurrences(trigger: ScheduleTrigger, now: str) -> tuple[tuple[int, str], ...]:
    """Every occurrence at or before ``now`` as ``(index, occurrence_iso)`` — deterministic and capped."""
    now_dt = _parse(now)
    base = trigger.anchor or now

    if trigger.kind is ScheduleKind.IMMEDIATE:
        return _single(0, _parse(base), now_dt)
    if trigger.kind is ScheduleKind.ONE_TIME:
        return () if trigger.run_at is None else _single(0, _parse(trigger.run_at), now_dt)
    if trigger.kind is ScheduleKind.DELAYED:
        if trigger.delay_seconds is None:
            return ()
        return _single(0, _parse(base) + timedelta(seconds=trigger.delay_seconds), now_dt)

    interval = effective_interval(trigger)
    if not interval or interval <= 0:
        return ()
    start = _parse(base)
    expires = _parse(trigger.expires_at) if trigger.expires_at else None
    result: list[tuple[int, str]] = []
    index = 0
    while len(result) < SAFETY_CAP:
        if trigger.max_occurrences is not None and index >= trigger.max_occurrences:
            break
        occurrence = start + timedelta(seconds=interval * index)
        if occurrence > now_dt or (expires is not None and occurrence > expires):
            break
        result.append((index, occurrence.isoformat()))
        index += 1
    return tuple(result)


def is_exhausted(trigger: ScheduleTrigger, now: str, dispatched: int) -> bool:
    """Whether a schedule has no further occurrences (one-shot done, or recurring past cap/expiry)."""
    if trigger.kind in (ScheduleKind.IMMEDIATE, ScheduleKind.ONE_TIME, ScheduleKind.DELAYED):
        return dispatched >= 1
    if trigger.max_occurrences is not None and dispatched >= trigger.max_occurrences:
        return True
    if trigger.expires_at is not None:
        next_index = dispatched
        interval = effective_interval(trigger)
        if interval and interval > 0:
            start = _parse(trigger.anchor or now)
            next_occurrence = start + timedelta(seconds=interval * next_index)
            return next_occurrence > _parse(trigger.expires_at)
    return False


def _single(index: int, occurrence: datetime, now_dt: datetime) -> tuple[tuple[int, str], ...]:
    return ((index, occurrence.isoformat()),) if occurrence <= now_dt else ()


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(iso)
