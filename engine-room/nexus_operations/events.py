"""Operations-Plane events — the additive ``operations.*`` instrumentation facts.

The Operations Plane observes; the one durable fact it records is an ``operations.snapshot`` — a
point-in-time health summary, recorded as instrumentation (never a Supervision ``Observation``, INV-11;
never an execution-control fact). Each is a canonical :class:`~nexus_core.domain.event.Event` with
``producer="operations"`` and ``source="nexus_operations"``. Timestamps are injected (INV-17).
"""

from __future__ import annotations

from datetime import UTC, datetime

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event

OPERATIONS_PRODUCER = "operations"
OPERATIONS_SOURCE = "nexus_operations"
EVENT_VERSION = "1"

OPERATIONS_SNAPSHOT = "operations.snapshot"

__all__ = [
    "OPERATIONS_PRODUCER",
    "OPERATIONS_SNAPSHOT",
    "OPERATIONS_SOURCE",
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
    """Construct a canonical ``operations.*`` Event with a single producer (INV-02)."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=OPERATIONS_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload=payload,
        source=OPERATIONS_SOURCE,
    )
