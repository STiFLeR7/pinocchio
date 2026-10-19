"""Persistence abstractions (Step 7) — interfaces only. No database.

These define how later phases will store and reconstruct operational state
*without* committing to any technology (no SQLite, no Postgres, no concrete event
store — those are Phase-2 decisions, ADR-001/AP-201). Per ADR-001, the
``EventStore`` is the authoritative substrate; ``Projection`` folds events into a
read model (current state is a projection); ``Snapshot`` materializes a checkpoint;
``Serializer`` is format-agnostic (wire format deferred to AP-101).
"""

from nexus_core.persistence.interfaces import (
    EventStore,
    Projection,
    Repository,
    Serializer,
    Snapshot,
    UnitOfWork,
)

__all__ = [
    "EventStore",
    "Projection",
    "Repository",
    "Serializer",
    "Snapshot",
    "UnitOfWork",
]
