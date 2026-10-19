"""Durable snapshot-store tests (:class:`nexus_infra.durable.DurableSnapshotStore`).

Mirrors ``test_snapshots.py``. ``create`` returns a record holding the original
state; ``get``/``latest``/``restore`` reconstruct value-equal structural state from
storage (ADR-001). Integrity (content-hash) and deterministic log-position expiry
behave identically to the in-memory store.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from nexus_infra import (
    DurableSnapshotStore,
    InfraEventType,
    InMemoryObservability,
    IntegrityError,
    SnapshotExpiredError,
    SnapshotNotFoundError,
    SnapshotRecord,
    connect,
    content_hash,
)


@pytest.fixture
def obs() -> InMemoryObservability:
    return InMemoryObservability()


@pytest.fixture
def store(tmp_path, obs: InMemoryObservability) -> DurableSnapshotStore:
    return DurableSnapshotStore(connect(str(tmp_path / "snap.db")), observability=obs)


@pytest.fixture
def state() -> dict[str, object]:
    return {"counter": 7, "items": ["a", "b"], "nested": {"flag": True}}


# -- create ------------------------------------------------------------------ #


def test_create_returns_record_with_expected_fields(
    store: DurableSnapshotStore, state: dict[str, object]
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
    assert record.content_hash == content_hash(state)


def test_create_defaults(store: DurableSnapshotStore, state: dict[str, object]) -> None:
    record = store.create("snap-1", "projection-x", state, log_position=1)
    assert record.projection_version == 1
    assert record.parent_identifier is None
    assert record.expires_at_sequence is None


def test_create_records_event_and_counter(
    store: DurableSnapshotStore, obs: InMemoryObservability, state: dict[str, object]
) -> None:
    store.create("snap-1", "projection-x", state, log_position=42, projection_version=3)
    store.create("snap-2", "projection-x", state, log_position=43)
    created = obs.events_of(InfraEventType.SNAPSHOT_CREATED)
    assert created[0].subject == "snap-1"
    assert created[0].at_sequence == 42
    assert created[0].detail == {"key": "projection-x", "version": 3}
    assert obs.counters["snapshot.created"] == 2


def test_create_duplicate_identifier_raises(
    store: DurableSnapshotStore, state: dict[str, object]
) -> None:
    store.create("snap-1", "projection-x", state, log_position=1)
    with pytest.raises(IntegrityError):
        store.create("snap-1", "projection-x", state, log_position=2)


# -- get / latest / lineage -------------------------------------------------- #


def test_get_returns_equal_record(store: DurableSnapshotStore, state: dict[str, object]) -> None:
    created = store.create("snap-1", "projection-x", state, log_position=1)
    got = store.get("snap-1")
    assert got.identifier == created.identifier
    assert got.state == state
    assert got.content_hash == created.content_hash


def test_get_unknown_raises(store: DurableSnapshotStore) -> None:
    with pytest.raises(SnapshotNotFoundError):
        store.get("missing")


def test_latest_is_scoped_and_most_recent(
    store: DurableSnapshotStore, state: dict[str, object]
) -> None:
    store.create("snap-1", "projection-x", state, log_position=1)
    store.create("snap-2", "projection-x", state, log_position=2)
    store.create("other", "key-b", state, log_position=3)
    assert store.latest("projection-x").identifier == "snap-2"
    assert store.latest("key-b").identifier == "other"
    assert store.latest("nope") is None


def test_lineage_oldest_first_with_parent(
    store: DurableSnapshotStore, state: dict[str, object]
) -> None:
    store.create("snap-1", "projection-x", state, log_position=1)
    store.create("snap-2", "projection-x", state, log_position=2, parent_identifier="snap-1")
    lineage = store.lineage("projection-x")
    assert tuple(r.identifier for r in lineage) == ("snap-1", "snap-2")
    assert lineage[0].parent_identifier is None
    assert lineage[1].parent_identifier == "snap-1"
    assert store.lineage("nope") == ()


# -- restore ----------------------------------------------------------------- #


def test_restore_returns_equal_state_and_records(
    store: DurableSnapshotStore, obs: InMemoryObservability, state: dict[str, object]
) -> None:
    store.create("snap-1", "projection-x", state, log_position=11)
    assert store.restore("snap-1") == state
    restored = obs.events_of(InfraEventType.SNAPSHOT_RESTORED)
    assert restored[0].subject == "snap-1"
    assert restored[0].at_sequence == 11
    assert obs.counters["snapshot.restored"] == 1


def test_restore_unknown_raises(store: DurableSnapshotStore) -> None:
    with pytest.raises(SnapshotNotFoundError):
        store.restore("missing")


# -- integrity + expiry ------------------------------------------------------ #


def test_validate_detects_tampering(store: DurableSnapshotStore, state: dict[str, object]) -> None:
    record = store.create("snap-1", "projection-x", state, log_position=1)
    store.validate(record)  # untampered: no raise
    tampered = replace(record, state={"counter": 999})
    with pytest.raises(IntegrityError):
        store.validate(tampered)


def test_expiry_horizon(store: DurableSnapshotStore, state: dict[str, object]) -> None:
    record = store.create("snap-1", "projection-x", state, log_position=1, expires_at_sequence=5)
    store.validate(record, current_sequence=5)  # exact horizon ok
    with pytest.raises(SnapshotExpiredError) as excinfo:
        store.validate(record, current_sequence=6)
    assert (excinfo.value.expires_at, excinfo.value.current) == (5, 6)

    store.create("snap-2", "projection-x", state, log_position=1, expires_at_sequence=5)
    with pytest.raises(SnapshotExpiredError):
        store.restore("snap-2", current_sequence=6)
