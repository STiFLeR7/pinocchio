"""Tests for the planning validators — fail-fast, deterministic, no correction.

Validation guards the planning pipeline at its boundaries: the Goal must be
plannable, the decomposition well-formed, the produced graph acyclic (except
declared loops, INV-10), and every produced reference must resolve. Every failure
is a subclass of :class:`PlanningError`; nothing is auto-corrected.
"""

from __future__ import annotations

import pytest

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import EdgeType
from nexus_core.contracts.status import GoalStatus
from nexus_core.domain.execution_graph import ExecutionGraph, GraphEdge, GraphNode
from nexus_planning import (
    CyclicGraphError,
    DanglingReferenceError,
    GoalNotPlannableError,
    InvalidDecompositionError,
    PlanningError,
    PlanningRequest,
)
from nexus_planning.validators import (
    validate_acyclic,
    validate_goal,
    validate_outputs,
    validate_request,
)
from tests.unit.nexus_planning.helpers import item, make_goal

# --------------------------------------------------------------------------- #
# error hierarchy                                                             #
# --------------------------------------------------------------------------- #


def test_every_specific_error_subclasses_planning_error() -> None:
    assert issubclass(GoalNotPlannableError, PlanningError)
    assert issubclass(InvalidDecompositionError, PlanningError)
    assert issubclass(CyclicGraphError, PlanningError)
    assert issubclass(DanglingReferenceError, PlanningError)


# --------------------------------------------------------------------------- #
# validate_goal                                                               #
# --------------------------------------------------------------------------- #


def test_validate_goal_accepts_a_normal_goal() -> None:
    validate_goal(make_goal())


def test_validate_goal_accepts_non_terminal_status() -> None:
    validate_goal(make_goal(status=GoalStatus.PLANNING))


def test_validate_goal_rejects_achieved_goal() -> None:
    with pytest.raises(GoalNotPlannableError):
        validate_goal(make_goal(status=GoalStatus.ACHIEVED))


def test_validate_goal_rejects_abandoned_goal() -> None:
    with pytest.raises(GoalNotPlannableError):
        validate_goal(make_goal(status=GoalStatus.ABANDONED))


def test_validate_goal_rejects_whitespace_only_outcome() -> None:
    with pytest.raises(GoalNotPlannableError):
        validate_goal(make_goal(outcome="   "))


# --------------------------------------------------------------------------- #
# validate_request                                                            #
# --------------------------------------------------------------------------- #


def test_validate_request_accepts_a_valid_request() -> None:
    request = PlanningRequest(work_items=(item("a"), item("b", depends_on=("a",))))

    validate_request(request)


def test_validate_request_rejects_empty_work_items() -> None:
    with pytest.raises(InvalidDecompositionError):
        validate_request(PlanningRequest(work_items=()))


def test_validate_request_rejects_duplicate_keys() -> None:
    request = PlanningRequest(work_items=(item("a"), item("a")))

    with pytest.raises(InvalidDecompositionError):
        validate_request(request)


def test_validate_request_rejects_self_dependency() -> None:
    request = PlanningRequest(work_items=(item("a", depends_on=("a",)),))

    with pytest.raises(InvalidDecompositionError):
        validate_request(request)


def test_validate_request_rejects_unknown_dependency() -> None:
    request = PlanningRequest(work_items=(item("a", depends_on=("ghost",)),))

    with pytest.raises(InvalidDecompositionError):
        validate_request(request)


# --------------------------------------------------------------------------- #
# validate_acyclic                                                            #
# --------------------------------------------------------------------------- #


def _node(identifier: str) -> GraphNode:
    return GraphNode(
        identifier=identifier,
        work_package_ref=Reference(target_type="work_package", identifier=f"wp-{identifier}"),
    )


def _edge(source: str, target: str) -> GraphEdge:
    return GraphEdge(
        identifier=f"edge-{source}-{target}",
        edge_type=EdgeType.EXECUTION,
        source_node=source,
        target_node=target,
    )


def _graph(
    nodes: tuple[GraphNode, ...],
    edges: tuple[GraphEdge, ...],
    *,
    loops: tuple[dict[str, str], ...] = (),
) -> ExecutionGraph:
    return ExecutionGraph(
        identity="graph-1",
        parent_goal=Reference(target_type="goal", identifier="goal-1"),
        parent_plan=Reference(target_type="plan", identifier="plan-1"),
        version="1",
        nodes=nodes,
        edges=edges,
        conditions=(),
        checkpoints=(),
        policies={},
        metadata={},
        loops=loops,
    )


def test_validate_acyclic_accepts_a_dag() -> None:
    graph = _graph(
        nodes=(_node("a"), _node("b"), _node("c")),
        edges=(_edge("a", "b"), _edge("b", "c")),
    )

    validate_acyclic(graph)


def test_validate_acyclic_rejects_a_two_node_cycle() -> None:
    graph = _graph(
        nodes=(_node("a"), _node("b")),
        edges=(_edge("a", "b"), _edge("b", "a")),
    )

    with pytest.raises(CyclicGraphError):
        validate_acyclic(graph)


def test_validate_acyclic_rejects_edge_to_unknown_node() -> None:
    graph = _graph(
        nodes=(_node("a"),),
        edges=(_edge("a", "ghost"),),
    )

    with pytest.raises(DanglingReferenceError):
        validate_acyclic(graph)


def test_validate_acyclic_allows_declared_loop() -> None:
    graph = _graph(
        nodes=(_node("a"), _node("b")),
        edges=(_edge("a", "b"), _edge("b", "a")),
        loops=({"source": "b", "target": "a"},),
    )

    validate_acyclic(graph)


# --------------------------------------------------------------------------- #
# validate_outputs                                                            #
# --------------------------------------------------------------------------- #


def _planned() -> tuple[ExecutionGraph, tuple[object, ...], tuple[str, ...]]:
    """Run a real planning cycle and return its graph, packages, and wp refs."""
    from tests.unit.nexus_planning.helpers import planning_env

    env = planning_env()
    goal = make_goal()
    request = PlanningRequest(work_items=(item("a"), item("b", depends_on=("a",))))
    result = env.planning.service.plan(goal, request)
    wp_refs = tuple(ref.identifier for ref in result.plan.work_package_refs)
    return result.execution_graph, result.work_packages, wp_refs


def test_validate_outputs_accepts_matching_inputs() -> None:
    graph, work_packages, wp_refs = _planned()

    validate_outputs(graph.identity, graph, work_packages, wp_refs)


def test_validate_outputs_rejects_mismatched_wp_refs() -> None:
    graph, work_packages, _ = _planned()

    with pytest.raises(DanglingReferenceError):
        validate_outputs(graph.identity, graph, work_packages, ("wp-does-not-exist",))


def test_validate_outputs_rejects_mismatched_graph_ref() -> None:
    graph, work_packages, wp_refs = _planned()

    with pytest.raises(DanglingReferenceError):
        validate_outputs("graph-wrong-id", graph, work_packages, wp_refs)


def test_validate_outputs_rejects_node_referencing_unknown_work_package() -> None:
    graph, _work_packages, wp_refs = _planned()
    # Drop every real work package so the graph's nodes reference unknown ids,
    # but keep plan_wp_refs consistent with the (now empty) package set so the
    # node-level check is the one that fires.

    with pytest.raises(DanglingReferenceError):
        validate_outputs(graph.identity, graph, (), ())
