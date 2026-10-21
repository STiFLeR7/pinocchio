"""Infrastructure observability — instrumentation only (no dashboards).

The substrate emits structured *infrastructure events*, counters, and timings so
operators (and later, Supervision) can derive health. This module provides the
sink interface plus an in-memory implementation for tests, a null implementation
for the default, zero-overhead path, and a stdlib-``logging``-backed implementation
an operator can wire in for a production process (P17 — the platform shipped with
no sink an operator could actually read after process exit; this closes that gap
additively, without touching the protocol or any existing sink). It builds **no**
dashboards, stores nothing durably itself, and never influences projected state.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from nexus_infra.clock import Clock


class InfraEventType(StrEnum):
    """The kinds of infrastructure events the substrate emits."""

    EVENT_APPENDED = "event.appended"
    EVENT_DUPLICATE_IGNORED = "event.duplicate_ignored"
    EVENT_PUBLISHED = "event.published"
    EVENT_DELIVERED = "event.delivered"
    HANDLER_FAILED = "event.handler_failed"
    EVENT_DEAD_LETTERED = "event.dead_lettered"
    PROJECTION_APPLIED = "projection.applied"
    PROJECTION_REBUILT = "projection.rebuilt"
    SNAPSHOT_CREATED = "snapshot.created"
    SNAPSHOT_RESTORED = "snapshot.restored"
    REPOSITORY_WRITE = "repository.write"
    TRANSACTION_COMMITTED = "transaction.committed"
    TRANSACTION_ROLLED_BACK = "transaction.rolled_back"
    CONCURRENCY_CONFLICT = "concurrency.conflict"


@dataclass(frozen=True, slots=True)
class InfraEvent:
    """A single structured instrumentation record (not a domain Event)."""

    type: InfraEventType
    subject: str
    """What the event is about (e.g. an event identifier, stream, or repo name)."""
    at_sequence: int | None = None
    """The log position this record relates to, when applicable."""
    duration_ns: int | None = None
    detail: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class Observability(Protocol):
    """Sink for infrastructure events, counters, and timings."""

    def record(self, event: InfraEvent) -> None: ...

    def increment(self, name: str, value: int = 1) -> None: ...

    def observe(self, name: str, value: float) -> None: ...


class NullObservability:
    """Default no-op sink — zero overhead, records nothing."""

    def record(self, event: InfraEvent) -> None:
        return None

    def increment(self, name: str, value: int = 1) -> None:
        return None

    def observe(self, name: str, value: float) -> None:
        return None


class InMemoryObservability:
    """Collecting sink for tests and local inspection."""

    def __init__(self) -> None:
        self.events: list[InfraEvent] = []
        self.counters: dict[str, int] = {}
        self.observations: dict[str, list[float]] = {}

    def record(self, event: InfraEvent) -> None:
        self.events.append(event)

    def increment(self, name: str, value: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + value

    def observe(self, name: str, value: float) -> None:
        self.observations.setdefault(name, []).append(value)

    def events_of(self, type_: InfraEventType) -> tuple[InfraEvent, ...]:
        """All recorded events of a given type (insertion order)."""
        return tuple(e for e in self.events if e.type is type_)


class LoggingObservability:
    """Writes each infrastructure event/counter/observation as one structured line via ``logging``.

    A production-usable sink: an operator configures the ``"nexus.infra"`` logger's handlers/level
    (file, stdout, a log-shipping handler — this class makes no assumption) and every append,
    concurrency conflict, transaction outcome, and snapshot operation becomes one log record. Errors
    (``HANDLER_FAILED``, ``CONCURRENCY_CONFLICT``, ``EVENT_DEAD_LETTERED``) log at ``WARNING``;
    everything else logs at ``INFO``. Never raises — a broken log handler must not break the platform.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("nexus.infra")

    _WARNING_TYPES = frozenset(
        {
            InfraEventType.HANDLER_FAILED,
            InfraEventType.CONCURRENCY_CONFLICT,
            InfraEventType.EVENT_DEAD_LETTERED,
        }
    )

    def record(self, event: InfraEvent) -> None:
        level = logging.WARNING if event.type in self._WARNING_TYPES else logging.INFO
        self._logger.log(
            level,
            "%s subject=%s at_sequence=%s detail=%s",
            event.type.value,
            event.subject,
            event.at_sequence,
            dict(event.detail),
        )

    def increment(self, name: str, value: int = 1) -> None:
        self._logger.info("counter %s +%s", name, value)

    def observe(self, name: str, value: float) -> None:
        self._logger.info("observation %s=%s", name, value)


@contextmanager
def timed(clock: Clock, observability: Observability, metric: str) -> Iterator[None]:
    """Measure the wrapped block and record its duration as an observation."""
    start = clock.now_ns()
    try:
        yield
    finally:
        observability.observe(metric, float(clock.now_ns() - start))
