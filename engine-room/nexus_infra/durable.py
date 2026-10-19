"""Durable, SQLite-backed implementations of the persistence substrate (ADR-007).

These are drop-in replacements for the in-memory adapters (``event_store``,
``repositories``, ``unit_of_work``, ``snapshots``) that persist behind the *same*
frozen synchronous protocols (``nexus_core.persistence.interfaces``). Per ADR-007:

- The **Event Log remains authoritative**; State (repositories) is a projection.
- Implementations are **synchronous** — the standard-library ``sqlite3`` driver
  honors the sync protocols natively. **No async, no async bridge** (INV-01).
- The ``VersionedSerializer`` is the on-disk format; events and objects are stored
  as its JSON envelope. Store-assigned positions are **persisted, never recomputed**.

Semantics (ordering, idempotency INV-16, optimistic concurrency, tail replay,
version bumps, snapshot integrity/expiry) mirror the in-memory adapters exactly.
The one physical difference is identity: a durable read reconstructs a *value-equal*
object from storage rather than returning the same Python instance — which is what
ADR-001 means by "state is a projection of the log."

# ponytail: one shared sqlite connection per infrastructure context, single-threaded
# (v2 is fully synchronous — 0 async def). A connection pool is only needed if v2
# ever runs the substrate concurrently.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterable
from contextlib import suppress
from typing import Any, Literal

from pydantic import BaseModel

from nexus_core.domain import Artifact, Goal, Knowledge, Plan, Policy
from nexus_core.domain.event import Event
from nexus_infra.clock import Clock, SystemClock
from nexus_infra.errors import (
    ConcurrencyConflictError,
    DuplicateEventError,
    IntegrityError,
    SnapshotExpiredError,
    SnapshotNotFoundError,
    TransactionError,
)
from nexus_infra.event_bus import InProcessEventBus
from nexus_infra.event_store import NO_EXPECTATION, StoredEvent
from nexus_infra.event_versioning import InMemoryUpcasterRegistry
from nexus_infra.identifiers import UuidIdentifierFactory
from nexus_infra.observability import (
    InfraEvent,
    InfraEventType,
    NullObservability,
    Observability,
)
from nexus_infra.serialization import VersionedSerializer, canonical_json, content_hash
from nexus_infra.snapshots import SnapshotRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    global_sequence INTEGER PRIMARY KEY,
    identifier      TEXT NOT NULL UNIQUE,
    stream          TEXT NOT NULL,
    stream_position INTEGER NOT NULL,
    type            TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    envelope        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_stream ON events(stream, stream_position);

CREATE TABLE IF NOT EXISTS repository_objects (
    name     TEXT NOT NULL,
    identity TEXT NOT NULL,
    version  INTEGER NOT NULL,
    ord      INTEGER NOT NULL,
    envelope TEXT NOT NULL,
    PRIMARY KEY (name, identity)
);
CREATE INDEX IF NOT EXISTS idx_repo_order ON repository_objects(name, ord);

CREATE TABLE IF NOT EXISTS snapshots (
    identifier          TEXT PRIMARY KEY,
    key                 TEXT NOT NULL,
    ord                 INTEGER NOT NULL,
    state               TEXT NOT NULL,
    log_position        INTEGER NOT NULL,
    projection_version  INTEGER NOT NULL,
    content_hash        TEXT NOT NULL,
    parent_identifier   TEXT,
    expires_at_sequence INTEGER
);
CREATE INDEX IF NOT EXISTS idx_snap_key ON snapshots(key, ord);
"""


class _ClosingConnection(sqlite3.Connection):
    """Close the connection when its final shared component reference is released."""

    def __del__(self) -> None:
        with suppress(Exception):
            self.close()


def connect(db_path: str) -> sqlite3.Connection:
    """Open a synchronous SQLite connection wired for explicit transactions.

    ``isolation_level=None`` puts the driver in autocommit mode: a bare statement
    commits immediately (so a standalone ``append``/``add`` is durable at once),
    while an explicit ``BEGIN``/``COMMIT`` (issued by the Unit of Work) wraps a
    batch in one durable transaction.
    """
    conn = sqlite3.connect(
        db_path,
        isolation_level=None,
        check_same_thread=False,
        factory=_ClosingConnection,
    )
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


