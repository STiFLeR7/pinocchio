"""Unit tests for ``EventMetadata`` and the event-seam Protocols."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.enums import Priority
from nexus_core.domain.event import Event
from nexus_core.events.identifiers import IdentifierFactory
from nexus_core.events.interfaces import EventConsumer, EventEmitter, EventHandler
from nexus_core.events.metadata import EventMetadata
from nexus_core.events.versioning import EventUpcaster, UpcasterRegistry

# --------------------------------------------------------------------------- #
# Builders                                                                     #
# --------------------------------------------------------------------------- #


def _build_event(
    identifier: str = "evt-1",
    correlation_identifier: str = "corr-1",
    version: str = "1.0.0",
) -> Event:
    return Event(
        identifier=identifier,
        type="goal.created",
        version=version,
        timestamp="2026-06-29T00:00:00Z",
        producer="intent",
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload={"goal": "goal-1"},
        source="cli",
    )


# --------------------------------------------------------------------------- #
# EventMetadata                                                               #
# --------------------------------------------------------------------------- #


def test_event_metadata_all_optional() -> None:
    meta = EventMetadata()
    assert meta.subsystem is None
    assert meta.priority is None
    assert meta.retry_count is None


def test_event_metadata_constructs_with_values() -> None:
    meta = EventMetadata(
        subsystem="orchestration",
        priority=Priority.HIGH,
        trace_identifier="trace-1",
        retry_count=2,
        latency_ms=12.5,
    )
    assert meta.subsystem == "orchestration"
    assert meta.priority is Priority.HIGH
    assert meta.retry_count == 2
    assert meta.latency_ms == 12.5


def test_event_metadata_is_frozen() -> None:
    meta = EventMetadata(subsystem="orchestration")
    with pytest.raises(ValidationError):
        meta.subsystem = "execution"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Fakes                                                                        #
# --------------------------------------------------------------------------- #


class FakeIdentifierFactory:
    """A deterministic counter-backed identifier factory."""

    def __init__(self) -> None:
        self._event = 0
        self._correlation = 0
        self._execution = 0

    def new_event_identifier(self) -> str:
        self._event += 1
        return f"evt-{self._event}"

    def new_correlation_identifier(self) -> str:
        self._correlation += 1
        return f"corr-{self._correlation}"

    def new_execution_identifier(self) -> str:
        self._execution += 1
        return f"exec-{self._execution}"


class FakeEmitter:
    def __init__(self) -> None:
        self.emitted: list[Event] = []

    def emit(self, event: Event) -> None:
        self.emitted.append(event)


class FakeHandler:
    def __init__(self) -> None:
        self.handled: list[Event] = []

    def handle(self, event: Event) -> None:
        self.handled.append(event)


class FakeConsumer:
    def __init__(self) -> None:
        self._handlers: list[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    def unsubscribe(self, handler: EventHandler) -> None:
        self._handlers.remove(handler)

    def dispatch(self, event: Event) -> None:
        for handler in self._handlers:
            handler.handle(event)


class FakePassthroughUpcaster:
    def can_upcast(self, event_type: str, version: str) -> bool:
        return event_type == "goal.created" and version == "1.0.0"

    def upcast(self, event: Event) -> Event:
        return event


class FakeUpcasterRegistry:
    def __init__(self) -> None:
        self._upcasters: list[EventUpcaster] = []

    def register(self, upcaster: EventUpcaster) -> None:
        self._upcasters.append(upcaster)

    def upcast_to_current(self, event: Event) -> Event:
        current = event
        for upcaster in self._upcasters:
            if upcaster.can_upcast(current.type, current.version):
                current = upcaster.upcast(current)
        return current


# --------------------------------------------------------------------------- #
# Protocol conformance                                                        #
# --------------------------------------------------------------------------- #


def test_fakes_satisfy_runtime_checkable_protocols() -> None:
    assert isinstance(FakeIdentifierFactory(), IdentifierFactory)
    assert isinstance(FakeEmitter(), EventEmitter)
    assert isinstance(FakeHandler(), EventHandler)
    assert isinstance(FakeConsumer(), EventConsumer)
    assert isinstance(FakePassthroughUpcaster(), EventUpcaster)
    assert isinstance(FakeUpcasterRegistry(), UpcasterRegistry)


# --------------------------------------------------------------------------- #
# Behaviour                                                                    #
# --------------------------------------------------------------------------- #


def test_emitter_collects_emitted_events() -> None:
    emitter = FakeEmitter()
    event = _build_event()
    emitter.emit(event)
    assert emitter.emitted == [event]


def test_consumer_dispatches_to_handler() -> None:
    consumer = FakeConsumer()
    handler = FakeHandler()
    consumer.subscribe(handler)
    event = _build_event()
    consumer.dispatch(event)
    assert handler.handled == [event]

    consumer.unsubscribe(handler)
    consumer.dispatch(_build_event(identifier="evt-2"))
    assert handler.handled == [event]


def test_deterministic_identifier_factory_yields_stable_ids() -> None:
    factory = FakeIdentifierFactory()
    assert factory.new_event_identifier() == "evt-1"
    assert factory.new_event_identifier() == "evt-2"
    assert factory.new_correlation_identifier() == "corr-1"
    assert factory.new_execution_identifier() == "exec-1"

    # A fresh factory replays the identical sequence (determinism).
    other = FakeIdentifierFactory()
    assert other.new_event_identifier() == "evt-1"


def test_upcaster_passes_event_through_registry() -> None:
    registry = FakeUpcasterRegistry()
    registry.register(FakePassthroughUpcaster())
    event = _build_event()
    assert registry.upcast_to_current(event) == event


def test_upcaster_skips_when_not_applicable() -> None:
    registry = FakeUpcasterRegistry()
    registry.register(FakePassthroughUpcaster())
    event = _build_event(version="2.0.0")
    # Upcaster declines (version mismatch); event unchanged.
    assert registry.upcast_to_current(event) == event
