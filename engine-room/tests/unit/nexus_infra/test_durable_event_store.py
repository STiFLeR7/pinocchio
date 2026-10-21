"""Durable event-store parity tests (:class:`nexus_infra.durable.DurableEventStore`).

Mirrors the semantic contract of ``test_event_store.py`` against the SQLite-backed
store. The one physical difference (ADR-007): a durable read reconstructs a
*value-equal* Event from storage rather than the same instance, so assertions use
value equality (``==``) where the in-memory suite used identity — every ordering,
position, idempotency, concurrency, tail-replay, and observability behavior is
otherwise identical.
"""

from __future__ import annotations

import pytest

from nexus_infra import (
    ConcurrencyConflictError,
    DuplicateEventError,
    DurableEventStore,
    InMemoryObservability,
    StoredEvent,
    connect,
)
from nexus_infra.event_store import NO_EXPECTATION
from nexus_infra.observability import InfraEventType
from tests.unit.nexus_infra.factories import make_event


@pytest.fixture
def store(tmp_path) -> DurableEventStore:
    return DurableEventStore(connect(str(tmp_path / "events.db")))


# -- ordering ---------------------------------------------------------------- #


def test_read_all_returns_events_in_global_append_order(store: DurableEventStore) -> None:
    e1 = make_event("evt-1", correlation_identifier="cor-a")
    e2 = make_event("evt-2", correlation_identifier="cor-b")
    e3 = make_event("evt-3", correlation_identifier="cor-a")
    store.append(e1)
    store.append(e2)
    store.append(e3)

    assert tuple(store.read_all()) == (e1, e2, e3)


def test_read_stream_returns_only_that_correlation_in_order(store: DurableEventStore) -> None:
    a1 = make_event("a1", correlation_identifier="cor-a")
    b1 = make_event("b1", correlation_identifier="cor-b")
    a2 = make_event("a2", correlation_identifier="cor-a")
    store.append(a1)
    store.append(b1)
    store.append(a2)

    assert tuple(store.read_stream("cor-a")) == (a1, a2)
    assert tuple(store.read_stream("cor-b")) == (b1,)
    assert tuple(store.read_stream("missing")) == ()


def test_read_all_empty_store_is_empty(store: DurableEventStore) -> None:
    assert tuple(store.read_all()) == ()


# -- positions --------------------------------------------------------------- #


def test_positions_and_global_sequence(store: DurableEventStore) -> None:
    a1 = store.append_expecting(make_event("a1", correlation_identifier="cor-a"), NO_EXPECTATION)
    b1 = store.append_expecting(make_event("b1", correlation_identifier="cor-b"), NO_EXPECTATION)
    a2 = store.append_expecting(make_event("a2", correlation_identifier="cor-a"), NO_EXPECTATION)

    assert isinstance(a1, StoredEvent)
    assert (a1.global_sequence, b1.global_sequence, a2.global_sequence) == (1, 2, 3)
    assert (a1.stream_position, a2.stream_position) == (0, 1)
    assert b1.stream_position == 0


def test_read_all_stored_returns_records_in_global_order(store: DurableEventStore) -> None:
    store.append(make_event("evt-1", correlation_identifier="cor-a"))
    store.append(make_event("evt-2", correlation_identifier="cor-b"))

    stored = store.read_all_stored()
    assert tuple(s.event.identifier for s in stored) == ("evt-1", "evt-2")
    assert tuple(s.global_sequence for s in stored) == (1, 2)


# -- idempotency / duplicates ------------------------------------------------ #


def test_appending_identical_event_twice_is_a_noop() -> None:
    obs = InMemoryObservability()
    store = DurableEventStore(_mem(), observability=obs)
    store.append(make_event("evt-1", correlation_identifier="cor-a", payload={"k": "v"}))
    store.append(make_event("evt-1", correlation_identifier="cor-a", payload={"k": "v"}))

    assert store.global_length() == 1
    assert store.stream_version("cor-a") == 1
    ignored = obs.events_of(InfraEventType.EVENT_DUPLICATE_IGNORED)
    assert len(ignored) == 1
    assert ignored[0].subject == "evt-1"
    assert ignored[0].at_sequence == 1


