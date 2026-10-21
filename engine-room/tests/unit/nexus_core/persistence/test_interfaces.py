"""Unit tests for the persistence Protocols via in-memory fakes."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import TracebackType
from typing import Any

from pydantic import BaseModel

from nexus_core.contracts.base import Constraint, Correlation
from nexus_core.contracts.enums import Domain, InterpretationConfidence, Priority
from nexus_core.contracts.status import GoalStatus
from nexus_core.domain.event import Event
from nexus_core.domain.goal import Goal, Scope
from nexus_core.persistence.interfaces import (
    EventStore,
    Projection,
    Repository,
    Serializer,
    Snapshot,
    UnitOfWork,
)

# --------------------------------------------------------------------------- #
# Builders                                                                     #
# --------------------------------------------------------------------------- #


def _build_goal(identity: str = "goal-1") -> Goal:
    return Goal(
        identity=identity,
        outcome="The release notes are published.",
        domain=Domain.SOFTWARE,
        priority=Priority.HIGH,
        confidence=InterpretationConfidence.HIGH,
        constraints=(Constraint(kind="deadline", detail={"by": "2026-07-01"}),),
        scope=Scope(included=("notes",), excluded=("marketing",)),
        correlation=Correlation(correlation_identifier="corr-1"),
        status=GoalStatus.NORMALIZED,
    )


def _build_event(
    identifier: str = "evt-1",
    correlation_identifier: str = "corr-1",
) -> Event:
    return Event(
        identifier=identifier,
        type="goal.created",
        version="1.0.0",
        timestamp="2026-06-29T00:00:00Z",
        producer="intent",
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload={"goal": "goal-1"},
        source="cli",
    )


# --------------------------------------------------------------------------- #
# Fakes                                                                        #
# --------------------------------------------------------------------------- #


class DictSerializer:
    """A model-dump-backed serializer; the wire format is a plain dict."""

    def serialize(self, obj: BaseModel) -> Mapping[str, Any]:
        return obj.model_dump()

    def deserialize[M: BaseModel](self, model_type: type[M], data: Mapping[str, Any]) -> M:
        return model_type.model_validate(dict(data))


class GoalRepository:
    def __init__(self) -> None:
        self._items: dict[str, Goal] = {}

    def get(self, identifier: str) -> Goal | None:
        return self._items.get(identifier)

    def add(self, obj: Goal) -> None:
        self._items[obj.identity] = obj

    def list_all(self) -> tuple[Goal, ...]:
        return tuple(self._items.values())


class InMemoryEventStore:
    def __init__(self) -> None:
        self._events: list[Event] = []

    def append(self, event: Event) -> None:
        self._events.append(event)

    def read_stream(self, correlation_identifier: str) -> Iterable[Event]:
        return tuple(e for e in self._events if e.correlation_identifier == correlation_identifier)

    def read_all(self) -> Iterable[Event]:
        return tuple(self._events)


class CountingProjection:
    """Folds the event log into a count of applied events, deduped by identifier."""

    def __init__(self) -> None:
        self._seen: set[str] = set()
        self._count = 0

    def apply(self, event: Event) -> None:
        if event.identifier in self._seen:
            return
        self._seen.add(event.identifier)
        self._count += 1

    @property
    def state(self) -> int:
        return self._count

    def set_count(self, value: int) -> None:
        self._count = value


class CounterSnapshot:
    def __init__(self, projection: CountingProjection) -> None:
        self._projection = projection

    def capture(self) -> int:
        return self._projection.state

    def restore(self, state: int) -> None:
        self._projection.set_count(state)


class InMemoryUnitOfWork:
    def __init__(self, repository: GoalRepository) -> None:
        self._repository = repository
        self._pending: list[Goal] = []
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> InMemoryUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if exc_type is not None and not self.committed:
            self.rollback()
        return None

    def stage(self, goal: Goal) -> None:
        self._pending.append(goal)

    def commit(self) -> None:
        for goal in self._pending:
            self._repository.add(goal)
        self._pending.clear()
        self.committed = True

    def rollback(self) -> None:
        self._pending.clear()
        self.rolled_back = True


# --------------------------------------------------------------------------- #
# Protocol conformance                                                        #
# --------------------------------------------------------------------------- #


def test_fakes_satisfy_runtime_checkable_protocols() -> None:
    repo = GoalRepository()
    projection = CountingProjection()
    assert isinstance(DictSerializer(), Serializer)
    assert isinstance(repo, Repository)
    assert isinstance(InMemoryEventStore(), EventStore)
    assert isinstance(projection, Projection)
    assert isinstance(CounterSnapshot(projection), Snapshot)
    assert isinstance(InMemoryUnitOfWork(repo), UnitOfWork)


# --------------------------------------------------------------------------- #
# Behaviour                                                                    #
# --------------------------------------------------------------------------- #


def test_serializer_round_trip_is_identity_preserving() -> None:
    serializer = DictSerializer()
    goal = _build_goal()
    data = serializer.serialize(goal)
    assert serializer.deserialize(Goal, data) == goal


def test_event_store_appends_and_reads_stream_by_correlation() -> None:
    store = InMemoryEventStore()
    e1 = _build_event(identifier="evt-1", correlation_identifier="corr-1")
    e2 = _build_event(identifier="evt-2", correlation_identifier="corr-2")
    e3 = _build_event(identifier="evt-3", correlation_identifier="corr-1")
    store.append(e1)
    store.append(e2)
    store.append(e3)
    assert tuple(store.read_stream("corr-1")) == (e1, e3)
    assert tuple(store.read_stream("corr-2")) == (e2,)
    assert tuple(store.read_all()) == (e1, e2, e3)


def test_repository_add_get_list() -> None:
    repo = GoalRepository()
    goal = _build_goal()
    repo.add(goal)
    assert repo.get("goal-1") == goal
    assert repo.get("absent") is None
    assert repo.list_all() == (goal,)


def test_projection_folds_events_into_counter() -> None:
    projection = CountingProjection()
    projection.apply(_build_event(identifier="evt-1"))
    projection.apply(_build_event(identifier="evt-2"))
    assert projection.state == 2
    # Duplicate delivery is idempotent (INV-16).
    projection.apply(_build_event(identifier="evt-1"))
    assert projection.state == 2


def test_snapshot_capture_and_restore() -> None:
    projection = CountingProjection()
    projection.apply(_build_event(identifier="evt-1"))
    projection.apply(_build_event(identifier="evt-2"))
    snapshot = CounterSnapshot(projection)
    captured = snapshot.capture()
    assert captured == 2

    projection.apply(_build_event(identifier="evt-3"))
    assert projection.state == 3

    snapshot.restore(captured)
    assert projection.state == 2


def test_unit_of_work_commit() -> None:
    repo = GoalRepository()
    goal = _build_goal()
    with InMemoryUnitOfWork(repo) as uow:
        uow.stage(goal)
        assert repo.get("goal-1") is None  # not yet durable
        uow.commit()
    assert uow.committed is True
    assert repo.get("goal-1") == goal


def test_unit_of_work_rolls_back_on_exception() -> None:
    repo = GoalRepository()
    goal = _build_goal()
    try:
        with InMemoryUnitOfWork(repo) as uow:
            uow.stage(goal)
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert uow.rolled_back is True
    assert repo.get("goal-1") is None
