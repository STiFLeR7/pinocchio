"""Runtime persistence — the repositories RM writes its own state through.

RM persists **only its own state**: the Runtime Sessions it creates and the Allocations
it reserves. It reuses the **Phase 2** ``InMemoryRepository`` mechanism unchanged — no new
persistence layer is invented (doc 00 §4). It never writes the repositories it *reads*
from (the Registry, the upstream package/manifest stores); those are inputs (doc 01 §3).

"Runtime metadata" (the Runtime Descriptors) is **not** persisted here: per INV-36 it lives
in the Harness Registry, which RM only reads through the Runtime Registry view (doc 04).
Duplicating it into a runtime-owned store would re-own availability/health — exactly what
INV-36 forbids.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.persistence.interfaces import Repository
from nexus_infra import InMemoryRepository, Observability
from nexus_runtime.allocation import Allocation
from nexus_runtime.runtime_session import RuntimeSession


@dataclass(frozen=True, slots=True)
class RuntimeRepositories:
    """The repositories RM persists its own outputs through (Phase 2 mechanism, reused)."""

    sessions: Repository[RuntimeSession]
    allocations: Repository[Allocation]


def build_runtime_repositories(observability: Observability | None = None) -> RuntimeRepositories:
    """Wire the default runtime repositories over the Phase 2 ``InMemoryRepository``."""
    return RuntimeRepositories(
        sessions=InMemoryRepository[RuntimeSession](
            "runtime_session", lambda s: s.identity, observability
        ),
        allocations=InMemoryRepository[Allocation](
            "runtime_allocation", lambda a: a.identity, observability
        ),
    )
