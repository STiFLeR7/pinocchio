"""Step 7 — infrastructure composition (dependency injection, no global state).

Wires the substrate into one replaceable :class:`InfrastructureContext`. Every
dependency is injected; there is no module-level singleton, no service locator,
and no hidden global. Callers may take the defaults via :func:`build_infrastructure`
or construct the context directly with their own components (e.g. a deterministic
clock and identifier factory in tests, or alternative implementations later).

The context is itself the platform :class:`~nexus_core.events.interfaces.EventEmitter`:
``emit`` is the only way a fact becomes true — it appends to the authoritative log
and then publishes to the bus.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from nexus_core.domain.event import Event
from nexus_core.events.identifiers import IdentifierFactory
from nexus_core.persistence.interfaces import Projection, UnitOfWork
from nexus_infra.clock import Clock, SystemClock
from nexus_infra.event_bus import InProcessEventBus
from nexus_infra.event_store import InMemoryEventStore
from nexus_infra.event_versioning import InMemoryUpcasterRegistry
from nexus_infra.identifiers import UuidIdentifierFactory
from nexus_infra.observability import NullObservability, Observability
from nexus_infra.projections import ProjectionEngine
from nexus_infra.repositories import (
    ArtifactRepository,
    GoalRepository,
    InMemoryRepository,
    KnowledgeRepository,
    PlanRepository,
    PolicyRepository,
)
from nexus_infra.serialization import VersionedSerializer
from nexus_infra.snapshots import InMemorySnapshotStore
from nexus_infra.unit_of_work import InMemoryUnitOfWork

# A factory that builds a UnitOfWork from (event_store, repositories, event_bus,
# observability). Injected so the same context can be memory-backed or durable
# (ADR-007) without any consumer knowing which — the default is in-memory.
UnitOfWorkFactory = Callable[..., UnitOfWork]


@dataclass(frozen=True, slots=True)
class InfrastructureContext:
    """The wired infrastructure substrate (immutable wiring, stateful components)."""

    observability: Observability
    clock: Clock
    identifiers: IdentifierFactory
    serializer: VersionedSerializer
    upcasters: InMemoryUpcasterRegistry
    event_store: InMemoryEventStore
    event_bus: InProcessEventBus
    snapshot_store: InMemorySnapshotStore
    goals: GoalRepository
    plans: PlanRepository
    artifacts: ArtifactRepository
    policies: PolicyRepository
    knowledge: KnowledgeRepository
    unit_of_work_factory: UnitOfWorkFactory = InMemoryUnitOfWork
    _close_callback: Callable[[], None] | None = None

    def repositories(self) -> tuple[InMemoryRepository[Any], ...]:
        """All registered repositories (for the unit of work)."""
        return (self.goals, self.plans, self.artifacts, self.policies, self.knowledge)

    def close(self) -> None:
        """Close any owned durable resources; in-memory contexts have nothing to close."""
        if self._close_callback is not None:
            self._close_callback()

    def __enter__(self) -> InfrastructureContext:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def emit(self, event: Event) -> None:
        """Append ``event`` to the authoritative log, then publish it (EventEmitter)."""
        self.event_store.append(event)
        self.event_bus.publish(event)

    def unit_of_work(self) -> UnitOfWork:
        """A fresh unit of work bound to this context's store, repos, and bus.

        Uses the injected :attr:`unit_of_work_factory` (default: in-memory), so a
        durable context (ADR-007) returns a durable, transactional Unit of Work
        without any consumer knowing the difference.
        """
        return self.unit_of_work_factory(
            self.event_store, self.repositories(), self.event_bus, self.observability
        )

    def projection_engine[S](
        self, factory: Callable[[], Projection[S]], *, version: int = 1
    ) -> ProjectionEngine[S]:
        """A projection engine wired with this context's upcasters and observability."""
        return ProjectionEngine(
            factory, version=version, upcasters=self.upcasters, observability=self.observability
        )


def build_infrastructure(
    *,
    observability: Observability | None = None,
    clock: Clock | None = None,
    identifiers: IdentifierFactory | None = None,
    serializer: VersionedSerializer | None = None,
) -> InfrastructureContext:
    """Construct a default infrastructure context; every part is overridable."""
    obs = observability or NullObservability()
    return InfrastructureContext(
        observability=obs,
        clock=clock or SystemClock(),
        identifiers=identifiers or UuidIdentifierFactory(),
        serializer=serializer or VersionedSerializer(),
        upcasters=InMemoryUpcasterRegistry(),
        event_store=InMemoryEventStore(obs),
        event_bus=InProcessEventBus(obs),
        snapshot_store=InMemorySnapshotStore(obs),
        goals=GoalRepository(obs),
        plans=PlanRepository(obs),
        artifacts=ArtifactRepository(obs),
        policies=PolicyRepository(obs),
        knowledge=KnowledgeRepository(obs),
    )
