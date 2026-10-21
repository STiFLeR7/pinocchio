"""Reflection composition — dependency-injection wiring for the Reflection Engine.

Mirrors ``build_validation`` / ``build_recovery``: it **reuses** the Phase 2 infrastructure
substrate (the event emitter is the infrastructure context; the repositories are the Phase 2
``InMemoryRepository``; the metrics sink is its observability) rather than inventing anything.
The infrastructure is not modified. Every dependency is overridable and there is no
module-level singleton.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_infra import InfrastructureContext
from nexus_reflection.engine import ReflectionEngine
from nexus_reflection.observability import ReflectionObservability
from nexus_reflection.persistence import ReflectionRepositories, build_reflection_repositories
from nexus_runtime.events import TimestampSource


@dataclass(frozen=True, slots=True)
class ReflectionContextBundle:
    """The wired reflection layer (immutable wiring, stateful engine + repositories)."""

    infrastructure: InfrastructureContext
    repositories: ReflectionRepositories
    engine: ReflectionEngine


def build_reflection(
    infrastructure: InfrastructureContext,
    *,
    repositories: ReflectionRepositories | None = None,
    timestamps: TimestampSource | None = None,
) -> ReflectionContextBundle:
    """Wire a reflection context over an infrastructure context; all parts overridable."""
    obs = infrastructure.observability
    resolved = repositories or build_reflection_repositories(obs)
    engine = ReflectionEngine(
        infrastructure,
        repositories=resolved,
        observability=ReflectionObservability(obs),
        timestamps=timestamps,
    )
    return ReflectionContextBundle(
        infrastructure=infrastructure, repositories=resolved, engine=engine
    )
