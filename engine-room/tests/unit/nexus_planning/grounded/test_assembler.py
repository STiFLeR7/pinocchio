"""The grounded planner — ExecutionPlan shape, three-input integration, events, determinism."""

from __future__ import annotations

from dataclasses import replace

from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_core.domain.plan import Plan
from nexus_planning.grounded import ExecutionPlan
from nexus_planning.grounded.assembler import PLANNING_EXECUTION_PLAN_ASSEMBLED
from tests.unit.nexus_planning.grounded.fixtures import item, make_inputs, wired_grounded


def test_assemble_produces_the_frozen_plan_bundle() -> None:
    _, ctx = wired_grounded()
    ep = ctx.planner.plan(make_inputs(work_items=(item("a"), item("b", depends_on=("a",)))))
    assert isinstance(ep, ExecutionPlan)
    assert isinstance(ep.plan, Plan)  # the frozen Plan (INV-07), not a new schema
    assert isinstance(ep.execution_graph, ExecutionGraph)
    assert ep.identity == ep.plan.identity
    assert ep.goal_ref.identifier == "g1"
    assert len(ep.work_packages) == 2


def test_graph_is_referenced_by_the_plan_not_nested() -> None:
    _, ctx = wired_grounded()
    ep = ctx.planner.plan(make_inputs(work_items=(item("a"),)))
    # INV-10: the Plan references its sibling graph by id; it never nests it.
    assert ep.plan.execution_graph_ref.identifier == ep.execution_graph.identity


def test_default_decomposition_is_the_atomic_single_package() -> None:
    _, ctx = wired_grounded()
    ep = ctx.planner.plan(make_inputs())  # no explicit work_items
    assert len(ep.work_packages) == 1
    assert ep.work_packages[
        0
    ].objective  # the Goal's objective, one package (no invented sub-tasks)


def test_explicit_work_items_remain_authoritative_over_interpreted_steps() -> None:
    _, ctx = wired_grounded()
    inputs = replace(
        make_inputs(work_items=(item("caller-authored"),)),
        operator_steps=({"key": "interpreted", "objective": "different inferred objective"},),
    )
    ep = ctx.planner.plan(inputs)
    assert len(ep.work_packages) == 1
    assert ep.work_packages[0].objective == "do caller-authored"


def test_context_package_is_a_first_class_input() -> None:
    _, ctx = wired_grounded()
    ep = ctx.planner.plan(make_inputs(work_items=(item("a"),)))
    # context_ref threaded onto the work package + surfaced as a context reference
    assert ep.work_packages[0].context.identifier.startswith("context-")
    assert any(r.target_type == "context_package" for r in ep.context_references)


def test_context_constraints_flow_to_work_packages() -> None:
    _, ctx = wired_grounded()
    inputs = make_inputs(work_items=(item("a"),))
    ep = ctx.planner.plan(inputs)
    # The ContextPackage's operative constraints are threaded onto the work items → packages.
    context_package = inputs.context_package
    assert context_package is not None and context_package.constraints
    wp_constraints = ep.work_packages[0].constraints
    for constraint in context_package.constraints:
        assert constraint in wp_constraints  # Constraint.detail is a dict → compare by ==, not hash


def test_execution_plan_fact_is_emitted() -> None:
    infra, ctx = wired_grounded()
    ep = ctx.planner.plan(make_inputs(work_items=(item("a"),)))
    events = [
        e for e in infra.event_store.read_all() if e.type == PLANNING_EXECUTION_PLAN_ASSEMBLED
    ]
    assert len(events) == 1
    assert events[0].payload["plan"] == ep.plan.identity
    assert events[0].payload["execution_plan"]["identity"] == ep.identity


def test_absent_strategy_and_context_still_plan() -> None:
    _, ctx = wired_grounded()
    ep = ctx.planner.plan(make_inputs(strategy=False, context=False))
    assert len(ep.work_packages) == 1
    assert ep.context_references == ()  # no context → no references, still valid


def test_assembly_is_deterministic() -> None:
    inputs = make_inputs(work_items=(item("a"), item("b", depends_on=("a",))))
    _, ctx_a = wired_grounded()
    _, ctx_b = wired_grounded()
    assert ctx_a.planner.plan(inputs) == ctx_b.planner.plan(inputs)
