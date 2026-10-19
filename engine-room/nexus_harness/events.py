"""Harness events — the operational facts the Harness emits to the log.

Each builder produces a canonical :class:`~nexus_core.domain.event.Event` with
``producer="harness"`` and a deterministic identifier, so a compilation cycle
replays identically. Timestamps are the one captured-as-data, non-structural value
(INV-17); their source is injected (:class:`TimestampSource`) so tests are
reproducible and the produced *domain objects* (Execution Packages / Manifests) stay
timestamp-free and deterministic.

``TimestampSource`` is re-declared here (rather than imported from an earlier layer)
to keep the dependency direction clean: the Harness is downstream of Orchestration
and never depends on it for this primitive.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event

HARNESS_PRODUCER = "harness"
HARNESS_SOURCE = "nexus_harness"
EVENT_VERSION = "1"

HARNESS_REQUEST_VALIDATED = "harness.request_validated"
SKILLS_RESOLVED = "harness.skills_resolved"
CAPABILITIES_RESOLVED = "harness.capabilities_resolved"
POLICIES_RESOLVED = "harness.policies_resolved"
CONTEXT_RESOLVED = "harness.context_resolved"
ARTIFACTS_RESOLVED = "harness.artifacts_resolved"
EXECUTION_PACKAGE_CREATED = "harness.execution_package_created"
EXECUTION_MANIFEST_CREATED = "harness.execution_manifest_created"
HARNESS_COMPLETED = "harness.completed"
HARNESS_FAILED = "harness.failed"


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
    """Construct a canonical harness Event with deterministic identity."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=HARNESS_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload=payload,
        source=HARNESS_SOURCE,
        sequence_position=sequence_position,
        causation_identifier=causation_identifier,
    )
