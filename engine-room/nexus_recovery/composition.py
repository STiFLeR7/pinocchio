"""Recovery composition — dependency-injection wiring for the Recovery Engine.

Mirrors ``build_execution`` / ``build_validation``: it **reuses** the Phase 2 infrastructure
substrate (the event emitter is the infrastructure context; the repository is the Phase 2
``InMemoryRepository``; the metrics sink is its observability) rather than inventing anything.
The infrastructure is not modified. Every dependency is overridable and there is no
module-level singleton.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_infra import InfrastructureContext
from nexus_recovery.engine import RecoveryEngine
from nexus_recovery.observability import RecoveryObservability
from nexus_recovery.persistence import RecoveryRepositories, build_recovery_repositories
from nexus_runtime.events import TimestampSource


@dataclass(frozen=True, slots=True)
class RecoveryContextBundle:
    """The wired recovery layer (immutable wiring, stateful engine + repositories)."""

    infrastructure: InfrastructureContext
    repositories: RecoveryRepositories
    engine: RecoveryEngine


def build_recovery(
    infrastructure: InfrastructureContext,
    *,
    repositories: RecoveryRepositories | None = None,
    timestamps: TimestampSource | None = None,
) -> RecoveryContextBundle:
    """Wire a recovery context over an infrastructure context; all parts overridable."""
    obs = infrastructure.observability
    resolved = repositories or build_recovery_repositories(obs)
    engine = RecoveryEngine(
        infrastructure,
        repositories=resolved,
        observability=RecoveryObservability(obs),
        timestamps=timestamps,
    )
    return RecoveryContextBundle(
        infrastructure=infrastructure, repositories=resolved, engine=engine
    )
