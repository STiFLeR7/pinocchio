"""Intent Resolution events — the ``intent.*`` facts the subsystem records.

Intent Resolution records **one** ``intent.resolved`` fact per resolution (the determinism seam,
INV-17): the interpreter understands once, the engine emits once, and the fact's payload embeds the
serialized :class:`~nexus_intent.model.IntentAnalysis` (the frozen Intent, the Goal if resolved, and
the clarification requests) so replaying the ``intent.*`` stream reconstructs the understanding —
including clarifications — without re-understanding. The fact is a canonical
:class:`~nexus_core.domain.event.Event` with ``producer="intent"`` and ``source="nexus_intent"``.
Timestamps are captured as data (INV-17); the clock is injected and used only here.
"""

from __future__ import annotations

from datetime import UTC, datetime

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event

__all__ = [
    "INTENT_RESOLVED",
    "build_event",
    "system_now",
]

INTENT_PRODUCER = "intent"
INTENT_SOURCE = "nexus_intent"
EVENT_VERSION = "1"

INTENT_RESOLVED = "intent.resolved"


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
    """Construct a canonical intent Event with deterministic identity."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=INTENT_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload=payload,
        source=INTENT_SOURCE,
    )
