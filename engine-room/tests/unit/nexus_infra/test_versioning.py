"""Tests for :class:`nexus_infra.InMemoryUpcasterRegistry`.

Old events stay replayable forever by upcasting them to the current schema
version on read (ADR-001 §6). The registry resolves applicable upcasters and
chains them to a fixed point. These tests cover single upcasting, chaining,
passthrough when nothing applies, and the non-convergence guard that protects
against an upcaster that claims applicability without ever advancing the event.
"""

from __future__ import annotations

import pytest

from nexus_core.domain.event import Event
from nexus_core.events.versioning import EventUpcaster
from nexus_infra import InMemoryUpcasterRegistry, UpcastError
from tests.unit.nexus_infra.factories import make_event


class UpcasterV1toV2:
    """Brings ``goal.created`` v1 events to v2, marking the bump in the payload."""

    def can_upcast(self, event_type: str, version: str) -> bool:
        return event_type == "goal.created" and version == "1"

    def upcast(self, event: Event) -> Event:
        return event.model_copy(update={"version": "2", "payload": {**event.payload, "v2": True}})


class UpcasterV2toV3:
    """Brings ``goal.created`` v2 events to v3."""

    def can_upcast(self, event_type: str, version: str) -> bool:
        return event_type == "goal.created" and version == "2"

    def upcast(self, event: Event) -> Event:
        return event.model_copy(update={"version": "3", "payload": {**event.payload, "v3": True}})


class NonConvergingUpcaster:
    """Always claims applicability but returns an equal event — must trip the guard."""

    def can_upcast(self, event_type: str, version: str) -> bool:
        return True

    def upcast(self, event: Event) -> Event:
        return event


def test_concrete_upcasters_satisfy_protocol() -> None:
    assert isinstance(UpcasterV1toV2(), EventUpcaster)
    assert isinstance(UpcasterV2toV3(), EventUpcaster)


def test_register_and_upcast_single_step() -> None:
    registry = InMemoryUpcasterRegistry()
    registry.register(UpcasterV1toV2())

    event = make_event("e1", type="goal.created", version="1")
    result = registry.upcast_to_current(event)

    assert result.version == "2"
    assert result.payload.get("v2") is True
    assert result.identifier == "e1"


def test_chaining_brings_v1_to_v3() -> None:
    registry = InMemoryUpcasterRegistry()
    registry.register(UpcasterV1toV2())
    registry.register(UpcasterV2toV3())

    event = make_event("e1", type="goal.created", version="1")
    result = registry.upcast_to_current(event)

    assert result.version == "3"
    assert result.payload.get("v2") is True
    assert result.payload.get("v3") is True


def test_chaining_is_order_independent() -> None:
    # The registry tries every upcaster each step, so registration order of the
    # chain steps does not change the fixed point.
    registry = InMemoryUpcasterRegistry()
    registry.register(UpcasterV2toV3())
    registry.register(UpcasterV1toV2())

    event = make_event("e1", type="goal.created", version="1")
    result = registry.upcast_to_current(event)

    assert result.version == "3"


def test_no_applicable_upcaster_returns_event_unchanged() -> None:
    registry = InMemoryUpcasterRegistry()
    registry.register(UpcasterV1toV2())

    # Wrong type: nothing applies.
    event = make_event("e1", type="plan.created", version="1")
    result = registry.upcast_to_current(event)

    assert result == event
    assert result is event


def test_empty_registry_returns_event_unchanged() -> None:
    registry = InMemoryUpcasterRegistry()
    event = make_event("e1", type="goal.created", version="1")

    assert registry.upcast_to_current(event) is event


def test_already_current_version_is_passthrough() -> None:
    registry = InMemoryUpcasterRegistry()
    registry.register(UpcasterV1toV2())

    # v2 already: the only registered upcaster only claims v1.
    event = make_event("e1", type="goal.created", version="2")
    result = registry.upcast_to_current(event)

    assert result is event


def test_non_convergence_raises_upcast_error() -> None:
    registry = InMemoryUpcasterRegistry()
    registry.register(NonConvergingUpcaster())

    event = make_event("e1", type="goal.created", version="1")
    with pytest.raises(UpcastError) as excinfo:
        registry.upcast_to_current(event)

    message = str(excinfo.value)
    assert "did not advance" in message
    assert "e1" in message
