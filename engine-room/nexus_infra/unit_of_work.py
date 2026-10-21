"""Step 6 — the Unit of Work (transactional boundary).

Coordinates a set of repositories, the event store, and the event bus under one
atomic boundary. Repository writes happen live but are snapshotted at ``begin``
so :meth:`rollback` can restore them; events are *staged* and flushed only on
:meth:`commit`. Transaction semantics are implementation-independent: the same
contract would hold over a SQL transaction.

Commit is atomic: before appending anything, every staged event is validated for
appendability (no duplicate identifier, consistent stream position). If that
check fails, nothing is appended and repositories are rolled back — so a commit
never lands a partial batch.

Used as a context manager. Exiting without an explicit :meth:`commit` — or via an
exception — rolls back.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Literal

from nexus_core.domain.event import Event
from nexus_infra.errors import (
    ConcurrencyConflictError,
    DuplicateEventError,
    TransactionError,
)
from nexus_infra.event_bus import InProcessEventBus
from nexus_infra.event_store import InMemoryEventStore
from nexus_infra.observability import (
    InfraEvent,
    InfraEventType,
    NullObservability,
    Observability,
)
from nexus_infra.repositories import InMemoryRepository


class InMemoryUnitOfWork:
    """A transactional boundary implementing ``UnitOfWork``."""

    def __init__(
        self,
        event_store: InMemoryEventStore,
        repositories: tuple[InMemoryRepository[Any], ...] = (),
        event_bus: InProcessEventBus | None = None,
        observability: Observability | None = None,
    ) -> None:
        self._store = event_store
        self._repos = tuple(repositories)
        self._bus = event_bus
        self._obs: Observability = observability or NullObservability()
        self._snapshots: list[
            tuple[InMemoryRepository[Any], tuple[dict[str, Any], dict[str, int]]]
        ] = []
        self._pending: list[Event] = []
        self._active = False

    # -- context manager / protocol ------------------------------------------ #

    def __enter__(self) -> InMemoryUnitOfWork:
        self.begin()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        if self._active:
            self.rollback()
        return False

    # -- lifecycle ----------------------------------------------------------- #

    def begin(self) -> None:
        """Open the transaction and snapshot every repository's state."""
        if self._active:
            raise TransactionError("unit of work is already active")
        self._snapshots = [(repo, repo._capture()) for repo in self._repos]
        self._pending = []
        self._active = True

    def collect(self, event: Event) -> None:
        """Stage an event to be appended (and published) on commit."""
        self._require_active()
        self._pending.append(event)

    def commit(self) -> None:
        """Atomically flush staged events, then make the transaction durable."""
        self._require_active()
        self._validate_appendable(self._pending)  # raises before any side effect
        for event in self._pending:
            self._store.append(event)
            if self._bus is not None:
                self._bus.publish(event)
        flushed = len(self._pending)
        self._finish()
        self._obs.record(
            InfraEvent(
                InfraEventType.TRANSACTION_COMMITTED, subject="uow", detail={"events": flushed}
            )
        )
        self._obs.increment("uow.committed")

    def rollback(self) -> None:
        """Discard staged events and restore every repository to its begin-state."""
        self._require_active()
        for repo, snapshot in self._snapshots:
            repo._apply(snapshot)
        self._finish()
        self._obs.record(InfraEvent(InfraEventType.TRANSACTION_ROLLED_BACK, subject="uow"))
        self._obs.increment("uow.rolled_back")

    # -- introspection ------------------------------------------------------- #

    @property
    def active(self) -> bool:
        """Whether the transaction is currently open."""
        return self._active

    @property
    def pending_events(self) -> tuple[Event, ...]:
        """Events staged but not yet committed."""
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
        self._snapshots = []
        self._pending = []
        self._active = False
