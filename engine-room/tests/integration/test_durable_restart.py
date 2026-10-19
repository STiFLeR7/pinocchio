"""Integration tests for the durable substrate (ADR-007) — the P1 acceptance gate.

Exercises :func:`build_durable_infrastructure` end-to-end and proves the guarantees
durability exists to provide:

- **Restart preserves history:** a fresh context on the same file sees every event.
- **Replay reconstructs projections identically** (INV-14), including after restart.
- **Deterministic replay:** identical input → identical projected state.
- **Ordering preserved** across restart.
- **Snapshot + tail replay == full replay** (ADR-001 / INV-18), durably.

No engine is involved — only the substrate — so these mirror the in-memory
``test_composition.py`` guarantees against the durable backend.
"""

from __future__ import annotations

from nexus_core.domain.event import Event
from nexus_infra import (
    DeterministicIdentifierFactory,
    InfrastructureContext,
    ProjectionEngine,
    build_durable_infrastructure,
)


class IdentifierProjection:
    """A projection whose state is the ordered tuple of applied event identifiers."""

    def __init__(self, seed: tuple[str, ...] = ()) -> None:
        self._applied: list[str] = list(seed)

    def apply(self, event: Event) -> None:
        self._applied.append(event.identifier)

    @property
    def state(self) -> tuple[str, ...]:
        return tuple(self._applied)


def _emit(ctx: InfrastructureContext, count: int, *, correlation: str | None = None) -> list[Event]:
    correlation = correlation or ctx.identifiers.new_correlation_identifier()
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


def test_restart_preserves_history(tmp_path) -> None:
    db = str(tmp_path / "infra.db")
    ctx = build_durable_infrastructure(db, identifiers=DeterministicIdentifierFactory())
    emitted = _emit(ctx, 5)
    assert ctx.event_store.global_length() == 5

    # "Restart": a brand-new context and SQLite connection on the same file.
    reopened = build_durable_infrastructure(db)
    assert reopened.event_store.global_length() == 5
    assert tuple(e.identifier for e in reopened.event_store.read_all()) == tuple(
        e.identifier for e in emitted
    )


def test_replay_reconstructs_projection_after_restart(tmp_path) -> None:
    db = str(tmp_path / "infra.db")
    ctx = build_durable_infrastructure(db, identifiers=DeterministicIdentifierFactory())
    live = ctx.projection_engine(IdentifierProjection)
    ctx.event_bus.subscribe(live)
    emitted = _emit(ctx, 6)

    reopened = build_durable_infrastructure(db)
    replayed = reopened.projection_engine(IdentifierProjection)
    replayed.rebuild(reopened.event_store.read_all())

    assert replayed.state == live.state
    assert replayed.state == tuple(e.identifier for e in emitted)


def test_identical_input_gives_identical_replay(tmp_path) -> None:
    db = str(tmp_path / "infra.db")
    ctx = build_durable_infrastructure(db, identifiers=DeterministicIdentifierFactory())
    _emit(ctx, 7)

    first = ctx.projection_engine(IdentifierProjection)
    first.rebuild(ctx.event_store.read_all())
    second = ctx.projection_engine(IdentifierProjection)
    second.rebuild(ctx.event_store.read_all())

    assert first.state == second.state


def test_global_ordering_preserved_across_restart(tmp_path) -> None:
    db = str(tmp_path / "infra.db")
    ctx = build_durable_infrastructure(db, identifiers=DeterministicIdentifierFactory())
    # Interleave two correlation streams to exercise global vs per-stream order.
    a = _emit(ctx, 2, correlation="cor-a")
    b = _emit(ctx, 2, correlation="cor-b")
    expected_global = [a[0], a[1], b[0], b[1]]

    reopened = build_durable_infrastructure(db)
    assert [e.identifier for e in reopened.event_store.read_all()] == [
        e.identifier for e in expected_global
    ]
    assert [e.identifier for e in reopened.event_store.read_stream("cor-a")] == [
        e.identifier for e in a
    ]


def test_snapshot_restore_plus_tail_equals_full_replay(tmp_path) -> None:
    db = str(tmp_path / "infra.db")
    ctx = build_durable_infrastructure(db, identifiers=DeterministicIdentifierFactory())
    live = ctx.projection_engine(IdentifierProjection)
    ctx.event_bus.subscribe(live)

    _emit(ctx, 3)
    snapshot_position = ctx.event_store.global_length()
    snapshot = ctx.snapshot_store.create(
        identifier="snap-1",
        key="identifier-projection",
        state=live.state,
        log_position=snapshot_position,
    )
    _emit(ctx, 4)  # the tail

    full = ctx.projection_engine(IdentifierProjection)
    full.rebuild(ctx.event_store.read_all())

    restored_state = ctx.snapshot_store.restore(snapshot.identifier)
    seeded = ProjectionEngine(lambda: IdentifierProjection(seed=tuple(restored_state)))
    seeded.consume(ctx.event_store.read_from(snapshot_position + 1))

    assert seeded.state == full.state


def test_idempotent_append_across_restart(tmp_path) -> None:
    # ADR-007 / INV-16: re-appending an identical event after restart is a no-op.
    db = str(tmp_path / "infra.db")
    ctx = build_durable_infrastructure(db, identifiers=DeterministicIdentifierFactory())
    [event] = _emit(ctx, 1)
    assert ctx.event_store.global_length() == 1

    reopened = build_durable_infrastructure(db)
    reopened.event_store.append(event)  # same identifier + content
    assert reopened.event_store.global_length() == 1


def test_unit_of_work_commit_survives_restart(tmp_path) -> None:
    db = str(tmp_path / "infra.db")
    ctx = build_durable_infrastructure(db)
    from tests.unit.nexus_infra.factories import make_event, make_goal

    with ctx.unit_of_work() as uow:
        ctx.goals.add(make_goal("goal-1"))
        uow.collect(make_event("evt-1"))
        uow.commit()

    reopened = build_durable_infrastructure(db)
    assert reopened.event_store.contains("evt-1") is True
    assert reopened.goals.get("goal-1") == make_goal("goal-1")
