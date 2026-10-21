"""Integration tests for :mod:`nexus_infra.composition`.

:func:`build_infrastructure` wires the whole substrate into one replaceable
:class:`InfrastructureContext` with **no global state**. These tests verify the
wiring, the ``EventEmitter`` behavior of ``emit`` (append-then-publish), and the
end-to-end event-sourcing guarantees that the substrate exists to provide:

- **Replay equivalence (INV-14):** a fresh projection rebuilt from the
  authoritative log reproduces the live projection's state exactly.
- **Snapshot + tail replay (ADR-001 / INV-18):** restoring the nearest snapshot
  and replaying only the tail equals a full replay from the whole log.
"""

from __future__ import annotations

import gc
import sqlite3

import pytest

from nexus_core.domain.event import Event
from nexus_infra import (
    DeterministicIdentifierFactory,
    InfrastructureContext,
    InMemoryObservability,
    InMemoryUnitOfWork,
    ProjectionEngine,
    build_durable_infrastructure,
    build_infrastructure,
)

# -- test doubles ------------------------------------------------------------ #


class IdentifierProjection:
    """A :class:`Projection` whose state is the ordered tuple of applied identifiers.

    Optionally seeded with a prior state (used to model snapshot restoration: a
    fresh projection initialized from a restored snapshot, then folding the tail).
    """

    def __init__(self, seed: tuple[str, ...] = ()) -> None:
        self._applied: list[str] = list(seed)

    def apply(self, event: Event) -> None:
        self._applied.append(event.identifier)

    @property
    def state(self) -> tuple[str, ...]:
        return tuple(self._applied)


class RecordingHandler:
    """An ``EventHandler`` that records every delivered event identifier."""

    def __init__(self) -> None:
        self.received: list[str] = []

    def handle(self, event: Event) -> None:
        self.received.append(event.identifier)


def _emit_events(ctx: InfrastructureContext, count: int) -> list[Event]:
    """Emit ``count`` events on a single correlation, returning them in order."""
    correlation = ctx.identifiers.new_correlation_identifier()
    emitted: list[Event] = []
    for _ in range(count):
        event = Event(
            identifier=ctx.identifiers.new_event_identifier(),
            type="goal.created",
            version="1",
            timestamp="2026-01-01T00:00:00Z",
            producer="intent_resolution",
            correlation_identifier=correlation,
            execution_identifier=None,
            payload={},
            source="test",
        )
        ctx.emit(event)
        emitted.append(event)
    return emitted


# -- wiring ------------------------------------------------------------------ #


def test_build_infrastructure_wires_all_components() -> None:
    ctx = build_infrastructure()

    assert ctx.event_store is not None
    assert ctx.event_bus is not None
    assert ctx.snapshot_store is not None
    assert ctx.serializer is not None
    assert ctx.upcasters is not None
    assert ctx.identifiers is not None
    assert ctx.clock is not None
    assert ctx.observability is not None
    assert ctx.repositories() == (
        ctx.goals,
        ctx.plans,
        ctx.artifacts,
        ctx.policies,
        ctx.knowledge,
    )


def test_repositories_returns_five_repos() -> None:
    ctx = build_infrastructure()

    assert len(ctx.repositories()) == 5


def test_no_global_state_between_contexts() -> None:
    first = build_infrastructure()
    second = build_infrastructure()

    _emit_events(first, 3)

    assert first.event_store.global_length() == 3
    assert second.event_store.global_length() == 0
    # The two contexts share no component instances.
    assert first.event_store is not second.event_store
    assert first.event_bus is not second.event_bus


def test_durable_connection_lives_with_components_and_closes_when_released(tmp_path) -> None:
    context = build_durable_infrastructure(str(tmp_path / "owned.db"))
    event_store = context.event_store

    del context
    gc.collect()
    assert event_store.global_length() == 0

    del event_store
    gc.collect()


def test_durable_context_close_closes_shared_connection(tmp_path) -> None:
    context = build_durable_infrastructure(str(tmp_path / "explicit-close.db"))
    event_store = context.event_store

    context.close()

    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        event_store.global_length()


