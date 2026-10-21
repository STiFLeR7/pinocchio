"""Reflection events — the ``reflection.*`` facts the Reflection Engine emits.

Milestone 4. Each fact is a canonical :class:`~nexus_core.domain.event.Event` with
``producer="reflection"`` and ``source="nexus_reflection"`` and a deterministic identifier, so
a reflection cycle replays identically (ADR-001; the ``reflection.*`` namespace is reserved for
Reflection, doc 26 / doc 23). The Reflection Report is a projection of this stream. Timestamps
are the one captured-as-data, non-structural value (INV-17); their source is injected so tests
are reproducible and the produced *value objects* (Report / Patterns / Candidates) stay
timestamp-free and deterministic.

``TimestampSource`` is reused from the runtime layer (reflection is downstream of recovery,
validation, execution, and runtime) rather than re-declared, keeping one definition of the
primitive.
"""

from __future__ import annotations

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event
from nexus_runtime.events import (  # reused primitive (reflection → recovery → … → runtime)
    FixedTimestampSource,
    SystemTimestampSource,
    TimestampSource,
)

__all__ = [
    "REFLECTION_ANALYSIS_COMPLETED",
    "REFLECTION_COMPLETED",
    "REFLECTION_FAILED",
    "REFLECTION_REPORT_CREATED",
    "REFLECTION_STARTED",
    "FixedTimestampSource",
    "SystemTimestampSource",
    "TimestampSource",
    "build_event",
]

REFLECTION_PRODUCER = "reflection"
REFLECTION_SOURCE = "nexus_reflection"
EVENT_VERSION = "1"

# --- canonical reflection.* taxonomy (doc 26 / doc 23) -------------------------- #
REFLECTION_STARTED = "reflection.started"
REFLECTION_ANALYSIS_COMPLETED = "reflection.analysis_completed"
REFLECTION_REPORT_CREATED = "reflection.report_created"
REFLECTION_COMPLETED = "reflection.completed"
REFLECTION_FAILED = "reflection.failed"


def build_event(
    identifier: str,
    event_type: str,
    correlation_identifier: str,
    payload: Struct,
    timestamp: str,
    *,
    execution_identifier: str | None = None,
) -> Event:
    """Construct a canonical reflection Event with deterministic identity."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=REFLECTION_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=execution_identifier,
        payload=payload,
        source=REFLECTION_SOURCE,
    )
