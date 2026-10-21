"""Tests for :class:`nexus_infra.ProjectionEngine`.

The engine drives a :class:`nexus_core.persistence.interfaces.Projection`, adding
idempotency (INV-16), determinism (INV-14), rebuild/replay-equivalence, schema
versioning, and optional upcasting. These tests exercise those guarantees through
a concrete ``CountingProjection`` whose state is the ordered tuple of applied
event identifiers — so both ordering and dedup are directly observable.
"""

from __future__ import annotations

from nexus_core.domain.event import Event
from nexus_core.events.versioning import EventUpcaster
from nexus_core.persistence.interfaces import Projection
from nexus_infra import (
    InfraEventType,
    InMemoryObservability,
    InMemoryUpcasterRegistry,
    ProjectionEngine,
)
from tests.unit.nexus_infra.factories import make_event


class CountingProjection:
    """A minimal :class:`Projection` whose state is the applied identifiers in order."""

    def __init__(self) -> None:
        self._applied: list[str] = []

    def apply(self, event: Event) -> None:
        self._applied.append(event.identifier)

    @property
    def state(self) -> tuple[str, ...]:
        return tuple(self._applied)


def make_projection() -> CountingProjection:
    """Factory the engine calls to (re)build a fresh projection."""
    return CountingProjection()


class RetypingUpcaster:
    """Bumps version 1 -> 2 and rewrites the event type, recording the change in payload."""

    def can_upcast(self, event_type: str, version: str) -> bool:
        return event_type == "goal.created" and version == "1"

    def upcast(self, event: Event) -> Event:
        return event.model_copy(
            update={
                "version": "2",
                "type": "goal.opened",
                "payload": {**event.payload, "upcast": True},
            }
        )


def test_concrete_projection_satisfies_protocol() -> None:
    assert isinstance(make_projection(), Projection)


def test_apply_folds_events_in_order() -> None:
    engine: ProjectionEngine[tuple[str, ...]] = ProjectionEngine(make_projection)

    engine.apply(make_event("e1"))
    engine.apply(make_event("e2"))
    engine.apply(make_event("e3"))

    assert engine.state == ("e1", "e2", "e3")
    assert engine.applied_count == 3


def test_idempotency_same_identifier_folded_once() -> None:
    obs = InMemoryObservability()
    engine: ProjectionEngine[tuple[str, ...]] = ProjectionEngine(make_projection, observability=obs)

    event = make_event("e1")
    engine.apply(event)
    state_after_first = engine.state

    engine.apply(event)  # duplicate delivery (INV-16)

    assert engine.state == state_after_first == ("e1",)
    assert engine.applied_count == 1
    assert engine.has_seen("e1") is True
    assert obs.counters.get("projection.duplicate_skipped") == 1
    assert obs.counters.get("projection.applied") == 1


def test_idempotency_distinct_payload_same_identifier_still_skipped() -> None:
    # Dedup is keyed strictly on identifier, independent of content.
    engine: ProjectionEngine[tuple[str, ...]] = ProjectionEngine(make_projection)

    engine.apply(make_event("e1", payload={"v": 1}))
    engine.apply(make_event("e1", payload={"v": 2}))

    assert engine.state == ("e1",)
    assert engine.applied_count == 1


def test_has_seen_false_for_unapplied_identifier() -> None:
    engine: ProjectionEngine[tuple[str, ...]] = ProjectionEngine(make_projection)
    assert engine.has_seen("never") is False


def test_consume_folds_sequence_in_order() -> None:
    engine: ProjectionEngine[tuple[str, ...]] = ProjectionEngine(make_projection)
    events = [make_event(f"e{i}") for i in range(5)]

    engine.consume(events)

    assert engine.state == tuple(f"e{i}" for i in range(5))
    assert engine.applied_count == 5


def test_handle_is_alias_for_apply() -> None:
    engine: ProjectionEngine[tuple[str, ...]] = ProjectionEngine(make_projection)

    engine.handle(make_event("e1"))
    engine.handle(make_event("e2"))
    engine.handle(make_event("e1"))  # still deduped through the handler path

    assert engine.state == ("e1", "e2")
    assert engine.applied_count == 2


def test_rebuild_is_replay_equivalent_on_same_engine() -> None:
    obs = InMemoryObservability()
    engine: ProjectionEngine[tuple[str, ...]] = ProjectionEngine(make_projection, observability=obs)
    events = [make_event(f"e{i}") for i in range(4)]

    engine.consume(events)
    built_state = engine.state

    engine.rebuild(events)

    assert engine.state == built_state == ("e0", "e1", "e2", "e3")
    assert engine.applied_count == 4

    rebuilt = obs.events_of(InfraEventType.PROJECTION_REBUILT)
    assert len(rebuilt) == 1
    assert rebuilt[0].detail == {"applied": 4}


def test_rebuild_clears_dedup_state() -> None:
    engine: ProjectionEngine[tuple[str, ...]] = ProjectionEngine(make_projection)
    events = [make_event("e1"), make_event("e2")]

    engine.consume(events)
    engine.rebuild(events)

    # If dedup state were not cleared, rebuild would skip every event.
    assert engine.state == ("e1", "e2")
    assert engine.applied_count == 2


def test_two_fresh_engines_fold_deterministically() -> None:
    events = [make_event(f"e{i}") for i in range(6)]

    engine_a: ProjectionEngine[tuple[str, ...]] = ProjectionEngine(make_projection)
    engine_b: ProjectionEngine[tuple[str, ...]] = ProjectionEngine(make_projection)

    engine_a.consume(events)
    engine_b.consume(events)

    assert engine_a.state == engine_b.state


def test_version_property_reflects_injected_version() -> None:
    engine: ProjectionEngine[tuple[str, ...]] = ProjectionEngine(make_projection, version=7)
    assert engine.version == 7


def test_default_version_is_one() -> None:
    engine: ProjectionEngine[tuple[str, ...]] = ProjectionEngine(make_projection)
    assert engine.version == 1


def test_upcasters_transform_events_before_apply() -> None:
    registry = InMemoryUpcasterRegistry()
    registry.register(RetypingUpcaster())

    captured: list[Event] = []

    class CapturingProjection:
        def __init__(self) -> None:
            self._events: list[Event] = []

        def apply(self, event: Event) -> None:
            self._events.append(event)
            captured.append(event)

        @property
        def state(self) -> tuple[Event, ...]:
            return tuple(self._events)

    engine: ProjectionEngine[tuple[Event, ...]] = ProjectionEngine(
        CapturingProjection, upcasters=registry
    )

    engine.apply(make_event("e1", type="goal.created", version="1"))

    applied = engine.state[0]
    assert applied.version == "2"
    assert applied.type == "goal.opened"
    assert applied.payload.get("upcast") is True
    # Dedup still keys on the original identifier, which upcasting preserves.
    assert engine.has_seen("e1") is True


def test_upcaster_passthrough_when_not_applicable() -> None:
    registry = InMemoryUpcasterRegistry()
    registry.register(RetypingUpcaster())

    upcaster: EventUpcaster = RetypingUpcaster()
    assert isinstance(upcaster, EventUpcaster)

    engine: ProjectionEngine[tuple[str, ...]] = ProjectionEngine(
        make_projection, upcasters=registry
    )

    # A type/version the upcaster does not claim flows through unchanged.
    engine.apply(make_event("e1", type="plan.created", version="1"))

    assert engine.state == ("e1",)
    assert engine.applied_count == 1
