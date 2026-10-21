"""Unit tests for the append-only event store (:mod:`nexus_infra.event_store`).

Covers append/read ordering, ``StoredEvent`` position assignment, idempotent
append, duplicate detection, optimistic concurrency, tail replay, the small
query API, and observability instrumentation. Plain pytest functions, no I/O.
"""

from __future__ import annotations

import pytest

from nexus_infra import (
    ConcurrencyConflictError,
    DuplicateEventError,
    InMemoryEventStore,
    InMemoryObservability,
    StoredEvent,
)
from nexus_infra.event_store import NO_EXPECTATION
from nexus_infra.observability import InfraEventType
from tests.unit.nexus_infra.factories import make_event

# --------------------------------------------------------------------------- #
# append / read ordering
# --------------------------------------------------------------------------- #


def test_read_all_returns_events_in_global_append_order() -> None:
    store = InMemoryEventStore()
    e1 = make_event("evt-1", correlation_identifier="cor-a")
    e2 = make_event("evt-2", correlation_identifier="cor-b")
    e3 = make_event("evt-3", correlation_identifier="cor-a")

    store.append(e1)
    store.append(e2)
    store.append(e3)

    assert tuple(store.read_all()) == (e1, e2, e3)


def test_read_stream_returns_only_that_correlation_in_causal_order() -> None:
    store = InMemoryEventStore()
    a1 = make_event("a1", correlation_identifier="cor-a")
    b1 = make_event("b1", correlation_identifier="cor-b")
    a2 = make_event("a2", correlation_identifier="cor-a")
    b2 = make_event("b2", correlation_identifier="cor-b")

    store.append(a1)
    store.append(b1)
    store.append(a2)
    store.append(b2)

    assert tuple(store.read_stream("cor-a")) == (a1, a2)
    assert tuple(store.read_stream("cor-b")) == (b1, b2)


def test_read_stream_unknown_correlation_is_empty() -> None:
    store = InMemoryEventStore()
    store.append(make_event("evt-1", correlation_identifier="cor-a"))

    assert tuple(store.read_stream("does-not-exist")) == ()


def test_read_all_empty_store_is_empty() -> None:
    store = InMemoryEventStore()

    assert tuple(store.read_all()) == ()


# --------------------------------------------------------------------------- #
# StoredEvent positions
# --------------------------------------------------------------------------- #


def test_append_expecting_returns_stored_event_with_positions() -> None:
    store = InMemoryEventStore()
    event = make_event("evt-1", correlation_identifier="cor-a")

    stored = store.append_expecting(event, NO_EXPECTATION)

    assert isinstance(stored, StoredEvent)
    assert stored.event == event
    assert stored.global_sequence == 1  # 1-based
    assert stored.stream == "cor-a"
    assert stored.stream_position == 0  # 0-based per stream


def test_global_sequence_is_one_based_and_monotonic() -> None:
    store = InMemoryEventStore()

    s1 = store.append_expecting(make_event("evt-1", correlation_identifier="cor-a"), NO_EXPECTATION)
    s2 = store.append_expecting(make_event("evt-2", correlation_identifier="cor-b"), NO_EXPECTATION)
    s3 = store.append_expecting(make_event("evt-3", correlation_identifier="cor-a"), NO_EXPECTATION)

    assert (s1.global_sequence, s2.global_sequence, s3.global_sequence) == (1, 2, 3)


def test_interleaved_streams_keep_independent_positions_but_shared_global_sequence() -> None:
    store = InMemoryEventStore()

    a1 = store.append_expecting(make_event("a1", correlation_identifier="cor-a"), NO_EXPECTATION)
    b1 = store.append_expecting(make_event("b1", correlation_identifier="cor-b"), NO_EXPECTATION)
    a2 = store.append_expecting(make_event("a2", correlation_identifier="cor-a"), NO_EXPECTATION)
    b2 = store.append_expecting(make_event("b2", correlation_identifier="cor-b"), NO_EXPECTATION)

    # Stream positions are per-stream and independent.
    assert (a1.stream_position, a2.stream_position) == (0, 1)
    assert (b1.stream_position, b2.stream_position) == (0, 1)

    # Global sequence is shared and monotonic across both streams.
    assert (a1.global_sequence, b1.global_sequence) == (1, 2)
    assert (a2.global_sequence, b2.global_sequence) == (3, 4)


