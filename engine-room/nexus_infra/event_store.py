"""Step 1 — the append-only Event Store (ADR-001, AP-201, INV-13/14).

The store is the **single authoritative source of operational truth**: an
ordered, append-only log. It never updates or deletes. It guarantees:

- **Deterministic global ordering** via a monotonic counter (not a clock).
- **Causal ordering per correlation** — a correlation identifier names a stream;
  events keep their append order within it.
- **Idempotent append** (INV-16) — re-appending an identical event is a no-op;
  re-using an identifier for different content is a :class:`DuplicateEventError`.
- **Optimistic concurrency** — an append may declare the stream position it
  expects to write at; a mismatch raises :class:`ConcurrencyConflictError`.
- **Replay** — read the whole log, a single correlation stream, or the tail from
  a global position (the basis for snapshot-plus-replay recovery).

This is a local, single-node implementation. Distributed storage is out of scope
(ADR-001 §10 keeps the model partition-friendly for later).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from nexus_core.domain.event import Event
from nexus_infra.errors import ConcurrencyConflictError, DuplicateEventError
from nexus_infra.observability import (
    InfraEvent,
    InfraEventType,
    NullObservability,
    Observability,
)

# Sentinel for "no concurrency expectation" on an append.
NO_EXPECTATION = -1


@dataclass(frozen=True, slots=True)
class StoredEvent:
    """An Event as committed to the log, with its assigned positions.

    ``global_sequence`` is 1-based across the whole store; ``stream_position`` is
    0-based within the event's correlation stream. Both are assigned by the store,
    never by the caller, so ordering is authoritative and deterministic.
    """

    event: Event
    global_sequence: int
    stream: str
    stream_position: int


class InMemoryEventStore:
    """A local append-only event log implementing ``EventStore``."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._log: list[StoredEvent] = []
        self._streams: dict[str, list[StoredEvent]] = {}
        self._by_identifier: dict[str, StoredEvent] = {}
        self._obs: Observability = observability or NullObservability()

    # -- EventStore protocol ------------------------------------------------- #

    def append(self, event: Event) -> None:
        """Append ``event`` to its correlation stream (Protocol entry point).

        If the event carries an explicit ``sequence_position`` it is treated as
        the *expected* stream version (optimistic concurrency). ``None`` means
        "append at the end with no expectation".
        """
        expected = (
            event.sequence_position if event.sequence_position is not None else NO_EXPECTATION
        )
        self.append_expecting(event, expected)

    def read_stream(self, correlation_identifier: str) -> Iterable[Event]:
        """Every event in one correlation stream, in causal (append) order."""
        return tuple(s.event for s in self._streams.get(correlation_identifier, ()))

    def read_all(self) -> Iterable[Event]:
        """Every event in the store, in global append order."""
        return tuple(s.event for s in self._log)

    # -- richer infrastructure API ------------------------------------------ #

    def append_expecting(self, event: Event, expected_version: int) -> StoredEvent:
        """Append with an explicit expected stream version.

        ``expected_version`` is the stream length the caller believes is current;
        :data:`NO_EXPECTATION` disables the check. Returns the committed
        :class:`StoredEvent`. Idempotent on the event identifier.
        """
        existing = self._by_identifier.get(event.identifier)
        if existing is not None:
            if existing.event == event:
                self._obs.record(
                    InfraEvent(
                        InfraEventType.EVENT_DUPLICATE_IGNORED,
                        subject=event.identifier,
                        at_sequence=existing.global_sequence,
                    )
                )
                return existing
            raise DuplicateEventError(event.identifier)

        stream = event.correlation_identifier
        stream_log = self._streams.setdefault(stream, [])
        current_version = len(stream_log)
        if expected_version != NO_EXPECTATION and expected_version != current_version:
            self._obs.record(
                InfraEvent(
                    InfraEventType.CONCURRENCY_CONFLICT,
                    subject=stream,
                    detail={"expected": expected_version, "actual": current_version},
                )
            )
            self._obs.increment("event_store.concurrency_conflict")
            raise ConcurrencyConflictError(stream, expected_version, current_version)

        stored = StoredEvent(
            event=event,
            global_sequence=len(self._log) + 1,
            stream=stream,
            stream_position=current_version,
        )
        self._log.append(stored)
        stream_log.append(stored)
        self._by_identifier[event.identifier] = stored
        self._obs.record(
            InfraEvent(
                InfraEventType.EVENT_APPENDED,
                subject=event.identifier,
                at_sequence=stored.global_sequence,
                detail={"type": event.type, "stream": stream},
            )
        )
        self._obs.increment("event_store.appended")
        return stored

    def read_from(self, global_sequence: int) -> Iterable[Event]:
        """The tail of the log from ``global_sequence`` (inclusive, 1-based).

        Used by recovery: restore a snapshot taken at position N, then replay from
        N+1 to reconstruct current state without re-reading the whole log.
        """
        if global_sequence < 1:
            raise ValueError("global_sequence is 1-based and must be >= 1")
        return tuple(s.event for s in self._log[global_sequence - 1 :])

    def read_all_stored(self) -> tuple[StoredEvent, ...]:
        """Every committed record (with positions), in global order."""
        return tuple(self._log)

    def stream_version(self, correlation_identifier: str) -> int:
        """The current length of a correlation stream (its next expected position)."""
        return len(self._streams.get(correlation_identifier, ()))

    def global_length(self) -> int:
        """The number of events in the whole log."""
        return len(self._log)

    def contains(self, event_identifier: str) -> bool:
        """Whether an event with this identifier has been committed."""
        return event_identifier in self._by_identifier
