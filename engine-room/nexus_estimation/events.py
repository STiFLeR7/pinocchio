"""Estimation events — the ``estimation.*`` facts the subsystem records.

An estimation records one ``estimation.estimated`` fact per report (WP: durable persistence /
replay). The fact is a canonical :class:`~nexus_core.domain.event.Event` with
``producer="estimation"`` and ``source="nexus_estimation"`` and a deterministic identity, so
an estimation replays identically (ADR-001/INV-17). The fact's payload embeds the serialized
report, so replaying the ``estimation.*`` stream reconstructs every estimate without
re-computation. Timestamps are captured as data (INV-17); the source is injected.
"""

from __future__ import annotations

from datetime import UTC, datetime

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event

__all__ = [
    "ESTIMATION_ESTIMATED",
    "build_event",
    "system_now",
]

ESTIMATION_PRODUCER = "estimation"
ESTIMATION_SOURCE = "nexus_estimation"
EVENT_VERSION = "1"

ESTIMATION_ESTIMATED = "estimation.estimated"


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
    """Construct a canonical estimation Event with deterministic identity."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=ESTIMATION_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload=payload,
        source=ESTIMATION_SOURCE,
    )