def test_read_all_stored_returns_records_in_global_order() -> None:
    store = InMemoryEventStore()
    store.append(make_event("evt-1", correlation_identifier="cor-a"))
    store.append(make_event("evt-2", correlation_identifier="cor-b"))

    stored = store.read_all_stored()

    assert tuple(s.event.identifier for s in stored) == ("evt-1", "evt-2")
    assert tuple(s.global_sequence for s in stored) == (1, 2)


# --------------------------------------------------------------------------- #
# idempotent append / duplicate detection
# --------------------------------------------------------------------------- #


def test_appending_identical_event_twice_is_a_noop() -> None:
    obs = InMemoryObservability()
    store = InMemoryEventStore(obs)
    event = make_event("evt-1", correlation_identifier="cor-a", payload={"k": "v"})

    store.append(event)
    store.append(make_event("evt-1", correlation_identifier="cor-a", payload={"k": "v"}))

    assert store.global_length() == 1
    assert store.stream_version("cor-a") == 1

    ignored = obs.events_of(InfraEventType.EVENT_DUPLICATE_IGNORED)
    assert len(ignored) == 1
    assert ignored[0].subject == "evt-1"
    assert ignored[0].at_sequence == 1


def test_idempotent_append_returns_the_original_stored_event() -> None:
    store = InMemoryEventStore()
    event = make_event("evt-1", correlation_identifier="cor-a")

    first = store.append_expecting(event, NO_EXPECTATION)
    again = store.append_expecting(event, NO_EXPECTATION)

    assert again == first
    assert again.global_sequence == 1


def test_duplicate_identifier_with_different_type_raises() -> None:
    store = InMemoryEventStore()
    store.append(make_event("evt-1", type="goal.created"))

    with pytest.raises(DuplicateEventError) as excinfo:
        store.append(make_event("evt-1", type="goal.updated"))

    assert excinfo.value.identifier == "evt-1"


def test_duplicate_identifier_with_different_payload_raises() -> None:
    store = InMemoryEventStore()
    store.append(make_event("evt-1", payload={"k": "v1"}))

    with pytest.raises(DuplicateEventError):
        store.append(make_event("evt-1", payload={"k": "v2"}))


def test_duplicate_does_not_mutate_the_log() -> None:
    store = InMemoryEventStore()
    store.append(make_event("evt-1", payload={"k": "v1"}))

    with pytest.raises(DuplicateEventError):
        store.append(make_event("evt-1", payload={"k": "v2"}))

    assert store.global_length() == 1
    assert next(iter(store.read_all())).payload == {"k": "v1"}


# --------------------------------------------------------------------------- #
# optimistic concurrency
# --------------------------------------------------------------------------- #


def test_append_expecting_succeeds_when_expected_matches_current_length() -> None:
    store = InMemoryEventStore()

    s0 = store.append_expecting(make_event("evt-1", correlation_identifier="cor-a"), 0)
    s1 = store.append_expecting(make_event("evt-2", correlation_identifier="cor-a"), 1)

    assert s0.stream_position == 0
    assert s1.stream_position == 1


def test_append_expecting_raises_on_version_mismatch() -> None:
    store = InMemoryEventStore()
    store.append_expecting(make_event("evt-1", correlation_identifier="cor-a"), 0)

    # Stream length is now 1; expecting 0 is stale.
    with pytest.raises(ConcurrencyConflictError) as excinfo:
        store.append_expecting(make_event("evt-2", correlation_identifier="cor-a"), 0)

    err = excinfo.value
    assert err.stream == "cor-a"
    assert err.expected == 0
    assert err.actual == 1


