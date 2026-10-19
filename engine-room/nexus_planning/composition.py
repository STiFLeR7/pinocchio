"""Planning composition — dependency-injection wiring (no global state).

Assembles the planning layer over a Phase 2 :class:`InfrastructureContext`. It
**reuses** the infrastructure substrate rather than inventing persistence: the
existing ``plans`` repository is used as-is, and the Work Package / Execution
Graph / Execution Strategy repositories are instances of the same Phase 2
``InMemoryRepository`` generic. The Plan emitter is the infrastructure context
itself (``emit`` = append-to-log then publish).

Every dependency is injected and overridable; there is no module-level singleton.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_core.domain.work_package import WorkPackage
from nexus_core.registries.interfaces import CapabilityRegistry
from nexus_infra import InfrastructureContext, InMemoryRepository
from nexus_planning.capability_resolver import CapabilityResolver, InMemoryCapabilityRegistry
from nexus_planning.decomposition import DecompositionStrategy
from nexus_planning.events import TimestampSource
from nexus_planning.planner import PlanningRepositories, PlanningService


@dataclass(frozen=True, slots=True)
class PlanningContext:
    """The wired planning layer (immutable wiring, stateful components)."""

    infrastructure: InfrastructureContext
    repositories: PlanningRepositories
    capability_registry: CapabilityRegistry
    capability_resolver: CapabilityResolver
    service: PlanningService


def build_planning(
    infrastructure: InfrastructureContext,
    *,
    capability_registry: CapabilityRegistry | None = None,
    decomposition: DecompositionStrategy | None = None,
    timestamps: TimestampSource | None = None,
) -> PlanningContext:
    """Wire a planning context over an infrastructure context; all parts overridable."""
    registry: CapabilityRegistry = capability_registry or InMemoryCapabilityRegistry()
    obs = infrastructure.observability
    repositories = PlanningRepositories(
        plans=infrastructure.plans,
        work_packages=InMemoryRepository[WorkPackage]("work_package", lambda w: w.identifier, obs),
        execution_graphs=InMemoryRepository[ExecutionGraph](
            "execution_graph", lambda g: g.identity, obs
        ),
        execution_strategies=InMemoryRepository[ExecutionStrategy](
            "execution_strategy", lambda s: s.identity, obs
        ),
    )
    resolver = CapabilityResolver(registry)
    service = PlanningService(
        repositories,
        resolver,
        infrastructure,
        decomposition=decomposition,
        timestamps=timestamps,
    )
    return PlanningContext(
        infrastructure=infrastructure,
        repositories=repositories,
        capability_registry=registry,
        capability_resolver=resolver,
        service=service,
    )
