"""``nexus_infra`` — Phase 2 infrastructure layer for Nexus v2.

Concrete, generic implementations of the foundation's interfaces
(``nexus_core.events`` / ``nexus_core.persistence``): an append-only event store,
an in-process event bus, a projection engine, a snapshot store, repositories, a
unit of work, and the composition that wires them.

This layer is **infrastructure only**. It contains no business logic, no
orchestration, no planning, no runtime/AI execution — those are later phases that
*consume* this substrate without modifying it. The dependency direction is
one-way: ``nexus_infra → nexus_core`` (never the reverse).

Design rules:

- **Event-sourced (ADR-001).** The event store is the authoritative, append-only
  log; state is a projection; snapshots are derived and carry a log position.
- **Deterministic.** Ordering uses an internal monotonic counter, not a clock;
  every clock/uniqueness dependency is an injected interface so tests are 100%
  reproducible.
- **Idempotent (INV-16).** Duplicate or out-of-order delivery causes no duplicate
  effect; projections dedupe by event identifier.
- **Optimistic concurrency.** Append and repository writes assert an expected
  version and raise on conflict; no locking.
- **Dependency injection, no global state.** Composition is explicit and
  replaceable (see :mod:`nexus_infra.composition`).
"""

from __future__ import annotations

from nexus_infra.clock import Clock, ManualClock, SystemClock
from nexus_infra.composition import InfrastructureContext, build_infrastructure
from nexus_infra.durable import (
    DurableArtifactRepository,
    DurableEventStore,
    DurableGoalRepository,
    DurableKnowledgeRepository,
    DurablePlanRepository,
    DurablePolicyRepository,
    DurableRepository,
    DurableSnapshotStore,
    DurableUnitOfWork,
    build_durable_infrastructure,
    connect,
)
from nexus_infra.errors import (
    ConcurrencyConflictError,
    DeadLetterError,
    DuplicateEventError,
    InfrastructureError,
    IntegrityError,
    SnapshotExpiredError,
    SnapshotNotFoundError,
    TransactionError,
    UpcastError,
)
from nexus_infra.event_bus import DeadLetter, InProcessEventBus, accept_all, by_correlation, by_type
from nexus_infra.event_store import InMemoryEventStore, StoredEvent
from nexus_infra.event_versioning import InMemoryUpcasterRegistry
from nexus_infra.identifiers import DeterministicIdentifierFactory, UuidIdentifierFactory
from nexus_infra.observability import (
    InfraEvent,
    InfraEventType,
    InMemoryObservability,
    LoggingObservability,
    NullObservability,
    Observability,
)
from nexus_infra.projections import ProjectionEngine
from nexus_infra.repositories import (
    ArtifactRepository,
    GoalRepository,
    InMemoryRepository,
    KnowledgeRepository,
    PlanRepository,
    PolicyRepository,
)
from nexus_infra.serialization import VersionedSerializer, canonical_json, content_hash
from nexus_infra.snapshots import InMemorySnapshotStore, SnapshotRecord
from nexus_infra.unit_of_work import InMemoryUnitOfWork

__version__ = "2.5.0"

__all__ = [
    "ArtifactRepository",
    "Clock",
    "ConcurrencyConflictError",
    "DeadLetter",
    "DeadLetterError",
    "DeterministicIdentifierFactory",
    "DuplicateEventError",
    "DurableArtifactRepository",
    "DurableEventStore",
    "DurableGoalRepository",
    "DurableKnowledgeRepository",
    "DurablePlanRepository",
    "DurablePolicyRepository",
    "DurableRepository",
    "DurableSnapshotStore",
    "DurableUnitOfWork",
    "GoalRepository",
    "InMemoryEventStore",
    "InMemoryObservability",
    "InMemoryRepository",
    "InMemorySnapshotStore",
    "InMemoryUnitOfWork",
    "InMemoryUpcasterRegistry",
    "InProcessEventBus",
    "InfraEvent",
    "InfraEventType",
    "InfrastructureContext",
    "InfrastructureError",
    "IntegrityError",
    "KnowledgeRepository",
    "LoggingObservability",
    "ManualClock",
    "NullObservability",
    "Observability",
    "PlanRepository",
    "PolicyRepository",
    "ProjectionEngine",
    "SnapshotExpiredError",
    "SnapshotNotFoundError",
    "SnapshotRecord",
    "StoredEvent",
    "SystemClock",
    "TransactionError",
    "UpcastError",
    "UuidIdentifierFactory",
    "VersionedSerializer",
    "accept_all",
    "build_durable_infrastructure",
    "build_infrastructure",
    "by_correlation",
    "by_type",
    "canonical_json",
    "connect",
    "content_hash",
]
