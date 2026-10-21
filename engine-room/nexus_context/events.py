"""Context Engineering events — the operational facts Phase 4 emits to the log.

Each builder produces a canonical :class:`~nexus_core.domain.event.Event` with
``producer="context_engineering"`` and a deterministic identifier, so a context
cycle replays identically. Timestamps are the one captured-as-data, non-structural
value (INV-17); their source is injected (:class:`TimestampSource`) so tests are
reproducible and the produced *domain objects* stay timestamp-free and
deterministic.

``TimestampSource`` is re-declared here (rather than imported from
``nexus_planning``) to keep the dependency direction clean: Context Engineering is
upstream of Planning (Goal → Context → Plan) and never depends on it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event

CONTEXT_PRODUCER = "context_engineering"
CONTEXT_SOURCE = "nexus_context"
EVENT_VERSION = "1"

CONTEXT_COLLECTION_STARTED = "context.collection_started"
CONTEXT_COLLECTED = "context.collected"
CONTEXT_VALIDATED = "context.validated"
CONTEXT_PACKAGE_CREATED = "context.package_created"
CONTEXT_ENGINEERING_COMPLETED = "context_engineering.completed"
CONTEXT_ENGINEERING_FAILED = "context_engineering.failed"


@runtime_checkable
class TimestampSource(Protocol):
    """Supplies the ISO-8601 timestamp recorded on each emitted event."""

    def now(self) -> str: ...


class FixedTimestampSource:
    """Deterministic timestamp source for tests and reproducible cycles."""

    def __init__(self, value: str = "1970-01-01T00:00:00+00:00") -> None:
        self._value = value

    def now(self) -> str:
        return self._value


class SystemTimestampSource:
    """Production timestamp source — UTC wall clock, ISO-8601."""

    def now(self) -> str:
        return datetime.now(UTC).isoformat()


def build_event(
    identifier: str,
    event_type: str,
    correlation_identifier: str,
    payload: Struct,
    timestamp: str,
    *,
    sequence_position: int | None = None,
    causation_identifier: str | None = None,
) -> Event:
    """Construct a canonical context-engineering Event with deterministic identity."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=CONTEXT_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload=payload,
        source=CONTEXT_SOURCE,
        sequence_position=sequence_position,
        causation_identifier=causation_identifier,
    )
