"""Estimation composition — dependency-injection wiring for the Estimation Engine.

Mirrors ``build_validation`` / ``build_policy``: it **reuses** the P1 infrastructure substrate
unchanged — the emitter is the infrastructure context, the report repository is a reused
``InMemoryRepository``, the metrics sink is the context's observability. Nothing in the
infrastructure is modified; integration is additive DI only. Durable persistence is transparent
over a context from ``build_durable_infrastructure`` (ADR-007). Every dependency is overridable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from nexus_estimation.baseline import DEFAULT_MODEL, EstimationModel
from nexus_estimation.engine import EstimationEngine
from nexus_estimation.observability import EstimationObservability
from nexus_estimation.persistence import EstimationRepositories, build_estimation_repositories
from nexus_infra import InfrastructureContext


@dataclass(frozen=True, slots=True)
class EstimationContext:
    """The wired estimation subsystem (immutable wiring, stateful engine + repository)."""

    infrastructure: InfrastructureContext
    model: EstimationModel
    repositories: EstimationRepositories
    engine: EstimationEngine


def build_estimation(
    infrastructure: InfrastructureContext,
    *,
    model: EstimationModel = DEFAULT_MODEL,
    repositories: EstimationRepositories | None = None,
    now: Callable[[], str] | None = None,
) -> EstimationContext:
    """Wire an estimation context over an infrastructure context; all parts overridable."""
    obs = infrastructure.observability
    resolved = repositories or build_estimation_repositories(obs)
    engine = EstimationEngine(
        model,
        emitter=infrastructure,
        repositories=resolved,
        observability=EstimationObservability(obs),
        now=now,
    )
    return EstimationContext(
        infrastructure=infrastructure, model=model, repositories=resolved, engine=engine
    )
