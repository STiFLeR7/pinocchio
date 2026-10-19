"""Work Package generation tests (ADR-003 §3.2, INV-09/33/37).

Verifies the deterministic projection of declared work items into immutable
:class:`WorkPackage` objects — identity, ownership references, priority
inheritance, capability/skill channelling, dependency wiring, and the
projection fields Planning deliberately leaves unset.

Driven mostly end-to-end through ``env.planning.service.plan(...)`` for realism,
with focused direct calls to :class:`WorkPackageGenerator` where a single field
needs isolating.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import Priority
from nexus_planning import PlanningRequest, WorkPackageGenerator
from tests.unit.nexus_planning.helpers import item, make_goal, planning_env


def _plan(goal, request, *capabilities):
    """Run a full planning cycle and return its work packages keyed by identifier."""
    env = planning_env(*capabilities)
    result = env.planning.service.plan(goal, request)
    return {wp.identifier: wp for wp in result.work_packages}


def test_one_work_package_per_item_with_derived_identifier():
    goal = make_goal("goal-1")
    request = PlanningRequest(work_items=(item("research"), item("build")))

    packages = _plan(goal, request)

    assert set(packages) == {"wp-goal-1-research", "wp-goal-1-build"}


def test_parent_goal_and_parent_plan_references():
    goal = make_goal("goal-1")
    request = PlanningRequest(work_items=(item("research"),))

    wp = _plan(goal, request)["wp-goal-1-research"]

    assert wp.parent_goal == Reference(target_type="goal", identifier="goal-1")
    assert wp.parent_plan == Reference(target_type="plan", identifier="plan-goal-1-v1")


def test_objective_flows_from_item():
    goal = make_goal("goal-1")
    request = PlanningRequest(work_items=(item("research", objective="Investigate options"),))

    wp = _plan(goal, request)["wp-goal-1-research"]

    assert wp.objective == "Investigate options"


def test_priority_defaults_to_goal_priority():
    goal = make_goal("goal-1")  # goal priority is HIGH
    request = PlanningRequest(work_items=(item("research"),))

    wp = _plan(goal, request)["wp-goal-1-research"]

    assert wp.priority is Priority.HIGH


def test_priority_uses_item_priority_when_set():
    goal = make_goal("goal-1")  # goal priority is HIGH
    request = PlanningRequest(work_items=(item("research", priority=Priority.LOW),))

    wp = _plan(goal, request)["wp-goal-1-research"]

    assert wp.priority is Priority.LOW


def test_context_equals_request_context_ref_when_provided():
    goal = make_goal("goal-1")
    context_ref = Reference(target_type="context_package", identifier="ctx-custom")
    request = PlanningRequest(work_items=(item("research"),), context_ref=context_ref)

    wp = _plan(goal, request)["wp-goal-1-research"]

    assert wp.context == context_ref


def test_context_defaults_when_request_has_no_context_ref():
    goal = make_goal("goal-1")
    request = PlanningRequest(work_items=(item("research"),))

    wp = _plan(goal, request)["wp-goal-1-research"]

    assert wp.context == Reference(target_type="context_package", identifier="context-goal-1")


def test_skills_are_skill_refs_followed_by_capability_references():
    goal = make_goal("goal-1")
    skill_ref = Reference(target_type="skill", identifier="skill.review")
    work_item = item(
        "research",
        capability_requirements=("cap.a", "cap.b"),
        skill_refs=(skill_ref,),
    )
    request = PlanningRequest(work_items=(work_item,))

    wp = _plan(goal, request)["wp-goal-1-research"]

    assert wp.skills == (
        skill_ref,
        Reference(target_type="capability", identifier="cap.a"),
        Reference(target_type="capability", identifier="cap.b"),
    )


def test_resources_is_empty_tuple():
    goal = make_goal("goal-1")
    request = PlanningRequest(work_items=(item("research", capability_requirements=("cap.a",)),))

    wp = _plan(goal, request)["wp-goal-1-research"]

    assert wp.resources == ()


def test_dependencies_reference_depended_on_work_packages():
    goal = make_goal("goal-1")
    request = PlanningRequest(
        work_items=(item("research"), item("build", depends_on=("research",)))
    )

    wp = _plan(goal, request)["wp-goal-1-build"]

    assert wp.dependencies == (
        Reference(target_type="work_package", identifier="wp-goal-1-research"),
    )


def test_execution_strategy_ref():
    goal = make_goal("goal-1")
    request = PlanningRequest(work_items=(item("research"),))

    wp = _plan(goal, request)["wp-goal-1-research"]

    assert wp.execution_strategy_ref == Reference(
        target_type="execution_strategy", identifier="strategy-goal-1-v1"
    )


def test_evidence_and_completion_criteria_flow_through():
    goal = make_goal("goal-1")
    evidence = {"requires": "tests"}
    completion = {"definition": "merged"}
    request = PlanningRequest(
        work_items=(item("research", evidence=evidence, completion_criteria=completion),)
    )

    wp = _plan(goal, request)["wp-goal-1-research"]

    assert wp.evidence == evidence
    assert wp.completion_criteria == completion


def test_inputs_and_outputs_flow_through():
    goal = make_goal("goal-1")
    input_ref = Reference(target_type="artifact", identifier="art-1")
    output_spec = {"name": "report"}
    request = PlanningRequest(
        work_items=(item("research", inputs=(input_ref,), outputs=(output_spec,)),)
    )

    wp = _plan(goal, request)["wp-goal-1-research"]

    assert wp.inputs == (input_ref,)
    assert wp.outputs == (output_spec,)


def test_correlation_carries_cycle_correlation_identifier():
    goal = make_goal("goal-1")
    request = PlanningRequest(work_items=(item("research"),), correlation_identifier="cor-custom")

    wp = _plan(goal, request)["wp-goal-1-research"]

    assert wp.correlation is not None
    assert wp.correlation.correlation_identifier == "cor-custom"


def test_status_is_none_projection_not_set_by_planning():
    goal = make_goal("goal-1")
    request = PlanningRequest(work_items=(item("research"),))

    wp = _plan(goal, request)["wp-goal-1-research"]

    assert wp.status is None


def test_generator_direct_call_matches_service():
    """Focused unit check: the generator alone produces the same identity/fields."""
    goal = make_goal("goal-1")
    request = PlanningRequest(work_items=(item("research"),))

    packages = WorkPackageGenerator().generate(
        goal,
        request,
        plan_identity="plan-goal-1-v1",
        strategy_identity="strategy-goal-1-v1",
        correlation_identifier="cor-goal-1",
    )

    assert len(packages) == 1
    wp = packages[0]
    assert wp.identifier == "wp-goal-1-research"
    assert wp.parent_plan == Reference(target_type="plan", identifier="plan-goal-1-v1")
    assert wp.resources == ()
    assert wp.status is None
