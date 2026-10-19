"""Repository persistence — the repository Repository Intelligence writes its own profiles through.

It persists **only its own output** (the immutable RepositoryProfile). It reuses the P1
``InMemoryRepository`` mechanism unchanged (no new persistence layer); over a durable infrastructure
context the same profiles ride the durable substrate (ADR-007). It writes no store it reads from.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.persistence.interfaces import Repository
from nexus_infra import InMemoryRepository, Observability
from nexus_repository.profile import RepositoryProfile


@dataclass(frozen=True, slots=True)
class RepositoryRepositories:
    """The repository Repository Intelligence persists its profiles through (P1, reused)."""

    profiles: Repository[RepositoryProfile]


def build_repository_repositories(
    observability: Observability | None = None,
) -> RepositoryRepositories:
    """Wire the default repository-profile store over the P1 ``InMemoryRepository``."""
    return RepositoryRepositories(
        profiles=InMemoryRepository[RepositoryProfile](
            "repository_profile", lambda p: p.identity, observability
        )
    )
