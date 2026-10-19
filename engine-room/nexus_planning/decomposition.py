"""Plan decomposition seam.

Phase 3 contains no AI: decomposition is *explicit*. The
:class:`DecompositionStrategy` Protocol is the dependency-inversion seam where a
future intelligent decomposer (a later phase) would generate work items from a
Goal. The Phase 3 implementation, :class:`ExplicitDecompositionStrategy`, simply
returns the request's declared decomposition unchanged — keeping planning fully
deterministic.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from nexus_core.domain.goal import Goal
from nexus_planning.requests import PlanningRequest


@runtime_checkable
class DecompositionStrategy(Protocol):
    """Produces the effective planning request (work decomposition) for a Goal."""

    def decompose(self, goal: Goal, request: PlanningRequest) -> PlanningRequest: ...


class ExplicitDecompositionStrategy:
    """Returns the explicitly declared decomposition unchanged (deterministic)."""

    def decompose(self, goal: Goal, request: PlanningRequest) -> PlanningRequest:
        return request