# --------------------------------------------------------------------------- #
# Durable Event Store
# --------------------------------------------------------------------------- #


class DurableEventStore:
    """A SQLite-backed append-only event log implementing ``EventStore`` (ADR-007)."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        serializer: VersionedSerializer | None = None,
        observability: Observability | None = None,
    ) -> None:
        self._conn = connection
        self._serializer = serializer or VersionedSerializer()
        self._obs: Observability = observability or NullObservability()

    # -- EventStore protocol ------------------------------------------------- #

    def append(self, event: Event) -> None:
        expected = (
            event.sequence_position if event.sequence_position is not None else NO_EXPECTATION
        )
        self.append_expecting(event, expected)

    def read_stream(self, correlation_identifier: str) -> Iterable[Event]:
        rows = self._conn.execute(
            "SELECT envelope FROM events WHERE stream=? ORDER BY global_sequence",
            (correlation_identifier,),
        ).fetchall()
        return tuple(self._deserialize(r[0]) for r in rows)

    def read_all(self) -> Iterable[Event]:
        rows = self._conn.execute("SELECT envelope FROM events ORDER BY global_sequence").fetchall()
        return tuple(self._deserialize(r[0]) for r in rows)

    # -- richer infrastructure API (mirrors InMemoryEventStore) -------------- #

    def append_expecting(self, event: Event, expected_version: int) -> StoredEvent:
        existing = self._conn.execute(
            "SELECT global_sequence, content_hash, stream, stream_position "
            "FROM events WHERE identifier=?",
            (event.identifier,),
        ).fetchone()
        if existing is not None:
            gseq, chash, stream_, spos = existing
            if chash == content_hash(event):
                self._obs.record(
                    InfraEvent(
                        InfraEventType.EVENT_DUPLICATE_IGNORED,
                        subject=event.identifier,
                        at_sequence=gseq,
                    )
                )
                return StoredEvent(
                    event=event, global_sequence=gseq, stream=stream_, stream_position=spos
                )
            raise DuplicateEventError(event.identifier)

        stream = event.correlation_identifier
        current_version = self._conn.execute(
            "SELECT COUNT(*) FROM events WHERE stream=?", (stream,)
        ).fetchone()[0]
        if expected_version != NO_EXPECTATION and expected_version != current_version:
            self._obs.record(
                InfraEvent(
                    InfraEventType.CONCURRENCY_CONFLICT,
                    subject=stream,
                    detail={"expected": expected_version, "actual": current_version},
                )
            )
            self._obs.increment("event_store.concurrency_conflict")
            raise ConcurrencyConflictError(stream, expected_version, current_version)

        gseq = self._conn.execute(
            "SELECT COALESCE(MAX(global_sequence), 0) + 1 FROM events"
        ).fetchone()[0]
        self._conn.execute(
            "INSERT INTO events(global_sequence, identifier, stream, stream_position, "
            "type, content_hash, envelope) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                gseq,
                event.identifier,
                stream,
                current_version,
                event.type,
                content_hash(event),
                self._serialize(event),
            ),
        )
        self._obs.record(
            InfraEvent(
                InfraEventType.EVENT_APPENDED,
                subject=event.identifier,
                at_sequence=gseq,
                detail={"type": event.type, "stream": stream},
            )
        )
        self._obs.increment("event_store.appended")
        return StoredEvent(
            event=event, global_sequence=gseq, stream=stream, stream_position=current_version
        )

    def read_from(self, global_sequence: int) -> Iterable[Event]:
        if global_sequence < 1:
            raise ValueError("global_sequence is 1-based and must be >= 1")
        rows = self._conn.execute(
            "SELECT envelope FROM events WHERE global_sequence >= ? ORDER BY global_sequence",
            (global_sequence,),
        ).fetchall()
        return tuple(self._deserialize(r[0]) for r in rows)

    def read_all_stored(self) -> tuple[StoredEvent, ...]:
        rows = self._conn.execute(
            "SELECT envelope, global_sequence, stream, stream_position "
            "FROM events ORDER BY global_sequence"
        ).fetchall()
        return tuple(
            StoredEvent(
                event=self._deserialize(env),
                global_sequence=gseq,
                stream=stream,
                stream_position=spos,
            )
            for env, gseq, stream, spos in rows
        )

    def stream_version(self, correlation_identifier: str) -> int:
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM events WHERE stream=?", (correlation_identifier,)
            ).fetchone()[0]
        )

    def global_length(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    def contains(self, event_identifier: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM events WHERE identifier=?", (event_identifier,)
        ).fetchone()
        return row is not None

    # -- serialization ------------------------------------------------------- #

    def _serialize(self, event: Event) -> str:
        return json.dumps(self._serializer.serialize(event))

    def _deserialize(self, envelope: str) -> Event:
        return self._serializer.deserialize(Event, json.loads(envelope))


# --------------------------------------------------------------------------- #
# Durable Repository
# --------------------------------------------------------------------------- #


class DurableRepository[T: BaseModel]:
    """A SQLite-backed, identity-keyed projection store implementing ``Repository[T]``.

    A durable read reconstructs a value-equal object from storage (ADR-001: state
    is a projection), rather than returning the same instance the in-memory adapter
    would. All other semantics — version bumps, insertion order, optimistic
    concurrency, remove — match the in-memory adapter exactly.
    """

    def __init__(
        self,
        name: str,
        key: Callable[[T], str],
        model_type: type[T],
        connection: sqlite3.Connection,
        serializer: VersionedSerializer | None = None,
        observability: Observability | None = None,
    ) -> None:
        self._name = name
        self._key = key
        self._model_type = model_type
        self._conn = connection
        self._serializer = serializer or VersionedSerializer()
        self._obs: Observability = observability or NullObservability()

    # -- Repository protocol ------------------------------------------------- #

    def get(self, identifier: str) -> T | None:
        row = self._conn.execute(
            "SELECT envelope FROM repository_objects WHERE name=? AND identity=?",
            (self._name, identifier),
        ).fetchone()
        return self._deserialize(row[0]) if row is not None else None

    def add(self, obj: T) -> None:
        self._write(obj)

    def list_all(self) -> tuple[T, ...]:
        rows = self._conn.execute(
            "SELECT envelope FROM repository_objects WHERE name=? ORDER BY ord",
            (self._name,),
        ).fetchall()
        return tuple(self._deserialize(r[0]) for r in rows)

    # -- optimistic concurrency ---------------------------------------------- #

    def add_expecting(self, obj: T, expected_version: int) -> None:
        identity = self._key(obj)
        current = self.version_of(identity)
        if current != expected_version:
            self._obs.increment("repository.concurrency_conflict")
            raise ConcurrencyConflictError(f"{self._name}:{identity}", expected_version, current)
        self._write(obj)

    def version_of(self, identifier: str) -> int:
        row = self._conn.execute(
            "SELECT version FROM repository_objects WHERE name=? AND identity=?",
            (self._name, identifier),
        ).fetchone()
        return row[0] if row is not None else 0

    # -- conveniences -------------------------------------------------------- #

    def contains(self, identifier: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM repository_objects WHERE name=? AND identity=?",
            (self._name, identifier),
        ).fetchone()
        return row is not None

    def remove(self, identifier: str) -> None:
        self._conn.execute(
            "DELETE FROM repository_objects WHERE name=? AND identity=?",
            (self._name, identifier),
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def count(self) -> int:
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM repository_objects WHERE name=?", (self._name,)
            ).fetchone()[0]
        )

    # -- transactional hooks (used by the Unit of Work for parity) ----------- #

    def _capture(self) -> list[tuple[str, int, int, str]]:
        return self._conn.execute(
            "SELECT identity, version, ord, envelope FROM repository_objects WHERE name=?",
            (self._name,),
        ).fetchall()

    def _apply(self, snapshot: list[tuple[str, int, int, str]]) -> None:
        self._conn.execute("DELETE FROM repository_objects WHERE name=?", (self._name,))
        self._conn.executemany(
            "INSERT INTO repository_objects(name, identity, version, ord, envelope) "
            "VALUES (?, ?, ?, ?, ?)",
            [(self._name, ident, ver, ordv, env) for ident, ver, ordv, env in snapshot],
        )

    def _write(self, obj: T) -> None:
        identity = self._key(obj)
        envelope = self._serialize(obj)
        existing = self._conn.execute(
            "SELECT version, ord FROM repository_objects WHERE name=? AND identity=?",
            (self._name, identity),
        ).fetchone()
        if existing is not None:
            new_version = existing[0] + 1
            self._conn.execute(
                "UPDATE repository_objects SET version=?, envelope=? WHERE name=? AND identity=?",
                (new_version, envelope, self._name, identity),
            )
        else:
            ordv = self._conn.execute(
                "SELECT COALESCE(MAX(ord), 0) + 1 FROM repository_objects WHERE name=?",
                (self._name,),
            ).fetchone()[0]
            self._conn.execute(
                "INSERT INTO repository_objects(name, identity, version, ord, envelope) "
                "VALUES (?, ?, ?, ?, ?)",
                (self._name, identity, 1, ordv, envelope),
            )
        self._obs.record(
            InfraEvent(InfraEventType.REPOSITORY_WRITE, subject=f"{self._name}:{identity}")
        )
        self._obs.increment("repository.write")

    def _serialize(self, obj: T) -> str:
        return json.dumps(self._serializer.serialize(obj))

    def _deserialize(self, envelope: str) -> T:
        return self._serializer.deserialize(self._model_type, json.loads(envelope))


class DurableGoalRepository(DurableRepository[Goal]):
    """Durable persistence adapter for :class:`~nexus_core.domain.Goal`."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        serializer: VersionedSerializer | None = None,
        observability: Observability | None = None,
    ) -> None:
        super().__init__("goal", lambda g: g.identity, Goal, connection, serializer, observability)


