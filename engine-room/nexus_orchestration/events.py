"""Orchestration events — the operational facts the Orchestrator emits to the log.

Each builder produces a canonical :class:`~nexus_core.domain.event.Event` with
``producer="orchestration"`` and a deterministic identifier, so an orchestration
cycle replays identically. Timestamps are the one captured-as-data, non-structural
value (INV-17); their source is injected (:class:`TimestampSource`) so tests are
reproducible and the produced *domain objects* stay timestamp-free and
deterministic.

``TimestampSource`` is re-declared here (rather than imported from an earlier
layer) to keep the dependency direction clean: Orchestration is downstream of
Planning/Context and never depends on them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event

ORCHESTRATION_PRODUCER = "orchestration"
ORCHESTRATION_SOURCE = "nexus_orchestration"
EVENT_VERSION = "1"

EXECUTION_SESSION_CREATED = "orchestration.execution_session_created"
WORK_PACKAGE_READY = "orchestration.work_package_ready"
DEPENDENCY_SATISFIED = "orchestration.dependency_satisfied"
EXECUTION_QUEUED = "orchestration.execution_queued"
APPROVAL_REQUESTED = "orchestration.approval_requested"
APPROVAL_GRANTED = "orchestration.approval_granted"
APPROVAL_REJECTED = "orchestration.approval_rejected"
HARNESS_REQUEST_CREATED = "orchestration.harness_request_created"
RUNTIME_REQUEST_CREATED = "orchestration.runtime_request_created"
ORCHESTRATION_COMPLETED = "orchestration.completed"
ORCHESTRATION_FAILED = "orchestration.failed"


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
    """Construct a canonical orchestration Event with deterministic identity."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=ORCHESTRATION_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload=payload,
        source=ORCHESTRATION_SOURCE,
        sequence_position=sequence_position,
        causation_identifier=causation_identifier,
    )
