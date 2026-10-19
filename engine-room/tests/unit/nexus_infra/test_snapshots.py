"""Tests for the in-memory snapshot store (create, restore, integrity, expiry, lineage).

Covers the durable substrate described in ``nexus_infra.snapshots``: integrity-stamped
capture, identifier/key lookup, lineage with parent linkage, deterministic log-position
expiry, and the observability side-effects each operation must emit.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from nexus_infra import (
    InfraEventType,
    InMemoryObservability,
    InMemorySnapshotStore,
    IntegrityError,
    SnapshotExpiredError,
    SnapshotNotFoundError,
    SnapshotRecord,
    content_hash,
)

from .factories import make_goal

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def obs() -> InMemoryObservability:
    """A collecting observability sink to assert side-effects against."""
    return InMemoryObservability()


@pytest.fixture
def store(obs: InMemoryObservability) -> InMemorySnapshotStore:
    """A snapshot store wired to the collecting observability sink."""
    return InMemorySnapshotStore(observability=obs)


@pytest.fixture
def state() -> dict[str, object]:
    """A simple, deterministic snapshot state."""
    return {"counter": 7, "items": ["a", "b"], "nested": {"flag": True}}


# --------------------------------------------------------------------------- #
# create()
# --------------------------------------------------------------------------- #


def test_create_returns_record_with_expected_fields(
    store: InMemorySnapshotStore, state: dict[str, object]
) -> None:
    record = store.create(
        "snap-1",
        "projection-x",
        state,
        log_position=42,
        projection_version=3,
        parent_identifier="parent-1",
        expires_at_sequence=100,
    )

    assert isinstance(record, SnapshotRecord)
    assert record.identifier == "snap-1"
    assert record.key == "projection-x"
    assert record.state == state
    assert record.log_position == 42
    assert record.projection_version == 3
    assert record.parent_identifier == "parent-1"
    assert record.expires_at_sequence == 100


def test_create_sets_content_hash_matching_state(
    store: InMemorySnapshotStore, state: dict[str, object]
) -> None:
    record = store.create("snap-1", "projection-x", state, log_position=1)

    assert record.content_hash == content_hash(state)


def test_create_defaults_projection_version_and_optionals(
    store: InMemorySnapshotStore, state: dict[str, object]
) -> None:
    record = store.create("snap-1", "projection-x", state, log_position=1)

    assert record.projection_version == 1
    assert record.parent_identifier is None
    assert record.expires_at_sequence is None


def test_create_supports_domain_object_state(store: InMemorySnapshotStore) -> None:
    goal = make_goal("goal-99", outcome="Ship the snapshot store")

    record = store.create("snap-goal", "goal-projection", goal, log_position=5)

    assert record.state is goal
    assert record.content_hash == content_hash(goal)


def test_create_records_snapshot_created_event(
    store: InMemorySnapshotStore, obs: InMemoryObservability, state: dict[str, object]
) -> None:
    store.create("snap-1", "projection-x", state, log_position=42, projection_version=3)

    created = obs.events_of(InfraEventType.SNAPSHOT_CREATED)
    assert len(created) == 1
    event = created[0]
    assert event.subject == "snap-1"
    assert event.at_sequence == 42
    assert event.detail == {"key": "projection-x", "version": 3}


def test_create_increments_created_counter(
    store: InMemorySnapshotStore, obs: InMemoryObservability, state: dict[str, object]
) -> None:
    store.create("snap-1", "projection-x", state, log_position=1)
    store.create("snap-2", "projection-x", state, log_position=2)

    assert obs.counters["snapshot.created"] == 2


def test_create_duplicate_identifier_raises_integrity_error(
    store: InMemorySnapshotStore, state: dict[str, object]
) -> None:
    store.create("snap-1", "projection-x", state, log_position=1)

    with pytest.raises(IntegrityError):
        store.create("snap-1", "projection-x", state, log_position=2)


# --------------------------------------------------------------------------- #
# get()
# --------------------------------------------------------------------------- #


def test_get_returns_created_record(store: InMemorySnapshotStore, state: dict[str, object]) -> None:
    created = store.create("snap-1", "projection-x", state, log_position=1)

    assert store.get("snap-1") is created


def test_get_unknown_identifier_raises_not_found(store: InMemorySnapshotStore) -> None:
    with pytest.raises(SnapshotNotFoundError):
        store.get("missing")


# --------------------------------------------------------------------------- #
# latest()
# --------------------------------------------------------------------------- #


def test_latest_returns_most_recent_for_key(
    store: InMemorySnapshotStore, state: dict[str, object]
) -> None:
    store.create("snap-1", "projection-x", state, log_position=1)
    second = store.create("snap-2", "projection-x", state, log_position=2)

    assert store.latest("projection-x") is second


def test_latest_is_scoped_per_key(store: InMemorySnapshotStore, state: dict[str, object]) -> None:
    a = store.create("a-1", "key-a", state, log_position=1)
    b = store.create("b-1", "key-b", state, log_position=2)

    assert store.latest("key-a") is a
    assert store.latest("key-b") is b


def test_latest_unknown_key_is_none(store: InMemorySnapshotStore) -> None:
    assert store.latest("nope") is None


# --------------------------------------------------------------------------- #
# lineage()
# --------------------------------------------------------------------------- #


def test_lineage_returns_all_for_key_oldest_first(
    store: InMemorySnapshotStore, state: dict[str, object]
) -> None:
    first = store.create("snap-1", "projection-x", state, log_position=1)
    second = store.create("snap-2", "projection-x", state, log_position=2)
    third = store.create("snap-3", "projection-x", state, log_position=3)

    assert store.lineage("projection-x") == (first, second, third)


def test_lineage_unknown_key_is_empty(store: InMemorySnapshotStore) -> None:
    assert store.lineage("nope") == ()


def test_lineage_tracks_parent_linkage(
    store: InMemorySnapshotStore, state: dict[str, object]
) -> None:
    first = store.create("snap-1", "projection-x", state, log_position=1)
    child = store.create(
        "snap-2",
        "projection-x",
        state,
        log_position=2,
        parent_identifier=first.identifier,
    )

    lineage = store.lineage("projection-x")
    assert lineage == (first, child)
    assert lineage[0].parent_identifier is None
    assert lineage[1].parent_identifier == first.identifier


# --------------------------------------------------------------------------- #
# restore()
# --------------------------------------------------------------------------- #


def test_restore_returns_original_state(
    store: InMemorySnapshotStore, state: dict[str, object]
) -> None:
    store.create("snap-1", "projection-x", state, log_position=1)

    assert store.restore("snap-1") == state


def test_restore_returns_domain_object_state(store: InMemorySnapshotStore) -> None:
    goal = make_goal("goal-7")
    store.create("snap-goal", "goal-projection", goal, log_position=1)

    assert store.restore("snap-goal") is goal


def test_restore_records_restored_event_and_counter(
    store: InMemorySnapshotStore, obs: InMemoryObservability, state: dict[str, object]
) -> None:
    store.create("snap-1", "projection-x", state, log_position=11)
    store.restore("snap-1")

    restored = obs.events_of(InfraEventType.SNAPSHOT_RESTORED)
    assert len(restored) == 1
    assert restored[0].subject == "snap-1"
    assert restored[0].at_sequence == 11
    assert obs.counters["snapshot.restored"] == 1


def test_restore_unknown_identifier_raises_not_found(store: InMemorySnapshotStore) -> None:
    with pytest.raises(SnapshotNotFoundError):
        store.restore("missing")


# --------------------------------------------------------------------------- #
# integrity validation
# --------------------------------------------------------------------------- #


def test_validate_passes_for_untampered_record(
    store: InMemorySnapshotStore, state: dict[str, object]
) -> None:
    record = store.create("snap-1", "projection-x", state, log_position=1)

    # Should not raise.
    store.validate(record)


def test_validate_detects_tampered_state_via_replace(
    store: InMemorySnapshotStore, state: dict[str, object]
) -> None:
    record = store.create("snap-1", "projection-x", state, log_position=1)
    tampered = replace(record, state={"counter": 999})  # hash kept from original

    with pytest.raises(IntegrityError):
        store.validate(tampered)


def test_validate_detects_directly_constructed_mismatch(store: InMemorySnapshotStore) -> None:
    forged = SnapshotRecord(
        identifier="forged",
        key="projection-x",
        state={"real": "state"},
        log_position=1,
        projection_version=1,
        content_hash=content_hash({"different": "value"}),
    )

    with pytest.raises(IntegrityError):
        store.validate(forged)


# --------------------------------------------------------------------------- #
# expiry
# --------------------------------------------------------------------------- #


def test_validate_raises_when_past_expiry_horizon(
    store: InMemorySnapshotStore, state: dict[str, object]
) -> None:
    record = store.create("snap-1", "projection-x", state, log_position=1, expires_at_sequence=5)

    with pytest.raises(SnapshotExpiredError) as excinfo:
        store.validate(record, current_sequence=6)

    assert excinfo.value.expires_at == 5
    assert excinfo.value.current == 6


def test_validate_at_exact_horizon_does_not_raise(
    store: InMemorySnapshotStore, state: dict[str, object]
) -> None:
    record = store.create("snap-1", "projection-x", state, log_position=1, expires_at_sequence=5)

    # current == expires_at_sequence is still valid (strict greater-than check).
    store.validate(record, current_sequence=5)


def test_validate_with_no_current_sequence_does_not_raise(
    store: InMemorySnapshotStore, state: dict[str, object]
) -> None:
    record = store.create("snap-1", "projection-x", state, log_position=1, expires_at_sequence=5)

    store.validate(record, current_sequence=None)


def test_restore_past_expiry_raises(store: InMemorySnapshotStore, state: dict[str, object]) -> None:
    store.create("snap-1", "projection-x", state, log_position=1, expires_at_sequence=5)

    with pytest.raises(SnapshotExpiredError):
        store.restore("snap-1", current_sequence=6)


def test_restore_within_horizon_succeeds(
    store: InMemorySnapshotStore, state: dict[str, object]
) -> None:
    store.create("snap-1", "projection-x", state, log_position=1, expires_at_sequence=5)

    assert store.restore("snap-1", current_sequence=5) == state
