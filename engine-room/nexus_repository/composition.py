"""Repository composition — dependency-injection wiring for Repository Intelligence.

Mirrors ``build_estimation`` / ``build_engineering`` / ``build_intent``: it **reuses** the P1
substrate unchanged (emitter = the infrastructure context, repository = a reused
``InMemoryRepository``, metrics = the context's observability). Integration is additive DI only; no
engine is modified. Durable persistence is transparent over ``build_durable_infrastructure``
(ADR-007). It imports no downstream engine — grounding depends only on the foundation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from nexus_infra import InfrastructureContext
from nexus_repository.engine import SCANNER_VERSION, RepositoryIntelligence
from nexus_repository.observability import RepositoryObservability
from nexus_repository.persistence import RepositoryRepositories, build_repository_repositories


@dataclass(frozen=True, slots=True)
class RepositoryContext:
    """The wired Repository-Intelligence subsystem (immutable wiring, stateful engine + repository)."""

    infrastructure: InfrastructureContext
    repositories: RepositoryRepositories
    engine: RepositoryIntelligence


def build_repository(
    infrastructure: InfrastructureContext,
    *,
    repositories: RepositoryRepositories | None = None,
    now: Callable[[], str] | None = None,
    scanner_version: str = SCANNER_VERSION,
) -> RepositoryContext:
    """Wire a repository-intelligence context over an infrastructure context; all parts overridable."""
    obs = infrastructure.observability
    resolved = repositories or build_repository_repositories(obs)
    engine = RepositoryIntelligence(
        emitter=infrastructure,
        repositories=resolved,
        observability=RepositoryObservability(obs),
        now=now,
        scanner_version=scanner_version,
    )
    return RepositoryContext(infrastructure=infrastructure, repositories=resolved, engine=engine)