class DurablePlanRepository(DurableRepository[Plan]):
    """Durable persistence adapter for :class:`~nexus_core.domain.Plan`."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        serializer: VersionedSerializer | None = None,
        observability: Observability | None = None,
    ) -> None:
        super().__init__("plan", lambda p: p.identity, Plan, connection, serializer, observability)


class DurableArtifactRepository(DurableRepository[Artifact]):
    """Durable persistence adapter for :class:`~nexus_core.domain.Artifact`."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        serializer: VersionedSerializer | None = None,
        observability: Observability | None = None,
    ) -> None:
        super().__init__(
            "artifact", lambda a: a.identity, Artifact, connection, serializer, observability
        )


class DurablePolicyRepository(DurableRepository[Policy]):
    """Durable persistence adapter for :class:`~nexus_core.domain.Policy`."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        serializer: VersionedSerializer | None = None,
        observability: Observability | None = None,
    ) -> None:
        super().__init__(
            "policy", lambda p: p.identity, Policy, connection, serializer, observability
        )


class DurableKnowledgeRepository(DurableRepository[Knowledge]):
    """Durable persistence adapter for :class:`~nexus_core.domain.Knowledge`."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        serializer: VersionedSerializer | None = None,
        observability: Observability | None = None,
    ) -> None:
        super().__init__(
            "knowledge", lambda k: k.identity, Knowledge, connection, serializer, observability
        )


