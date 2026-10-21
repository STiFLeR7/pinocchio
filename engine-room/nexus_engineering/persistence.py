"""Engineering persistence — the repository EI writes its own Strategies through.

EI persists **only its own output** (the immutable Engineering Strategy). It reuses the P1
``InMemoryRepository`` mechanism unchanged (no new persistence layer); over a durable
infrastructure context the same Strategies ride the durable substrate (ADR-007). It never writes
the stores it reads from — its inputs are immutable facts it never mutates.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.persistence.interfaces import Repository
from nexus_engineering.model import EngineeringStrategy
from nexus_infra import InMemoryRepository, Observability


@dataclass(frozen=True, slots=True)
class EngineeringRepositories:
    """The repository EI persists its Strategies through (P1, reused)."""

    strategies: Repository[EngineeringStrategy]


def build_engineering_repositories(
    observability: Observability | None = None,
) -> EngineeringRepositories:
    """Wire the default engineering repository over the P1 ``InMemoryRepository``."""
    return EngineeringRepositories(
        strategies=InMemoryRepository[EngineeringStrategy](
            "engineering_strategy", lambda s: s.identity, observability
        )
    )
