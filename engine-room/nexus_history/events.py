"""Execution History events — the ``execution_history.*`` facts the subsystem records.

Execution History records **one** ``execution_history.projected`` fact per query (the determinism
seam, INV-17): it reconstructs history once from the authoritative log, emits once, and the fact's
payload embeds the serialized :class:`~nexus_history.model.ExecutionHistoryProfile` so replaying the
``execution_history.*`` stream reconstructs the historical view **without re-projecting**. The fact
is a canonical :class:`~nexus_core.domain.event.Event` with ``producer="execution_history"`` /
``source="nexus_history"``. Timestamps are captured as data (INV-17); the clock is injected and used
only here, never in the projection.

Execution History emits **only** ``execution_history.*`` events — it never touches ``runtime.*``,
``validation.*``, ``recovery.*``, ``reflection.*``, or ``knowledge.*`` (it reads them, read-only).
"""

from __future__ import annotations

from datetime import UTC, datetime

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event

__all__ = [
    "EXECUTION_HISTORY_PROJECTED",
    "HISTORY_EVENT_PREFIX",
    "build_event",
    "system_now",
]

HISTORY_PRODUCER = "execution_history"
HISTORY_SOURCE = "nexus_history"
EVENT_VERSION = "1"

HISTORY_EVENT_PREFIX = "execution_history."
EXECUTION_HISTORY_PROJECTED = "execution_history.projected"


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
    """Construct a canonical execution-history Event with deterministic identity."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=HISTORY_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload=payload,
        source=HISTORY_SOURCE,
    )