# --------------------------------------------------------------------------- #
# Durable Unit of Work
# --------------------------------------------------------------------------- #


class DurableUnitOfWork:
    """A transactional boundary over the shared SQLite connection (``UnitOfWork``).

    ``commit`` maps to **one durable SQLite transaction**: repository writes made
    during the block and the staged event batch are validated, appended, and
    committed atomically — a commit never lands a partial batch (ADR-007). Events
    are published to the bus **after** the durable commit, so the bus never sees an
    uncommitted fact. ``rollback`` (or an unclosed/failed block) issues a SQL
    ROLLBACK, undoing every write in the transaction.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        event_store: DurableEventStore,
        repositories: tuple[DurableRepository[Any], ...] = (),
        event_bus: InProcessEventBus | None = None,
        observability: Observability | None = None,
    ) -> None:
        self._conn = connection
        self._store = event_store
        self._repos = tuple(repositories)
        self._bus = event_bus
        self._obs: Observability = observability or NullObservability()
        self._pending: list[Event] = []
        self._active = False

    # -- context manager / protocol ------------------------------------------ #

    def __enter__(self) -> DurableUnitOfWork:
        self.begin()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> Literal[False]:
        if self._active:
            self.rollback()
        return False

    # -- lifecycle ----------------------------------------------------------- #

    def begin(self) -> None:
        if self._active:
            raise TransactionError("unit of work is already active")
        self._conn.execute("BEGIN")
        self._pending = []
        self._active = True

    def collect(self, event: Event) -> None:
        self._require_active()
        self._pending.append(event)

    def commit(self) -> None:
        self._require_active()
        self._validate_appendable(self._pending)  # raises before any append; txn stays open
        for event in self._pending:
            self._store.append(event)
        self._conn.execute("COMMIT")
        published = tuple(self._pending)
        self._finish()
        if self._bus is not None:
            for event in published:
                self._bus.publish(event)
        self._obs.record(
            InfraEvent(
                InfraEventType.TRANSACTION_COMMITTED,
                subject="uow",
                detail={"events": len(published)},
            )
        )
        self._obs.increment("uow.committed")

    def rollback(self) -> None:
        self._require_active()
        self._conn.execute("ROLLBACK")
        self._finish()
        self._obs.record(InfraEvent(InfraEventType.TRANSACTION_ROLLED_BACK, subject="uow"))
        self._obs.increment("uow.rolled_back")

    # -- introspection ------------------------------------------------------- #

    @property
    def active(self) -> bool:
        return self._active

    @property
    def pending_events(self) -> tuple[Event, ...]:
        return tuple(self._pending)

    # -- internals ----------------------------------------------------------- #

    def _validate_appendable(self, events: list[Event]) -> None:
        seen: set[str] = set()
        next_position: dict[str, int] = {}
        for event in events:
            if self._store.contains(event.identifier) or event.identifier in seen:
                raise DuplicateEventError(event.identifier)
            seen.add(event.identifier)
            stream = event.correlation_identifier
            expected = next_position.get(stream, self._store.stream_version(stream))
            if event.sequence_position is not None and event.sequence_position != expected:
                raise ConcurrencyConflictError(stream, event.sequence_position, expected)
            next_position[stream] = expected + 1

    def _require_active(self) -> None:
        if not self._active:
            raise TransactionError("no active unit of work")

    def _finish(self) -> None:
        self._pending = []
        self._active = False


# --------------------------------------------------------------------------- #
# Durable Snapshot Store
# --------------------------------------------------------------------------- #


class DurableSnapshotStore:
    """A SQLite-backed snapshot store with integrity, versioning, lineage, and expiry.

    ``create`` returns a record holding the original state (it is in hand);
    ``get``/``latest``/``restore`` reconstruct the state structurally from storage
    (value-equal, per ADR-001). Integrity and log-position-expiry semantics match
    the in-memory store exactly.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        observability: Observability | None = None,
    ) -> None:
        self._conn = connection
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
        exists = self._conn.execute(
            "SELECT 1 FROM snapshots WHERE identifier=?", (identifier,)
        ).fetchone()
        if exists is not None:
            raise IntegrityError(f"snapshot identifier {identifier!r} already exists")
        chash = content_hash(state)
        ordv = self._conn.execute("SELECT COALESCE(MAX(ord), 0) + 1 FROM snapshots").fetchone()[0]
        self._conn.execute(
            "INSERT INTO snapshots(identifier, key, ord, state, log_position, "
            "projection_version, content_hash, parent_identifier, expires_at_sequence) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                identifier,
                key,
                ordv,
                canonical_json(state),
                log_position,
                projection_version,
                chash,
                parent_identifier,
                expires_at_sequence,
            ),
        )
        self._obs.record(
            InfraEvent(
                InfraEventType.SNAPSHOT_CREATED,
                subject=identifier,
                at_sequence=log_position,
                detail={"key": key, "version": projection_version},
            )
        )
        self._obs.increment("snapshot.created")
        return SnapshotRecord(
            identifier=identifier,
            key=key,
            state=state,
            log_position=log_position,
            projection_version=projection_version,
            content_hash=chash,
            parent_identifier=parent_identifier,
            expires_at_sequence=expires_at_sequence,
        )

    def get(self, identifier: str) -> SnapshotRecord[Any]:
        row = self._conn.execute(
            "SELECT identifier, key, state, log_position, projection_version, "
            "content_hash, parent_identifier, expires_at_sequence "
            "FROM snapshots WHERE identifier=?",
            (identifier,),
        ).fetchone()
        if row is None:
            raise SnapshotNotFoundError(f"no snapshot with identifier {identifier!r}")
        return self._record(row)

    def latest(self, key: str) -> SnapshotRecord[Any] | None:
        row = self._conn.execute(
            "SELECT identifier, key, state, log_position, projection_version, "
            "content_hash, parent_identifier, expires_at_sequence "
            "FROM snapshots WHERE key=? ORDER BY ord DESC LIMIT 1",
            (key,),
        ).fetchone()
        return self._record(row) if row is not None else None

    def validate(self, record: SnapshotRecord[Any], current_sequence: int | None = None) -> None:
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
        rows = self._conn.execute(
            "SELECT identifier, key, state, log_position, projection_version, "
            "content_hash, parent_identifier, expires_at_sequence "
            "FROM snapshots WHERE key=? ORDER BY ord",
            (key,),
        ).fetchall()
        return tuple(self._record(r) for r in rows)

    def _record(self, row: tuple[Any, ...]) -> SnapshotRecord[Any]:
        identifier, key, state, log_position, version, chash, parent, expires = row
        return SnapshotRecord(
            identifier=identifier,
            key=key,
            state=json.loads(state),
            log_position=log_position,
            projection_version=version,
            content_hash=chash,
            parent_identifier=parent,
            expires_at_sequence=expires,
        )