def test_concurrency_conflict_does_not_append() -> None:
    store = InMemoryEventStore()
    store.append_expecting(make_event("evt-1", correlation_identifier="cor-a"), 0)

    with pytest.raises(ConcurrencyConflictError):
        store.append_expecting(make_event("evt-2", correlation_identifier="cor-a"), 5)

    assert store.global_length() == 1
    assert store.stream_version("cor-a") == 1


def test_append_uses_sequence_position_zero_on_empty_stream() -> None:
    store = InMemoryEventStore()

    store.append(make_event("evt-1", correlation_identifier="cor-a", sequence_position=0))

    assert store.stream_version("cor-a") == 1


def test_append_with_sequence_position_one_on_empty_stream_raises() -> None:
    store = InMemoryEventStore()

    with pytest.raises(ConcurrencyConflictError) as excinfo:
        store.append(make_event("evt-1", correlation_identifier="cor-a", sequence_position=1))

    err = excinfo.value
    assert err.stream == "cor-a"
    assert err.expected == 1
    assert err.actual == 0


def test_append_with_sequence_position_none_never_conflicts() -> None:
    store = InMemoryEventStore()

    # Append several without ever declaring a position; no conflict regardless
    # of current stream length.
    store.append(make_event("evt-1", correlation_identifier="cor-a", sequence_position=None))
    store.append(make_event("evt-2", correlation_identifier="cor-a", sequence_position=None))
    store.append(make_event("evt-3", correlation_identifier="cor-a", sequence_position=None))

    assert store.stream_version("cor-a") == 3


def test_append_sequence_positions_drive_consecutive_writes() -> None:
    store = InMemoryEventStore()

    store.append(make_event("evt-1", correlation_identifier="cor-a", sequence_position=0))
    store.append(make_event("evt-2", correlation_identifier="cor-a", sequence_position=1))
    store.append(make_event("evt-3", correlation_identifier="cor-a", sequence_position=2))

    assert store.stream_version("cor-a") == 3
    assert tuple(e.identifier for e in store.read_stream("cor-a")) == ("evt-1", "evt-2", "evt-3")


# --------------------------------------------------------------------------- #
# read_from (tail replay)
# --------------------------------------------------------------------------- #


def _seed_three(store: InMemoryEventStore) -> tuple[object, object, object]:
    e1 = make_event("evt-1", correlation_identifier="cor-a")
    e2 = make_event("evt-2", correlation_identifier="cor-b")
    e3 = make_event("evt-3", correlation_identifier="cor-a")
    store.append(e1)
    store.append(e2)
    store.append(e3)
    return e1, e2, e3


def test_read_from_one_returns_all() -> None:
    store = InMemoryEventStore()
    e1, e2, e3 = _seed_three(store)

    assert tuple(store.read_from(1)) == (e1, e2, e3)


def test_read_from_middle_returns_inclusive_tail() -> None:
    store = InMemoryEventStore()
    _e1, e2, e3 = _seed_three(store)

    assert tuple(store.read_from(2)) == (e2, e3)


def test_read_from_last_returns_single_tail() -> None:
    store = InMemoryEventStore()
    _e1, _e2, e3 = _seed_three(store)

    assert tuple(store.read_from(3)) == (e3,)


def test_read_from_past_end_is_empty() -> None:
    store = InMemoryEventStore()
    _seed_three(store)

    assert tuple(store.read_from(store.global_length() + 1)) == ()


def test_read_from_zero_raises_value_error() -> None:
    store = InMemoryEventStore()
    _seed_three(store)

    with pytest.raises(ValueError):
        store.read_from(0)


def test_read_from_negative_raises_value_error() -> None:
    store = InMemoryEventStore()
    _seed_three(store)

    with pytest.raises(ValueError):
        store.read_from(-1)


