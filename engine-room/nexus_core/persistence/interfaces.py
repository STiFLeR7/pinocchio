"""Persistence interface definitions — abstractions only.

Every type here is a ``Protocol``: a seam later phases implement. Nothing here
opens a connection, chooses a format, or touches storage. This keeps the domain
and the rest of the foundation free of infrastructure coupling (dependency
inversion): higher layers depend on these abstractions, implementations are
injected.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import TracebackType
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from nexus_core.domain.event import Event


@runtime_checkable
class Serializer(Protocol):
    """Format-agnostic structural (de)serialization of domain objects.

    Returns/consumes a plain mapping; the concrete wire format (JSON, msgpack,
    …) is deferred to AP-101. Round-tripping must be identity-preserving.
    """

    def serialize(self, obj: BaseModel) -> Mapping[str, Any]: ...

    def deserialize[M: BaseModel](self, model_type: type[M], data: Mapping[str, Any]) -> M: ...


@runtime_checkable
class Repository[T: BaseModel](Protocol):
    """Stores and retrieves whole domain objects by identity (a CRUD-free read model).

    A repository never mutates a stored object in place (objects are immutable);
    a new version replaces a prior one by identity.
    """

    def get(self, identifier: str) -> T | None: ...

    def add(self, obj: T) -> None: ...

    def list_all(self) -> tuple[T, ...]: ...


@runtime_checkable
class EventStore(Protocol):
    """The authoritative append-only log (ADR-001). Append and read only — never update."""

    def append(self, event: Event) -> None: ...

    def read_stream(self, correlation_identifier: str) -> Iterable[Event]: ...

    def read_all(self) -> Iterable[Event]: ...


@runtime_checkable
class Projection[S](Protocol):
    """A read model folded from the event log. Current state is a projection (ADR-001).

    ``apply`` must be idempotent in the presence of duplicate delivery (INV-16),
    and deterministic so replay reproduces identical state.
    """

    def apply(self, event: Event) -> None: ...

    @property
    def state(self) -> S: ...


@runtime_checkable
class Snapshot[S](Protocol):
    """Materializes/restores a projection's state — the basis for checkpoints.

    A snapshot is derived from the log at a position; restoring it plus replaying
    the tail reconstructs current state (INV-14, INV-18).
    """

    def capture(self) -> S: ...

    def restore(self, state: S) -> None: ...


@runtime_checkable
class UnitOfWork(Protocol):
    """Transactional boundary for a set of persistence operations.

    Used as a context manager; ``commit`` makes changes durable, ``rollback``
    discards them. The foundation defines the boundary only; the transactional
    machinery is a later-phase implementation detail.
    """

    def __enter__(self) -> UnitOfWork: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
