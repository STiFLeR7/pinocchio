"""Step 5 — Repository implementations (persistence adapters only).

A repository stores and retrieves whole, immutable domain objects by identity. It
holds **no business logic**: no validation orchestration, no policy, no
transitions — those belong to higher layers. Because domain objects are frozen,
a write never mutates in place; it replaces the prior version by identity and
bumps an optimistic-concurrency version.

The generic :class:`InMemoryRepository` is the single adapter; the concrete
repositories merely bind the model type, its identity accessor, and a name. They
deliberately add no methods — a repository is a storage seam, not a service.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from nexus_core.domain import Artifact, Goal, Knowledge, Plan, Policy
from nexus_infra.errors import ConcurrencyConflictError
from nexus_infra.observability import (
    InfraEvent,
    InfraEventType,
    NullObservability,
    Observability,
)


class InMemoryRepository[T: BaseModel]:
    """A local, identity-keyed store implementing ``Repository[T]``."""

    def __init__(
        self,
        name: str,
        key: Callable[[T], str],
        observability: Observability | None = None,
    ) -> None:
        self._name = name
        self._key = key
        self._items: dict[str, T] = {}
        self._versions: dict[str, int] = {}
        self._obs: Observability = observability or NullObservability()

    # -- Repository protocol ------------------------------------------------- #

    def get(self, identifier: str) -> T | None:
        """The current object for ``identifier``, or ``None``."""
        return self._items.get(identifier)

    def add(self, obj: T) -> None:
        """Insert or replace ``obj`` by its identity (a new immutable version)."""
        self._write(obj)

    def list_all(self) -> tuple[T, ...]:
        """Every current object, in insertion order (deterministic)."""
        return tuple(self._items.values())

    # -- optimistic concurrency ---------------------------------------------- #

    def add_expecting(self, obj: T, expected_version: int) -> None:
        """Write ``obj`` only if its stored version matches ``expected_version``."""
        identity = self._key(obj)
        current = self._versions.get(identity, 0)
        if current != expected_version:
            self._obs.increment("repository.concurrency_conflict")
            raise ConcurrencyConflictError(f"{self._name}:{identity}", expected_version, current)
        self._write(obj)

    def version_of(self, identifier: str) -> int:
        """The current write version for ``identifier`` (``0`` if absent)."""
        return self._versions.get(identifier, 0)

    # -- conveniences -------------------------------------------------------- #

    def contains(self, identifier: str) -> bool:
        """Whether an object with ``identifier`` is stored."""
        return identifier in self._items

    def remove(self, identifier: str) -> None:
        """Delete an object by identity (no error if absent)."""
        self._items.pop(identifier, None)
        self._versions.pop(identifier, None)

    @property
    def name(self) -> str:
        """The repository's logical name (the object kind it stores)."""
        return self._name

    @property
    def count(self) -> int:
        """How many objects are stored."""
        return len(self._items)

    # -- transactional hooks (used by the Unit of Work) ---------------------- #

    def _capture(self) -> tuple[dict[str, T], dict[str, int]]:
        """Snapshot internal state for transactional rollback (frozen objects → shallow copy)."""
        return dict(self._items), dict(self._versions)

    def _apply(self, snapshot: tuple[dict[str, T], dict[str, int]]) -> None:
        """Restore internal state captured by :meth:`_capture`."""
        items, versions = snapshot
        self._items = dict(items)
        self._versions = dict(versions)

    def _write(self, obj: T) -> None:
        identity = self._key(obj)
        self._items[identity] = obj
        self._versions[identity] = self._versions.get(identity, 0) + 1
        self._obs.record(
            InfraEvent(InfraEventType.REPOSITORY_WRITE, subject=f"{self._name}:{identity}")
        )
        self._obs.increment("repository.write")


class GoalRepository(InMemoryRepository[Goal]):
    """Persistence adapter for :class:`~nexus_core.domain.Goal`."""

    def __init__(self, observability: Observability | None = None) -> None:
        super().__init__("goal", lambda g: g.identity, observability)


class PlanRepository(InMemoryRepository[Plan]):
    """Persistence adapter for :class:`~nexus_core.domain.Plan`."""

    def __init__(self, observability: Observability | None = None) -> None:
        super().__init__("plan", lambda p: p.identity, observability)


class ArtifactRepository(InMemoryRepository[Artifact]):
    """Persistence adapter for :class:`~nexus_core.domain.Artifact`."""

    def __init__(self, observability: Observability | None = None) -> None:
        super().__init__("artifact", lambda a: a.identity, observability)


class PolicyRepository(InMemoryRepository[Policy]):
    """Persistence adapter for :class:`~nexus_core.domain.Policy`."""

    def __init__(self, observability: Observability | None = None) -> None:
        super().__init__("policy", lambda p: p.identity, observability)


class KnowledgeRepository(InMemoryRepository[Knowledge]):
    """Persistence adapter for :class:`~nexus_core.domain.Knowledge`."""

    def __init__(self, observability: Observability | None = None) -> None:
        super().__init__("knowledge", lambda k: k.identity, observability)
