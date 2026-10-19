"""Unit tests for the Unit of Work (:mod:`nexus_infra.unit_of_work`).

Covers the transactional boundary: commit flushes staged events to the store and
publishes them to the bus while persisting repository writes; rollback restores
repositories and discards events; the context manager auto-rolls-back without an
explicit commit and on exceptions; commit pre-validates the whole batch atomically
(duplicate identifiers, pre-existing identifiers, stream-position conflicts) so a
failed commit lands no partial side effects; and lifecycle misuse raises
``TransactionError``. Plain pytest functions, no I/O.
"""

from __future__ import annotations

import pytest

from nexus_core.domain.event import Event
from nexus_infra import (
    ConcurrencyConflictError,
    DuplicateEventError,
    GoalRepository,
    InMemoryEventStore,
    InMemoryUnitOfWork,
    InProcessEventBus,
    TransactionError,
)
from tests.unit.nexus_infra.factories import make_event, make_goal


class RecordingHandler:
    """An event handler that records every event it receives, in order."""

    def __init__(self) -> None:
        self.received: list[Event] = []

    def handle(self, event: Event) -> None:
        self.received.append(event)


def _build_uow(
    *, with_bus: bool = False
) -> tuple[InMemoryEventStore, GoalRepository, InProcessEventBus | None, InMemoryUnitOfWork]:
    """Assemble a store, one goal repository, an optional bus, and a wired UoW."""
    store = InMemoryEventStore()
    repo = GoalRepository()
    bus = InProcessEventBus() if with_bus else None
    uow = InMemoryUnitOfWork(store, repositories=(repo,), event_bus=bus)
    return store, repo, bus, uow


# --------------------------------------------------------------------------- #
# commit
# --------------------------------------------------------------------------- #


def test_commit_appends_event_publishes_and_persists_repo_change() -> None:
    store, repo, bus, uow = _build_uow(with_bus=True)
    assert bus is not None
    handler = RecordingHandler()
    bus.subscribe(handler)

    event = make_event("evt-1")
    with uow:
        repo.add(make_goal("goal-1"))
        uow.collect(event)
        uow.commit()

    # Event appended to the store.
    assert store.global_length() == 1
    assert store.contains("evt-1") is True
    # Event published to the bus subscriber.
    assert handler.received == [event]
    # Repository change persisted.
    assert repo.get("goal-1") is not None
    # Transaction closed and drained.
    assert uow.active is False
    assert uow.pending_events == ()


def test_commit_without_a_bus_still_appends_and_persists() -> None:
    store, repo, _bus, uow = _build_uow(with_bus=False)

    with uow:
        repo.add(make_goal("goal-1"))
        uow.collect(make_event("evt-1"))
        uow.commit()

    assert store.global_length() == 1
    assert repo.contains("goal-1") is True


# --------------------------------------------------------------------------- #
# rollback
# --------------------------------------------------------------------------- #


def test_rollback_restores_repo_and_discards_events() -> None:
    store, repo, _bus, uow = _build_uow()

    uow.begin()
    repo.add(make_goal("goal-1"))
    uow.collect(make_event("evt-1"))
    assert uow.pending_events != ()

    uow.rollback()

    # Repo restored to its pre-transaction (empty) state.
    assert repo.get("goal-1") is None
    assert repo.count == 0
    # No event appended.
    assert store.global_length() == 0
    assert store.contains("evt-1") is False
    # Pending events drained, transaction closed.
    assert uow.pending_events == ()
    assert uow.active is False


def test_rollback_restores_prior_repo_contents() -> None:
    store, repo, _bus, uow = _build_uow()
    # Pre-existing state committed before the transaction under test.
    repo.add(make_goal("goal-existing"))

    uow.begin()
    repo.add(make_goal("goal-new"))
    uow.rollback()

    assert repo.contains("goal-existing") is True
    assert repo.contains("goal-new") is False
    assert repo.count == 1


# --------------------------------------------------------------------------- #
# context manager auto-rollback
# --------------------------------------------------------------------------- #


def test_context_manager_without_commit_discards_changes() -> None:
    store, repo, _bus, uow = _build_uow()

    with uow:
        repo.add(make_goal("goal-1"))
        uow.collect(make_event("evt-1"))
        # No commit() — exiting the block must roll back.

    assert repo.get("goal-1") is None
    assert store.global_length() == 0
    assert uow.active is False