def test_idempotent_append_returns_equal_stored_event(store: DurableEventStore) -> None:
    event = make_event("evt-1", correlation_identifier="cor-a")
    first = store.append_expecting(event, NO_EXPECTATION)
    again = store.append_expecting(event, NO_EXPECTATION)

    assert again == first
    assert again.global_sequence == 1


def test_duplicate_identifier_with_different_content_raises(store: DurableEventStore) -> None:
    store.append(make_event("evt-1", payload={"k": "v1"}))

    with pytest.raises(DuplicateEventError) as excinfo:
        store.append(make_event("evt-1", payload={"k": "v2"}))
    assert excinfo.value.identifier == "evt-1"

    # The log is unchanged.
    assert store.global_length() == 1
    assert next(iter(store.read_all())).payload == {"k": "v1"}


# -- optimistic concurrency -------------------------------------------------- #


def test_append_expecting_matches_and_conflicts(store: DurableEventStore) -> None:
    store.append_expecting(make_event("evt-1", correlation_identifier="cor-a"), 0)

    with pytest.raises(ConcurrencyConflictError) as excinfo:
        store.append_expecting(make_event("evt-2", correlation_identifier="cor-a"), 0)
    err = excinfo.value
    assert (err.stream, err.expected, err.actual) == ("cor-a", 0, 1)
    # Conflict appended nothing.
    assert store.global_length() == 1
    assert store.stream_version("cor-a") == 1


def test_sequence_position_drives_concurrency(store: DurableEventStore) -> None:
    with pytest.raises(ConcurrencyConflictError):
        store.append(make_event("evt-1", correlation_identifier="cor-a", sequence_position=1))
    store.append(make_event("evt-1", correlation_identifier="cor-a", sequence_position=0))
    store.append(make_event("evt-2", correlation_identifier="cor-a", sequence_position=1))
    assert store.stream_version("cor-a") == 2


# -- tail replay ------------------------------------------------------------- #


def test_read_from_tail_and_bounds(store: DurableEventStore) -> None:
    e1 = make_event("evt-1", correlation_identifier="cor-a")
    e2 = make_event("evt-2", correlation_identifier="cor-b")
    e3 = make_event("evt-3", correlation_identifier="cor-a")
    for e in (e1, e2, e3):
        store.append(e)

    assert tuple(store.read_from(1)) == (e1, e2, e3)
    assert tuple(store.read_from(2)) == (e2, e3)
    assert tuple(store.read_from(4)) == ()
    with pytest.raises(ValueError):
        store.read_from(0)
    with pytest.raises(ValueError):
        store.read_from(-1)


# -- query API + observability ----------------------------------------------- #


def test_query_api(store: DurableEventStore) -> None:
    store.append(make_event("a1", correlation_identifier="cor-a"))
    store.append(make_event("a2", correlation_identifier="cor-a"))
    store.append(make_event("b1", correlation_identifier="cor-b"))

    assert store.stream_version("cor-a") == 2
    assert store.stream_version("unknown") == 0
    assert store.global_length() == 3
    assert store.contains("a1") is True
    assert store.contains("never") is False


def test_observability_counters() -> None:
    obs = InMemoryObservability()
    store = DurableEventStore(_mem(), observability=obs)
    store.append_expecting(make_event("evt-1", correlation_identifier="cor-a"), 0)
    with pytest.raises(ConcurrencyConflictError):
        store.append_expecting(make_event("evt-2", correlation_identifier="cor-a"), 0)

    assert obs.counters["event_store.appended"] == 1
    assert obs.counters["event_store.concurrency_conflict"] == 1
    appended = obs.events_of(InfraEventType.EVENT_APPENDED)
    assert appended[0].detail == {"type": "goal.created", "stream": "cor-a"}


def _mem():
    """An in-memory SQLite connection (fast, isolated) for observability tests."""
    return connect(":memory:")