# -- emit (EventEmitter) ----------------------------------------------------- #


def test_emit_appends_to_log_and_publishes_to_bus() -> None:
    ctx = build_infrastructure(identifiers=DeterministicIdentifierFactory())
    handler = RecordingHandler()
    ctx.event_bus.subscribe(handler)

    [event] = _emit_events(ctx, 1)

    # Appended to the authoritative log.
    assert ctx.event_store.global_length() == 1
    assert ctx.event_store.contains(event.identifier) is True
    # Published to the bus.
    assert handler.received == [event.identifier]


def test_emit_publishes_to_all_subscribers_in_order() -> None:
    ctx = build_infrastructure(identifiers=DeterministicIdentifierFactory())
    handler = RecordingHandler()
    ctx.event_bus.subscribe(handler)

    emitted = _emit_events(ctx, 3)

    assert handler.received == [e.identifier for e in emitted]


# -- unit of work ------------------------------------------------------------ #


def test_unit_of_work_returns_bound_working_uow() -> None:
    ctx = build_infrastructure()

    uow = ctx.unit_of_work()

    assert isinstance(uow, InMemoryUnitOfWork)
    # It is usable as a transactional boundary.
    with uow:
        uow.commit()


# -- projection engine ------------------------------------------------------- #


def test_projection_engine_is_wired_with_context_collaborators() -> None:
    obs = InMemoryObservability()
    ctx = build_infrastructure(observability=obs)

    engine = ctx.projection_engine(IdentifierProjection)

    assert isinstance(engine, ProjectionEngine)
    engine.apply(_emit_events(ctx, 1)[0])
    # Wired with this context's observability sink.
    assert obs.counters.get("projection.applied") == 1


# -- end-to-end replay + snapshot (the key integration test) ----------------- #


def test_live_projection_folds_emitted_events_in_order() -> None:
    ctx = build_infrastructure(identifiers=DeterministicIdentifierFactory())
    live = ctx.projection_engine(IdentifierProjection)
    ctx.event_bus.subscribe(live)

    emitted = _emit_events(ctx, 4)

    assert live.state == tuple(e.identifier for e in emitted)


def test_replay_from_log_equals_live_projection() -> None:
    # INV-14: deterministic reconstruction from the authoritative log.
    ctx = build_infrastructure(identifiers=DeterministicIdentifierFactory())
    live = ctx.projection_engine(IdentifierProjection)
    ctx.event_bus.subscribe(live)

    _emit_events(ctx, 5)

    replayed = ctx.projection_engine(IdentifierProjection)
    replayed.rebuild(ctx.event_store.read_all())

    assert replayed.state == live.state


def test_snapshot_restore_plus_tail_replay_equals_full_replay() -> None:
    # ADR-001 / INV-18: restore nearest snapshot + replay tail == full replay.
    ctx = build_infrastructure(identifiers=DeterministicIdentifierFactory())
    live = ctx.projection_engine(IdentifierProjection)
    ctx.event_bus.subscribe(live)

    # Emit an initial batch, then snapshot the live state at the current position.
    _emit_events(ctx, 3)
    snapshot_position = ctx.event_store.global_length()
    snapshot = ctx.snapshot_store.create(
        identifier="snap-1",
        key="identifier-projection",
        state=live.state,
        log_position=snapshot_position,
    )

    # Emit more events after the snapshot (the "tail").
    _emit_events(ctx, 4)

    # Full replay from the whole log is the source of truth.
    full = ctx.projection_engine(IdentifierProjection)
    full.rebuild(ctx.event_store.read_all())

    # Reconstruct: restore the snapshot, seed a fresh projection with it, then
    # replay only the tail after the snapshot position.
    restored_state = ctx.snapshot_store.restore(snapshot.identifier)
    seeded = ProjectionEngine(lambda: IdentifierProjection(seed=restored_state))
    seeded.consume(ctx.event_store.read_from(snapshot_position + 1))

    assert seeded.state == full.state
