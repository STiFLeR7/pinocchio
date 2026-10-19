"""Engineering-Intelligence events — the ``engineering.*`` facts EI records.

EI records **one** ``engineering.strategized`` fact per Strategy (the determinism seam, INV-17):
the reasoner reasons once, the engine emits once, and the fact's payload embeds the serialized
Strategy so replaying the ``engineering.*`` stream reconstructs the decision without re-inference.
The fact is a canonical :class:`~nexus_core.domain.event.Event` with ``producer="engineering"`` and
``source="nexus_engineering"``. Timestamps are captured as data (INV-17); the clock is injected and
used only here, never in the reasoning.
"""

from __future__ import annotations

from datetime import UTC, datetime

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event

__all__ = [
    "ENGINEERING_STRATEGIZED",
    "build_event",
    "system_now",
]

ENGINEERING_PRODUCER = "engineering"
ENGINEERING_SOURCE = "nexus_engineering"
EVENT_VERSION = "1"

ENGINEERING_STRATEGIZED = "engineering.strategized"


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
    """Construct a canonical engineering Event with deterministic identity."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=ENGINEERING_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload=payload,
        source=ENGINEERING_SOURCE,
    )
