"""Schedule registry reconstruction — rebuild durable scheduler state from the ``scheduler.*`` log.

Scheduler state is a projection (INV-13/14): the schedules, their lifecycle, and which occurrences have
already fired are a pure function of the durable ``scheduler.*`` facts. A reopened log reconstructs the
identical schedules and the identical set of fired occurrences, so a restart never re-dispatches a done
occurrence (INV-18). The Goal request is stored on the ``scheduler.registered`` fact and reloaded on demand.
"""

from __future__ import annotations

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event
from nexus_scheduler import events as sevents
from nexus_scheduler.model import (
    AutonomyMode,
    Schedule,
    ScheduleKind,
    ScheduleStatus,
)

# Facts that mark an occurrence as fired (handled) — none of these is ever retried on a later tick.
_FIRED = frozenset(
    {
        sevents.SCHEDULER_DISPATCHED,
        sevents.SCHEDULER_DISPATCH_DENIED,
        sevents.SCHEDULER_DISPATCH_REQUESTED,
        sevents.SCHEDULER_OPERATION_RAN,
    }
)

_STATUS_FACT = {
    sevents.SCHEDULER_CANCELLED: ScheduleStatus.CANCELLED,
    sevents.SCHEDULER_PAUSED: ScheduleStatus.PAUSED,
    sevents.SCHEDULER_RESUMED: ScheduleStatus.ACTIVE,
    sevents.SCHEDULER_EXPIRED: ScheduleStatus.EXPIRED,
    sevents.SCHEDULER_COMPLETED: ScheduleStatus.COMPLETED,
}


class _Trace:
    __slots__ = ("fired", "registered", "status")

    def __init__(self, registered: Event) -> None:
        self.registered = registered
        self.status = ScheduleStatus.ACTIVE
        self.fired: set[int] = set()


def reconstruct_schedules(events: tuple[Event, ...]) -> tuple[Schedule, ...]:
    """Rebuild every schedule from the ``scheduler.*`` stream, in registration order (the log is truth)."""
    traces: dict[str, _Trace] = {}
    order: list[str] = []
    for event in events:
        if event.producer != sevents.SCHEDULER_PRODUCER:
            continue
        schedule_id = str(event.payload.get("schedule_id", ""))
        if event.type == sevents.SCHEDULER_REGISTERED:
            if schedule_id not in traces:
                order.append(schedule_id)
            traces[schedule_id] = _Trace(event)
            continue
        trace = traces.get(schedule_id)
        if trace is None:
            continue
        if event.type in _FIRED:
            trace.fired.add(int(event.payload.get("occurrence", 0)))
        elif event.type in _STATUS_FACT:
            trace.status = _STATUS_FACT[event.type]
    return tuple(_project(traces[schedule_id]) for schedule_id in order)


def reconstruct_schedule(events: tuple[Event, ...], schedule_id: str) -> Schedule | None:
    """Rebuild one schedule, or ``None`` if it was never registered."""
    for schedule in reconstruct_schedules(events):
        if schedule.identity == schedule_id:
            return schedule
    return None


def request_payload_for(events: tuple[Event, ...], schedule_id: str) -> Struct | None:
    """The serialized Goal request stored on the ``scheduler.registered`` fact, if any."""
    for event in events:
        if event.producer != sevents.SCHEDULER_PRODUCER:
            continue
        if event.type != sevents.SCHEDULER_REGISTERED:
            continue
        if str(event.payload.get("schedule_id", "")) != schedule_id:
            continue
        request = event.payload.get("request")
        return request if isinstance(request, dict) else None
    return None


def _project(trace: _Trace) -> Schedule:
    payload = trace.registered.payload
    return Schedule(
        identity=str(payload.get("schedule_id", "")),
        kind=ScheduleKind(payload.get("kind", ScheduleKind.IMMEDIATE.value)),
        status=trace.status,
        autonomy=AutonomyMode(payload.get("autonomy", AutonomyMode.GOVERNED.value)),
        target_kind=str(payload.get("target_kind", "")),
        operation=_opt(payload.get("operation")),
        anchor=str(payload.get("anchor", "")),
        run_at=_opt(payload.get("run_at")),
        delay_seconds=_opt_int(payload.get("delay_seconds")),
        interval_seconds=_opt_int(payload.get("interval_seconds")),
        cron=_opt(payload.get("cron")),
        max_occurrences=_opt_int(payload.get("max_occurrences")),
        expires_at=_opt(payload.get("expires_at")),
        dispatched=tuple(sorted(trace.fired)),
        correlation_identifier=str(payload.get("correlation", "")),
    )


def _opt(value: object) -> str | None:
    return None if value is None else str(value)


def _opt_int(value: object) -> int | None:
    return value if isinstance(value, int) else None
