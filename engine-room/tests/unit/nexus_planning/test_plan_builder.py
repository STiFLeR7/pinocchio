"""Plan construction tests (ADR-003 §3.3, INV-03/08/10/37).

Verifies the deterministic assembly of the immutable :class:`Plan`: identity and
versioning, ownership references, milestones, priority ordering, complexity
estimates, operational risks (missing capabilities), and the request-sourced
narrative fields.

Driven mostly through ``env.planning.service.plan(...)`` so the risk path
(capability resolution → missing → operational risk) is exercised end-to-end,
with focused direct calls to :class:`PlanBuilder` where useful.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import Priority
from nexus_core.domain import Milestone
from nexus_planning import PlanBuilder, PlanningRequest
from tests.unit.nexus_planning.helpers import item, make_capability, make_goal, planning_env


def _plan(goal, request, *capabilities):
    """Run a full planning cycle and return the resulting Plan."""
    env = planning_env(*capabilities)
    return env.planning.service.plan(goal, request).plan


def test_plan_identity_parent_goal_and_default_version():
    goal = make_goal("goal-1")
    request = PlanningRequest(work_items=(item("research"),))

    plan = _plan(goal, request)

    assert plan.identity == "plan-goal-1-v1"
    assert plan.parent_goal == Reference(target_type="goal", identifier="goal-1")
    assert plan.version == "1"


def test_plan_version_override():
    goal = make_goal("goal-1")
    request = PlanningRequest(work_items=(item("research"),), plan_version="2")

    plan = _plan(goal, request)

    assert plan.identity == "plan-goal-1-v2"
    assert plan.version == "2"


def test_work_package_refs_match_generated_packages():
    goal = make_goal("goal-1")
    request = PlanningRequest(work_items=(item("research"), item("build")))

    env = planning_env()
    result = env.planning.service.plan(goal, request)

    ref_ids = {ref.identifier for ref in result.plan.work_package_refs}
    wp_ids = {wp.identifier for wp in result.work_packages}
    assert ref_ids == wp_ids
    assert ref_ids == {"wp-goal-1-research", "wp-goal-1-build"}


def test_execution_graph_ref():
    goal = make_goal("goal-1")
    request = PlanningRequest(work_items=(item("research"),))

    plan = _plan(goal, request)

    assert plan.execution_graph_ref == Reference(
        target_type="execution_graph", identifier="graph-goal-1-v1"
    )


def test_narrative_fields_default_from_request():
    goal = make_goal("goal-1")
    request = PlanningRequest(work_items=(item("research"),))

    plan = _plan(goal, request)

    assert plan.approach_summary == request.approach_summary
    assert plan.dependency_summary == request.dependency_summary
    assert plan.rationale == request.rationale


def test_narrative_fields_can_be_overridden():
    goal = make_goal("goal-1")
    request = PlanningRequest(
        work_items=(item("research"),),
        approach_summary="Custom approach",
        dependency_summary="Custom dependencies",
        rationale="Custom rationale",
    )

    plan = _plan(goal, request)

    assert plan.approach_summary == "Custom approach"
    assert plan.dependency_summary == "Custom dependencies"
    assert plan.rationale == "Custom rationale"


def test_milestones_default_to_single_planning_complete():
    goal = make_goal("goal-1")
    request = PlanningRequest(work_items=(item("research"),))

    plan = _plan(goal, request)

    assert len(plan.milestones) == 1
    assert plan.milestones[0].identifier == "planning-complete"


def test_milestones_use_request_milestones_when_provided():
    goal = make_goal("goal-1")
    milestone = Milestone(
        identifier="design-approved",
        meaning="The design has been signed off.",
        completion_condition="Reviewer approves the design.",
    )
    request = PlanningRequest(work_items=(item("research"),), milestones=(milestone,))

    plan = _plan(goal, request)

    assert plan.milestones == (milestone,)


def test_priorities_reflect_item_or_goal_priority():
    goal = make_goal("goal-1")  # goal priority is HIGH
    request = PlanningRequest(
        work_items=(
            item("research"),  # inherits goal priority
            item("build", priority=Priority.LOW),  # explicit
        )
    )

    plan = _plan(goal, request)

    assert plan.priorities == {"research": "high", "build": "low"}


def test_complexity_estimates_count_packages_and_dependencies():
    goal = make_goal("goal-1")
    request = PlanningRequest(
        work_items=(
            item("research"),
            item("build", depends_on=("research",)),
            item("ship", depends_on=("research", "build")),
        )
    )

    plan = _plan(goal, request)

    assert plan.complexity_estimates == {
        "work_package_count": 3,
        "dependency_count": 3,
    }


def test_operational_risks_include_missing_capability():
    goal = make_goal("goal-1")
    request = PlanningRequest(
        work_items=(item("research", capability_requirements=("cap.missing",)),)
    )

    # planning_env() registers nothing, so cap.missing is unresolved.
    plan = _plan(goal, request)

    assert {"kind": "missing_capability", "capability": "cap.missing"} in plan.operational_risks


def test_registered_capability_yields_no_missing_capability_risk():
    goal = make_goal("goal-1")
    request = PlanningRequest(
        work_items=(item("research", capability_requirements=("cap.present",)),)
    )

    plan = _plan(goal, request, make_capability("cap.present"))

    assert plan.operational_risks == ()


def test_assumptions_flow_from_request():
    goal = make_goal("goal-1")
    request = PlanningRequest(
        work_items=(item("research"),),
        assumptions=("registry is current", "scope is fixed"),
    )

    plan = _plan(goal, request)

    assert plan.assumptions == ("registry is current", "scope is fixed")


def test_builder_direct_call_assembles_plan():
    """Focused unit check: PlanBuilder alone produces the expected identity/refs."""
    goal = make_goal("goal-1")
    request = PlanningRequest(work_items=(item("research"), item("build")))
    env = planning_env()
    result = env.planning.service.plan(goal, request)

    plan = PlanBuilder().build(
        goal,
        request,
        work_packages=result.work_packages,
        graph_identity="graph-goal-1-v1",
        correlation_identifier="cor-goal-1",
    )

    assert plan.identity == "plan-goal-1-v1"
    assert plan.execution_graph_ref == Reference(
        target_type="execution_graph", identifier="graph-goal-1-v1"
    )
    assert {ref.identifier for ref in plan.work_package_refs} == {
        "wp-goal-1-research",
        "wp-goal-1-build",
    }
    assert plan.operational_risks == ()
