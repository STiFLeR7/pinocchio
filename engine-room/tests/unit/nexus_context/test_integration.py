"""Pipeline integration: Goal → Context Engineering → Context Package → Planning.

Phase 4 sits *upstream* of Planning. This module proves the two layers compose
into the documented pipeline **by reference**, with no coupling in either
direction:

    Goal → Context Engineering → Context Package → Planning → …

Context Engineering produces a validated :class:`ContextPackage`; the
:func:`context_reference` seam turns it into a by-id ``Reference``; Planning
consumes that reference verbatim as ``PlanningRequest.context_ref`` and stamps it
onto every generated Work Package (``work_package_generator`` uses
``request.context_ref`` when provided). The final test guards the one-way
dependency direction: ``nexus_context`` never imports ``nexus_planning``.
"""

from __future__ import annotations

import inspect

from nexus_context import context_reference
from nexus_core.contracts.base import Reference
from nexus_core.domain import Goal
from nexus_core.domain.context_package import ContextPackage
from nexus_infra import build_infrastructure
from nexus_planning import (
    FixedTimestampSource,
    PlanningRequest,
    WorkItemSpec,
    build_planning,
)
from tests.unit.nexus_context.helpers import (
    context_env,
    fragment,
    make_goal,
    request,
)


def _context_package(goal: Goal) -> ContextPackage:
    """Engineer a context package for ``goal`` over a fresh context environment."""
    ctx = context_env()
    result = ctx.context.service.engineer(
        goal,
        request(fragment("repo"), fragment("notes")),
    )
    return result.package


# --------------------------------------------------------------------------- #
# 1. context_reference builds the by-id Reference Planning consumes.          #
# --------------------------------------------------------------------------- #


def test_context_reference_targets_the_package_by_id() -> None:
    goal = make_goal("goal-pipeline")
    package = _context_package(goal)

    ref = context_reference(package)

    assert isinstance(ref, Reference)
    assert ref.target_type == "context_package"
    assert ref.identifier == package.identity


# --------------------------------------------------------------------------- #
# 2. Planning consumes the context reference end to end.                      #
# --------------------------------------------------------------------------- #


def test_planning_stamps_context_reference_onto_work_packages() -> None:
    goal = make_goal("goal-pipeline")
    package = _context_package(goal)
    ref = context_reference(package)

    planning = build_planning(build_infrastructure(), timestamps=FixedTimestampSource())
    plan_request = PlanningRequest(
        work_items=(WorkItemSpec(key="research", objective="Investigate the operational context"),),
        context_ref=ref,
    )

    result = planning.service.plan(goal, plan_request)

    # A plan and its work packages were produced.
    assert result.plan is not None
    assert len(result.work_packages) == 1

    # Every generated Work Package carries the engineered context by reference.
    generated = result.work_packages[0]
    assert generated.context == ref
    assert generated.context.identifier == ref.identifier

    # The plan was persisted through the planning repositories.
    assert planning.repositories.plans.get(result.plan.identity) == result.plan


def test_plan_without_context_ref_uses_default_reference() -> None:
    """The pipeline is opt-in: omitting ``context_ref`` yields the goal-derived default."""
    goal = make_goal("goal-default")

    planning = build_planning(build_infrastructure(), timestamps=FixedTimestampSource())
    plan_request = PlanningRequest(
        work_items=(WorkItemSpec(key="research", objective="Investigate"),),
    )

    result = planning.service.plan(goal, plan_request)
    generated = result.work_packages[0]

    assert generated.context.target_type == "context_package"
    assert generated.context.identifier == "context-goal-default"


# --------------------------------------------------------------------------- #
# 3. Dependency direction is one-way: nexus_context ↛ nexus_planning.         #
# --------------------------------------------------------------------------- #


def test_context_service_does_not_import_planning() -> None:
    import nexus_context.service as context_service

    source = inspect.getsource(context_service)
    assert "import nexus_planning" not in source
    assert "from nexus_planning" not in source