# --------------------------------------------------------------------------- #
# Composition
# --------------------------------------------------------------------------- #


def build_durable_infrastructure(
    db_path: str,
    *,
    observability: Observability | None = None,
    clock: Clock | None = None,
    identifiers: Any | None = None,
    serializer: VersionedSerializer | None = None,
) -> Any:
    """Construct an :class:`InfrastructureContext` backed by durable SQLite storage.

    The returned context is structurally identical to :func:`build_infrastructure`'s
    — the same protocols, the same ``emit``/``unit_of_work``/``projection_engine``
    helpers — so no consumer can tell whether persistence is memory-backed or
    durable. The Unit of Work is bound to the shared connection via an injected
    factory.
    """
    from nexus_infra.composition import InfrastructureContext

    obs = observability or NullObservability()
    ser = serializer or VersionedSerializer()
    conn = connect(db_path)

    store = DurableEventStore(conn, ser, obs)
    snapshots = DurableSnapshotStore(conn, obs)

    def uow_factory(
        event_store: Any,
        repositories: tuple[Any, ...],
        event_bus: InProcessEventBus | None,
        observability: Observability,
    ) -> DurableUnitOfWork:
        return DurableUnitOfWork(conn, event_store, repositories, event_bus, observability)

    return InfrastructureContext(
        observability=obs,
        clock=clock or SystemClock(),
        identifiers=identifiers or UuidIdentifierFactory(),
        serializer=ser,
        upcasters=InMemoryUpcasterRegistry(),
        event_store=store,  # type: ignore[arg-type]  # protocol-compatible durable adapter
        event_bus=InProcessEventBus(obs),
        snapshot_store=snapshots,  # type: ignore[arg-type]
        goals=DurableGoalRepository(conn, ser, obs),  # type: ignore[arg-type]
        plans=DurablePlanRepository(conn, ser, obs),  # type: ignore[arg-type]
        artifacts=DurableArtifactRepository(conn, ser, obs),  # type: ignore[arg-type]
        policies=DurablePolicyRepository(conn, ser, obs),  # type: ignore[arg-type]
        knowledge=DurableKnowledgeRepository(conn, ser, obs),  # type: ignore[arg-type]
        unit_of_work_factory=uow_factory,
        _close_callback=conn.close,
    )
