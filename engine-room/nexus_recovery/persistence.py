"""Recovery persistence — the repository Recovery writes its own output through.

Recovery persists **only its own output**: the immutable Recovery Plans it produces. It
reuses the **Phase 2** ``InMemoryRepository`` mechanism unchanged (no new persistence layer).
It never writes the stores it *reads* from (the Validation Report, the Execution Result, the
event log) — those are inputs, and Recovery never mutates Validation or Execution (INV-22).
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.persistence.interfaces import Repository
from nexus_infra import InMemoryRepository, Observability
from nexus_recovery.plan import RecoveryPlan


@dataclass(frozen=True, slots=True)
class RecoveryRepositories:
    """The repository Recovery persists its own output through (Phase 2, reused)."""

    plans: Repository[RecoveryPlan]


def build_recovery_repositories(
    observability: Observability | None = None,
) -> RecoveryRepositories:
    """Wire the default recovery repositories over the Phase 2 ``InMemoryRepository``."""
    return RecoveryRepositories(
        plans=InMemoryRepository[RecoveryPlan](
            "recovery_plan", lambda p: p.identity, observability
        ),
    )
