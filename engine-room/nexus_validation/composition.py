"""Validation composition — dependency-injection wiring for the Validation Engine.

Mirrors ``build_runtime`` / ``build_execution``: it **reuses** the Phase 2 infrastructure
substrate (the event emitter is the infrastructure context; repositories are the Phase 2
``InMemoryRepository``; the metrics sink is its observability) rather than inventing
anything. The infrastructure is not modified. Every dependency is overridable and there is
no module-level singleton.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_infra import InfrastructureContext
from nexus_runtime.events import TimestampSource
from nexus_validation.engine import ValidationEngine
from nexus_validation.observability import ValidationObservability
from nexus_validation.persistence import ValidationRepositories, build_validation_repositories


@dataclass(frozen=True, slots=True)
class ValidationContext:
    """The wired validation layer (immutable wiring, stateful engine + repositories)."""

    infrastructure: InfrastructureContext
    repositories: ValidationRepositories
    engine: ValidationEngine


def build_validation(
    infrastructure: InfrastructureContext,
    *,
    repositories: ValidationRepositories | None = None,
    timestamps: TimestampSource | None = None,
) -> ValidationContext:
    """Wire a validation context over an infrastructure context; all parts overridable."""
    obs = infrastructure.observability
    resolved = repositories or build_validation_repositories(obs)
    engine = ValidationEngine(
        infrastructure,
        repositories=resolved,
        observability=ValidationObservability(obs),
        timestamps=timestamps,
    )
    return ValidationContext(infrastructure=infrastructure, repositories=resolved, engine=engine)
