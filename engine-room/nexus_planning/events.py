"""Planning events — the operational facts Planning emits to the event log.

Each builder produces a canonical :class:`~nexus_core.domain.event.Event` with
``producer="planning"`` and a deterministic identifier, so a planning cycle
replays identically. Timestamps are the one captured-as-data, non-structural
value (INV-17); their source is injected (:class:`TimestampSource`) so tests are
reproducible and the produced *domain objects* stay timestamp-free and
deterministic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event

PLANNING_PRODUCER = "planning"
PLANNING_SOURCE = "nexus_planning"
EVENT_VERSION = "1"

PLAN_CREATED = "plan.created"
PLAN_UPDATED = "plan.updated"
WORK_PACKAGE_CREATED = "work_package.created"
EXECUTION_GRAPH_CREATED = "execution_graph.created"
PLANNING_COMPLETED = "planning.completed"
PLANNING_FAILED = "planning.failed"


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
    """Construct a canonical planning Event with deterministic identity."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=PLANNING_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload=payload,
        source=PLANNING_SOURCE,
        sequence_position=sequence_position,
        causation_identifier=causation_identifier,
    )