# --------------------------------------------------------------------------- #
# small query API
# --------------------------------------------------------------------------- #


def test_stream_version_counts_per_correlation() -> None:
    store = InMemoryEventStore()
    store.append(make_event("a1", correlation_identifier="cor-a"))
    store.append(make_event("a2", correlation_identifier="cor-a"))
    store.append(make_event("b1", correlation_identifier="cor-b"))

    assert store.stream_version("cor-a") == 2
    assert store.stream_version("cor-b") == 1


def test_stream_version_unknown_correlation_is_zero() -> None:
    store = InMemoryEventStore()

    assert store.stream_version("unknown") == 0


def test_global_length_counts_all_events() -> None:
    store = InMemoryEventStore()
    assert store.global_length() == 0

    store.append(make_event("a1", correlation_identifier="cor-a"))
    store.append(make_event("b1", correlation_identifier="cor-b"))

    assert store.global_length() == 2


def test_contains_true_for_known_id_false_for_unknown() -> None:
    store = InMemoryEventStore()
    store.append(make_event("evt-1"))

    assert store.contains("evt-1") is True
    assert store.contains("never-seen") is False


# --------------------------------------------------------------------------- #
# observability counters / events
# --------------------------------------------------------------------------- #


def test_appended_counter_increments_per_real_append() -> None:
    obs = InMemoryObservability()
    store = InMemoryEventStore(obs)

    store.append(make_event("evt-1", correlation_identifier="cor-a"))
    store.append(make_event("evt-2", correlation_identifier="cor-a"))

    assert obs.counters["event_store.appended"] == 2


def test_appended_counter_does_not_increment_on_idempotent_append() -> None:
    obs = InMemoryObservability()
    store = InMemoryEventStore(obs)
    event = make_event("evt-1", correlation_identifier="cor-a")

    store.append(event)
    store.append(event)

    assert obs.counters["event_store.appended"] == 1


def test_concurrency_conflict_counter_increments_on_conflict() -> None:
    obs = InMemoryObservability()
    store = InMemoryEventStore(obs)
    store.append_expecting(make_event("evt-1", correlation_identifier="cor-a"), 0)

    with pytest.raises(ConcurrencyConflictError):
        store.append_expecting(make_event("evt-2", correlation_identifier="cor-a"), 0)

    assert obs.counters["event_store.concurrency_conflict"] == 1
    # Only the first (real) append incremented the appended counter; the
    # conflicting append did not add a second.
    assert obs.counters["event_store.appended"] == 1


def test_append_records_event_appended_infra_event() -> None:
    obs = InMemoryObservability()
    store = InMemoryEventStore(obs)

    store.append(make_event("evt-1", type="goal.created", correlation_identifier="cor-a"))

    appended = obs.events_of(InfraEventType.EVENT_APPENDED)
    assert len(appended) == 1
    assert appended[0].subject == "evt-1"
    assert appended[0].at_sequence == 1
    assert appended[0].detail == {"type": "goal.created", "stream": "cor-a"}


def test_conflict_records_concurrency_conflict_infra_event() -> None:
    obs = InMemoryObservability()
    store = InMemoryEventStore(obs)
    store.append_expecting(make_event("evt-1", correlation_identifier="cor-a"), 0)

    with pytest.raises(ConcurrencyConflictError):
        store.append_expecting(make_event("evt-2", correlation_identifier="cor-a"), 7)

    conflicts = obs.events_of(InfraEventType.CONCURRENCY_CONFLICT)
    assert len(conflicts) == 1
    assert conflicts[0].subject == "cor-a"
    assert conflicts[0].detail == {"expected": 7, "actual": 1}


def test_default_observability_is_silent() -> None:
    # No observability injected — appends still work, nothing is recorded.
    store = InMemoryEventStore()

    store.append(make_event("evt-1", correlation_identifier="cor-a"))

    assert store.global_length() == 1
