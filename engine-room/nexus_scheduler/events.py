"""Scheduler events — the additive ``scheduler.*`` timing + autonomy-dispatch facts.

The Scheduler records **only** timing-and-dispatch facts: a schedule registered / cancelled / paused /
resumed / expired, and each due occurrence dispatched (with its autonomy + policy provenance), denied, or
queued for manual action, plus a scheduled platform operation run. It records no policy verdict (Policy
owns evaluation — INV-28), no reasoning, and no engine fact — the owners record their own. Each is a
canonical :class:`~nexus_core.domain.event.Event` with ``producer="scheduler"`` and
``source="nexus_scheduler"``. The stream is durable, so replay reconstructs scheduling history exactly and
a restart resumes schedules without duplicate dispatch (INV-13/14/18). Timestamps are injected (INV-17).
"""

from __future__ import annotations

from datetime import UTC, datetime

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event

SCHEDULER_PRODUCER = "scheduler"
SCHEDULER_SOURCE = "nexus_scheduler"
EVENT_VERSION = "1"

SCHEDULER_REGISTERED = "scheduler.registered"
SCHEDULER_DISPATCHED = "scheduler.dispatched"
SCHEDULER_DISPATCH_DENIED = "scheduler.dispatch_denied"
SCHEDULER_DISPATCH_REQUESTED = "scheduler.dispatch_requested"
SCHEDULER_OPERATION_RAN = "scheduler.operation_ran"
SCHEDULER_CANCELLED = "scheduler.cancelled"
SCHEDULER_PAUSED = "scheduler.paused"
SCHEDULER_RESUMED = "scheduler.resumed"
SCHEDULER_EXPIRED = "scheduler.expired"
SCHEDULER_COMPLETED = "scheduler.completed"

__all__ = [
    "SCHEDULER_CANCELLED",
    "SCHEDULER_COMPLETED",
    "SCHEDULER_DISPATCHED",
    "SCHEDULER_DISPATCH_DENIED",
    "SCHEDULER_DISPATCH_REQUESTED",
    "SCHEDULER_EXPIRED",
    "SCHEDULER_OPERATION_RAN",
    "SCHEDULER_PAUSED",
    "SCHEDULER_PRODUCER",
    "SCHEDULER_REGISTERED",
    "SCHEDULER_RESUMED",
    "SCHEDULER_SOURCE",
    "build_event",
    "system_now",
]


def system_now() -> str:
    """Default timestamp source: wall-clock UTC, ISO-8601 (captured as event data)."""
    return datetime.now(UTC).isoformat()


def build_event(
    identifier: str,
    event_type: str,
    correlation_identifier: str,
    payload: Struct,
    timestamp: str,
) -> Event:
    """Construct a canonical ``scheduler.*`` Event with a single producer (INV-02)."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=SCHEDULER_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload=payload,
        source=SCHEDULER_SOURCE,
    )
