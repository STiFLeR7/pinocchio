"""Shared fixtures for the P10 grounded-planning suite — genuine upstream artifacts.

Builds a real EngineeringStrategy (P5) and a real ContextPackage (P9, via the incumbent Context
Engineering producer) so the tests exercise true three-input integration. Deterministic throughout
(fixed timestamps, clock-free ids).
"""

from __future__ import annotations

from nexus_context import ContextRequest, build_context_engineering
from nexus_infra import InfrastructureContext, build_infrastructure
from nexus_planning import FixedTimestampSource, WorkItemSpec
from nexus_planning.grounded import GroundedPlanningContext, PlanningInputs, build_grounded_planning
from tests.unit.nexus_engineering.fixtures import make_goal, strategy_for


def item(key: str, **overrides) -> WorkItemSpec:
    return WorkItemSpec(key=key, objective=overrides.pop("objective", f"do {key}"), **overrides)


def make_context(goal):
    """A real, deterministic ContextPackage from the incumbent Context Engineering producer."""
    infra = build_infrastructure()
    return build_context_engineering(infra).service.engineer(goal, ContextRequest()).package


def make_inputs(
    *,
    goal=None,
    strategy: bool = True,
    context: bool = True,
    work_items: tuple[WorkItemSpec, ...] = (),
) -> PlanningInputs:
    goal = goal or make_goal()
    return PlanningInputs(
        goal=goal,
        engineering_strategy=strategy_for(goal, persist=False) if strategy else None,
        context_package=make_context(goal) if context else None,
        work_items=work_items,
    )


def wired_grounded() -> tuple[InfrastructureContext, GroundedPlanningContext]:
    """A fresh infra plus a grounded-planning context with a fixed clock."""
    infra = build_infrastructure()
    return infra, build_grounded_planning(infra, timestamps=FixedTimestampSource())