def test_exception_inside_block_propagates_and_rolls_back() -> None:
    store, repo, _bus, uow = _build_uow()

    class BoomError(RuntimeError):
        pass

    with pytest.raises(BoomError):
        with uow:
            repo.add(make_goal("goal-1"))
            uow.collect(make_event("evt-1"))
            raise BoomError("explode mid-transaction")

    assert repo.get("goal-1") is None
    assert store.global_length() == 0
    assert uow.active is False


def test_context_manager_does_not_rollback_after_explicit_commit() -> None:
    store, repo, _bus, uow = _build_uow()

    with uow:
        repo.add(make_goal("goal-1"))
        uow.collect(make_event("evt-1"))
        uow.commit()

    # Committed state survives the context-manager exit.
    assert repo.contains("goal-1") is True
    assert store.global_length() == 1


# --------------------------------------------------------------------------- #
# atomic flush pre-validation
# --------------------------------------------------------------------------- #


def test_commit_with_duplicate_identifiers_in_batch_appends_nothing() -> None:
    store, repo, _bus, uow = _build_uow()

    uow.begin()
    repo.add(make_goal("goal-1"))
    uow.collect(make_event("evt-dup"))
    uow.collect(make_event("evt-dup"))

    with pytest.raises(DuplicateEventError) as excinfo:
        uow.commit()

    assert excinfo.value.identifier == "evt-dup"
    # Atomicity: nothing appended despite the first event being individually valid.
    assert store.global_length() == 0
    # Transaction remains active (commit did not finish), so we can roll back cleanly.
    assert uow.active is True
    uow.rollback()
    assert repo.contains("goal-1") is False


def test_commit_with_preexisting_identifier_leaves_store_unchanged() -> None:
    store, repo, _bus, uow = _build_uow()
    # An event already in the store before the transaction.
    store.append(make_event("evt-existing"))
    assert store.global_length() == 1

    uow.begin()
    uow.collect(make_event("evt-existing", payload={"different": "content"}))

    with pytest.raises(DuplicateEventError) as excinfo:
        uow.commit()

    assert excinfo.value.identifier == "evt-existing"
    # Store unchanged beyond the pre-existing event.
    assert store.global_length() == 1


def test_commit_with_wrong_stream_position_raises_and_appends_nothing() -> None:
    store, repo, _bus, uow = _build_uow()

    uow.begin()
    # sequence_position 5 on an empty stream (expected position 0) is a conflict.
    uow.collect(make_event("evt-1", correlation_identifier="stream-a", sequence_position=5))

    with pytest.raises(ConcurrencyConflictError) as excinfo:
        uow.commit()

    error = excinfo.value
    assert error.stream == "stream-a"
    assert error.expected == 5
    assert error.actual == 0
    assert store.global_length() == 0


# --------------------------------------------------------------------------- #
# transaction lifecycle errors
# --------------------------------------------------------------------------- #


def test_collect_without_active_transaction_raises() -> None:
    _store, _repo, _bus, uow = _build_uow()

    with pytest.raises(TransactionError):
        uow.collect(make_event("evt-1"))


def test_commit_without_active_transaction_raises() -> None:
    _store, _repo, _bus, uow = _build_uow()

    with pytest.raises(TransactionError):
        uow.commit()


def test_rollback_without_active_transaction_raises() -> None:
    _store, _repo, _bus, uow = _build_uow()

    with pytest.raises(TransactionError):
        uow.rollback()


def test_begin_twice_raises() -> None:
    _store, _repo, _bus, uow = _build_uow()
    uow.begin()

    with pytest.raises(TransactionError):
        uow.begin()


# --------------------------------------------------------------------------- #
# active / pending_events properties across the lifecycle
# --------------------------------------------------------------------------- #


def test_active_and_pending_events_track_the_lifecycle() -> None:
    _store, repo, _bus, uow = _build_uow()

    assert uow.active is False
    assert uow.pending_events == ()

    uow.begin()
    assert uow.active is True
    assert uow.pending_events == ()

    e1 = make_event("evt-1")
    e2 = make_event("evt-2")
    uow.collect(e1)
    uow.collect(e2)
    assert uow.pending_events == (e1, e2)

    uow.commit()
    assert uow.active is False
    assert uow.pending_events == ()


def test_pending_events_cleared_after_rollback() -> None:
    _store, _repo, _bus, uow = _build_uow()

    uow.begin()
    uow.collect(make_event("evt-1"))
    assert uow.pending_events != ()

    uow.rollback()
    assert uow.pending_events == ()
    assert uow.active is False
