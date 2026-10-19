"""Durable Unit-of-Work tests (:class:`nexus_infra.durable.DurableUnitOfWork`).

Mirrors ``test_unit_of_work.py`` against the SQLite-backed store/repo sharing one
connection. ``commit`` is one real SQLite transaction (ADR-007): a failed
pre-validation appends nothing and leaves the transaction open for a clean
rollback; events publish only after the durable commit.
"""

from __future__ import annotations

import pytest

from nexus_core.domain.event import Event
from nexus_infra import (
    ConcurrencyConflictError,
    DuplicateEventError,
    DurableEventStore,
    DurableGoalRepository,
    DurableUnitOfWork,
    InProcessEventBus,
    TransactionError,
    connect,
)
from tests.unit.nexus_infra.factories import make_event, make_goal


class RecordingHandler:
    def __init__(self) -> None:
        self.received: list[Event] = []

    def handle(self, event: Event) -> None:
        self.received.append(event)


def _build(tmp_path, *, with_bus: bool = False):
    conn = connect(str(tmp_path / "uow.db"))
    store = DurableEventStore(conn)
    repo = DurableGoalRepository(conn)
    bus = InProcessEventBus() if with_bus else None
    uow = DurableUnitOfWork(conn, store, (repo,), bus)
    return store, repo, bus, uow


# -- commit ------------------------------------------------------------------ #


def test_commit_appends_publishes_and_persists(tmp_path) -> None:
    store, repo, bus, uow = _build(tmp_path, with_bus=True)
    handler = RecordingHandler()
    bus.subscribe(handler)

    event = make_event("evt-1")
    with uow:
        repo.add(make_goal("goal-1"))
        uow.collect(event)
        uow.commit()

    assert store.global_length() == 1
    assert store.contains("evt-1") is True
    assert handler.received == [event]
    assert repo.get("goal-1") is not None
    assert uow.active is False
    assert uow.pending_events == ()


def test_commit_without_a_bus_still_persists(tmp_path) -> None:
    store, repo, _bus, uow = _build(tmp_path)
    with uow:
        repo.add(make_goal("goal-1"))
        uow.collect(make_event("evt-1"))
        uow.commit()
    assert store.global_length() == 1
    assert repo.contains("goal-1") is True


# -- rollback (real SQL ROLLBACK) -------------------------------------------- #


def test_rollback_restores_repo_and_discards_events(tmp_path) -> None:
    store, repo, _bus, uow = _build(tmp_path)
    uow.begin()
    repo.add(make_goal("goal-1"))
    uow.collect(make_event("evt-1"))
    uow.rollback()

    assert repo.get("goal-1") is None
    assert repo.count == 0
    assert store.global_length() == 0
    assert uow.pending_events == ()
    assert uow.active is False


def test_rollback_restores_prior_committed_contents(tmp_path) -> None:
    _store, repo, _bus, uow = _build(tmp_path)
    repo.add(make_goal("goal-existing"))  # committed before the transaction (autocommit)

    uow.begin()
    repo.add(make_goal("goal-new"))
    uow.rollback()

    assert repo.contains("goal-existing") is True
    assert repo.contains("goal-new") is False
    assert repo.count == 1


def test_context_manager_without_commit_rolls_back(tmp_path) -> None:
    store, repo, _bus, uow = _build(tmp_path)
    with uow:
        repo.add(make_goal("goal-1"))
        uow.collect(make_event("evt-1"))
    assert repo.get("goal-1") is None
    assert store.global_length() == 0
    assert uow.active is False


def test_exception_inside_block_rolls_back(tmp_path) -> None:
    store, repo, _bus, uow = _build(tmp_path)

    class BoomError(RuntimeError):
        pass

    with pytest.raises(BoomError):
        with uow:
            repo.add(make_goal("goal-1"))
            uow.collect(make_event("evt-1"))
            raise BoomError("explode")

    assert repo.get("goal-1") is None
    assert store.global_length() == 0
    assert uow.active is False


# -- atomic pre-validation --------------------------------------------------- #


def test_duplicate_identifiers_in_batch_append_nothing(tmp_path) -> None:
    store, repo, _bus, uow = _build(tmp_path)
    uow.begin()
    repo.add(make_goal("goal-1"))
    uow.collect(make_event("evt-dup"))
    uow.collect(make_event("evt-dup"))

    with pytest.raises(DuplicateEventError) as excinfo:
        uow.commit()
    assert excinfo.value.identifier == "evt-dup"
    assert store.global_length() == 0
    assert uow.active is True
    uow.rollback()
    assert repo.contains("goal-1") is False


def test_preexisting_identifier_leaves_store_unchanged(tmp_path) -> None:
    store, _repo, _bus, uow = _build(tmp_path)
    store.append(make_event("evt-existing"))
    assert store.global_length() == 1

    uow.begin()
    uow.collect(make_event("evt-existing", payload={"different": "content"}))
    with pytest.raises(DuplicateEventError) as excinfo:
        uow.commit()
    assert excinfo.value.identifier == "evt-existing"
    assert store.global_length() == 1
    uow.rollback()


def test_wrong_stream_position_appends_nothing(tmp_path) -> None:
    store, _repo, _bus, uow = _build(tmp_path)
    uow.begin()
    uow.collect(make_event("evt-1", correlation_identifier="stream-a", sequence_position=5))

    with pytest.raises(ConcurrencyConflictError) as excinfo:
        uow.commit()
    err = excinfo.value
    assert (err.stream, err.expected, err.actual) == ("stream-a", 5, 0)
    assert store.global_length() == 0
    uow.rollback()


# -- lifecycle errors -------------------------------------------------------- #


def test_lifecycle_errors(tmp_path) -> None:
    _store, _repo, _bus, uow = _build(tmp_path)
    with pytest.raises(TransactionError):
        uow.collect(make_event("evt-1"))
    with pytest.raises(TransactionError):
        uow.commit()
    with pytest.raises(TransactionError):
        uow.rollback()
    uow.begin()
    with pytest.raises(TransactionError):
        uow.begin()
    uow.rollback()


def test_active_and_pending_track_lifecycle(tmp_path) -> None:
    _store, _repo, _bus, uow = _build(tmp_path)
    assert uow.active is False
    assert uow.pending_events == ()

    uow.begin()
    assert uow.active is True
    e1, e2 = make_event("evt-1"), make_event("evt-2")
    uow.collect(e1)
    uow.collect(e2)
    assert uow.pending_events == (e1, e2)

    uow.commit()
    assert uow.active is False
    assert uow.pending_events == ()
