"""Grounded planning composition — DI wiring over an infrastructure context.

Mirrors :func:`~nexus_planning.composition.build_planning`: it builds the incumbent Planning context
over the P1/P2 infrastructure (reusing its Plan/Work-Package/Graph/Strategy repositories and its event
emitter unchanged, durable transparently over ``build_durable_infrastructure`` — ADR-007), then adds
the :class:`~nexus_planning.grounded.assembler.GroundedPlanner` over that incumbent service. The
incumbent Planning subsystem is not modified.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.registries.interfaces import CapabilityRegistry
from nexus_infra import InfrastructureContext
from nexus_planning.composition import PlanningContext, build_planning
from nexus_planning.decomposition import DecompositionStrategy
from nexus_planning.events import TimestampSource
from nexus_planning.grounded.assembler import (
    GroundedPlanner,
    GroundedPlanningObservability,
)


@dataclass(frozen=True, slots=True)
class GroundedPlanningContext:
    """The wired grounded-planning layer (immutable wiring, stateful planner + incumbent service)."""

    infrastructure: InfrastructureContext
    planning: PlanningContext
    planner: GroundedPlanner


def build_grounded_planning(
    infrastructure: InfrastructureContext,
    *,
    capability_registry: CapabilityRegistry | None = None,
    decomposition: DecompositionStrategy | None = None,
    timestamps: TimestampSource | None = None,
) -> GroundedPlanningContext:
    """Wire a grounded-planning context over an infrastructure context; parts are overridable."""
    planning = build_planning(
        infrastructure,
        capability_registry=capability_registry,
        decomposition=decomposition,
        timestamps=timestamps,
    )
    planner = GroundedPlanner(
        planning.service,
        infrastructure,
        timestamps=timestamps,
        observability=GroundedPlanningObservability(infrastructure.observability),
    )
    return GroundedPlanningContext(
        infrastructure=infrastructure, planning=planning, planner=planner
    )
