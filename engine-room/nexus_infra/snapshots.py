"""Step 4 — the Snapshot Store (ADR-001 §3.3, AP-204, INV-14/18).

A snapshot materializes a projection's state at a specific **log position** so a
future Recovery can restore the nearest valid snapshot and replay only the tail —
never re-folding the whole log, and never resuming "from operator intent". This
module stores and restores snapshots with:

- **Integrity validation** — a SHA-256 content hash is recorded at capture and
  re-verified on restore; a mismatch is a hard :class:`IntegrityError`.
- **Versioning + parent linkage** — every snapshot keeps its projection version
  and an optional parent, forming a lineage per key.
- **Expiration** — an optional *log-position* horizon (deterministic, never a
  wall clock): a snapshot too far behind the current log is refused.

Recovery *behavior* is a later phase; this provides only the durable substrate it
will build on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nexus_infra.errors import (
    IntegrityError,
    SnapshotExpiredError,
    SnapshotNotFoundError,
)
from nexus_infra.observability import (
    InfraEvent,
    InfraEventType,
    NullObservability,
    Observability,
)
from nexus_infra.serialization import content_hash


@dataclass(frozen=True, slots=True)
class SnapshotRecord[S]:
    """A captured projection state plus the metadata needed to trust and place it."""

    identifier: str
    key: str
    """What this snapshots (a projection / aggregate identity)."""
    state: S
    log_position: int
    """The global event sequence this snapshot corresponds to."""
    projection_version: int
    content_hash: str
    parent_identifier: str | None = None
    expires_at_sequence: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)


class InMemorySnapshotStore:
    """A local snapshot store with integrity, versioning, lineage, and expiry."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._by_identifier: dict[str, SnapshotRecord[Any]] = {}
        self._by_key: dict[str, list[SnapshotRecord[Any]]] = {}
        self._obs: Observability = observability or NullObservability()

    def create[S](
        self,
        identifier: str,
        key: str,
        state: S,
        log_position: int,
        *,
        projection_version: int = 1,
        parent_identifier: str | None = None,
        expires_at_sequence: int | None = None,
    ) -> SnapshotRecord[S]:
        """Capture ``state`` at ``log_position`` as an integrity-stamped snapshot."""
        if identifier in self._by_identifier:
            raise IntegrityError(f"snapshot identifier {identifier!r} already exists")
        record: SnapshotRecord[S] = SnapshotRecord(
            identifier=identifier,
            key=key,
            state=state,
            log_position=log_position,
            projection_version=projection_version,
            content_hash=content_hash(state),
            parent_identifier=parent_identifier,
            expires_at_sequence=expires_at_sequence,
        )
        self._by_identifier[identifier] = record
        self._by_key.setdefault(key, []).append(record)
        self._obs.record(
            InfraEvent(
                InfraEventType.SNAPSHOT_CREATED,
                subject=identifier,
                at_sequence=log_position,
                detail={"key": key, "version": projection_version},
            )
        )
        self._obs.increment("snapshot.created")
        return record

    def get(self, identifier: str) -> SnapshotRecord[Any]:
        """Fetch a snapshot by identifier (raises if absent)."""
        record = self._by_identifier.get(identifier)
        if record is None:
            raise SnapshotNotFoundError(f"no snapshot with identifier {identifier!r}")
        return record

    def latest(self, key: str) -> SnapshotRecord[Any] | None:
        """The most recently captured snapshot for ``key`` (or ``None``)."""
        history = self._by_key.get(key)
        return history[-1] if history else None

    def validate(self, record: SnapshotRecord[Any], current_sequence: int | None = None) -> None:
        """Pre-restore validation: integrity, then expiry (if a horizon is set).

        Raises :class:`IntegrityError` on hash mismatch or
        :class:`SnapshotExpiredError` if the snapshot is past its log horizon.
        """
        if content_hash(record.state) != record.content_hash:
            raise IntegrityError(f"snapshot {record.identifier!r} failed integrity check")
        if (
            current_sequence is not None
            and record.expires_at_sequence is not None
            and current_sequence > record.expires_at_sequence
        ):
            raise SnapshotExpiredError(
                record.identifier, record.expires_at_sequence, current_sequence
            )

    def restore(self, identifier: str, *, current_sequence: int | None = None) -> Any:
        """Validate and return the snapshotted state (the restore entry point)."""
        record = self.get(identifier)
        self.validate(record, current_sequence)
        self._obs.record(
            InfraEvent(
                InfraEventType.SNAPSHOT_RESTORED,
                subject=identifier,
                at_sequence=record.log_position,
            )
        )
        self._obs.increment("snapshot.restored")
        return record.state

    def lineage(self, key: str) -> tuple[SnapshotRecord[Any], ...]:
        """All snapshots for a key, oldest first."""
        return tuple(self._by_key.get(key, ()))
