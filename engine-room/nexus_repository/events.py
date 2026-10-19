"""Repository Intelligence events — the ``repository.*`` facts the subsystem records.

Repository Intelligence records **one** ``repository.profiled`` fact per scan (the determinism
seam, INV-17): the scan runs once, the engine emits once, and the fact's payload embeds the
serialized :class:`~nexus_repository.profile.RepositoryProfile` so replaying the ``repository.*``
stream reconstructs the repository understanding **without rescanning**. The fact is a canonical
:class:`~nexus_core.domain.event.Event` with ``producer="repository"`` / ``source="nexus_repository"``.
Timestamps are captured as data (INV-17); the clock is injected and used only here, never in the scan.
"""

from __future__ import annotations

from datetime import UTC, datetime

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event

__all__ = [
    "REPOSITORY_PROFILED",
    "build_event",
    "system_now",
]

REPOSITORY_PRODUCER = "repository"
REPOSITORY_SOURCE = "nexus_repository"
EVENT_VERSION = "1"

REPOSITORY_PROFILED = "repository.profiled"


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
    """Construct a canonical repository Event with deterministic identity."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=REPOSITORY_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload=payload,
        source=REPOSITORY_SOURCE,
    )
