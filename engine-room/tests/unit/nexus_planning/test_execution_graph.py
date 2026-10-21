"""Unit tests for the Execution Graph builder (Step 4, ADR-003 §3.3, INV-10).

These tests exercise the deterministic topology construction: one node per work
item, typed edges for dependencies, conditional/approval/checkpoint handling,
graph metadata, the sibling-not-nested invariant (INV-10), build determinism, and
acyclicity validation (cycles raise unless explicitly declared as loops).
"""

from __future__ import annotations

import pytest

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import CoordinationModel, EdgeType
from nexus_core.domain.execution_graph import ExecutionGraph, GraphEdge, GraphNode
from nexus_planning import (
    CyclicGraphError,
    ExecutionGraphBuilder,
    PlanningRequest,
)
from nexus_planning.validators import validate_acyclic

from .helpers import item, make_goal, planning_env

GOAL = "goal-1"


def _build(*items, version: str = "1", coordination=CoordinationModel.SEQUENTIAL):
    """Build an ExecutionGraph directly from work items via the builder."""
    goal = make_goal(GOAL)
    request = PlanningRequest(work_items=tuple(items), plan_version=version)
    builder = ExecutionGraphBuilder()
    return builder.build(
        goal,
        request,
        plan_identity=f"plan-{GOAL}-v{version}",
        strategy_identity=f"strategy-{GOAL}-v{version}",
        coordination=coordination,
        correlation_identifier=f"cor-{GOAL}",
    )


def _node(graph: ExecutionGraph, identifier: str) -> GraphNode:
    return next(node for node in graph.nodes if node.identifier == identifier)


# --------------------------------------------------------------------------- #
# Nodes                                                                        #
# --------------------------------------------------------------------------- #


def test_one_node_per_item_with_canonical_references():
    graph = _build(item("research"), item("build"))

    assert len(graph.nodes) == 2
    node = _node(graph, "node-research")
    assert node.identifier == "node-research"
    assert node.work_package_ref.identifier == f"wp-{GOAL}-research"
    assert node.execution_strategy_ref is not None
    assert node.execution_strategy_ref.identifier == f"strategy-{GOAL}-v1"
    assert node.required_context_ref is not None
    assert node.required_context_ref.identifier == f"context-{GOAL}"


# --------------------------------------------------------------------------- #
# Edges: sequential / parallel / join                                         #
# --------------------------------------------------------------------------- #


def test_dependency_yields_execution_edge():
    graph = _build(item("research"), item("build", depends_on=("research",)))

    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert edge.edge_type is EdgeType.EXECUTION
    assert edge.source_node == "node-research"
    assert edge.target_node == "node-build"
    assert edge.condition is None


def test_parallel_independent_items_have_no_edges():
    graph = _build(item("a"), item("b"))

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 0


def test_join_node_records_two_inbound_edges_and_sync_point():
    graph = _build(item("a"), item("b"), item("c", depends_on=("a", "b")))

    inbound = [edge for edge in graph.edges if edge.target_node == "node-c"]
    assert len(inbound) == 2
    assert {edge.source_node for edge in inbound} == {"node-a", "node-b"}
    assert "node-c" in graph.policies["synchronization_points"]


# --------------------------------------------------------------------------- #
# Conditional flow                                                            #
# --------------------------------------------------------------------------- #


def test_conditional_item_yields_conditional_edge_and_condition_entry():
    graph = _build(item("a"), item("b", depends_on=("a",), condition="x>0"))

    edge = graph.edges[0]
    assert edge.edge_type is EdgeType.CONDITIONAL
    assert edge.source_node == "node-a"
    assert edge.target_node == "node-b"
    assert edge.condition == "x>0"
    assert {"node": "node-b", "predicate": "x>0"} in graph.conditions


# --------------------------------------------------------------------------- #
# Approval gates                                                              #
# --------------------------------------------------------------------------- #


def test_approval_item_adds_constraint_and_gate():
    graph = _build(item("review", requires_approval=True))

    node = _node(graph, "node-review")
    kinds = {constraint.kind for constraint in node.constraints}
    assert "approval" in kinds
    assert "node-review" in graph.policies["approval_gates"]


# --------------------------------------------------------------------------- #
# Checkpoints                                                                 #
# --------------------------------------------------------------------------- #


def test_checkpoint_item_yields_checkpoint_reference():
    graph = _build(item("m", is_checkpoint=True))

    assert len(graph.checkpoints) == 1
    checkpoint = graph.checkpoints[0]
    assert checkpoint.target_type == "checkpoint"


def test_non_checkpoint_item_yields_no_checkpoints():
    graph = _build(item("m"))

    assert graph.checkpoints == ()


# --------------------------------------------------------------------------- #
# Metadata                                                                    #
# --------------------------------------------------------------------------- #


def test_metadata_for_small_chain():
    graph = _build(
        item("a"),
        item("b", depends_on=("a",)),
        item("c", depends_on=("b",)),
    )

    metadata = graph.metadata
    assert metadata["node_count"] == 3
    assert metadata["edge_count"] == 2
    assert metadata["root_nodes"] == ["node-a"]
    assert metadata["terminal_nodes"] == ["node-c"]
    assert metadata["goal"] == GOAL
    assert metadata["plan"] == f"plan-{GOAL}-v1"
    assert metadata["version"] == "1"


# --------------------------------------------------------------------------- #
# INV-10: sibling, not nested                                                #
# --------------------------------------------------------------------------- #


def test_graph_is_sibling_of_plan_not_nested():
    env = planning_env()
    goal = make_goal(GOAL)
    request = PlanningRequest(work_items=(item("a"),))
    result = env.planning.service.plan(goal, request)

    graph = result.execution_graph
    plan = result.plan
    # Graph points back to the Plan by id.
    assert graph.parent_plan.identifier == plan.identity
    # Plan references the graph by id (not embedded).
    assert plan.execution_graph_ref.identifier == graph.identity
    assert isinstance(plan.execution_graph_ref, Reference)
    # The Plan does not embed an ExecutionGraph object anywhere.
    for value in plan.__dict__.values():
        assert not isinstance(value, ExecutionGraph)


# --------------------------------------------------------------------------- #
# Determinism                                                                 #
# --------------------------------------------------------------------------- #


def test_build_is_deterministic_across_two_calls():
    items = (
        item("a"),
        item("b", depends_on=("a",), condition="y>1"),
        item("c", depends_on=("a", "b"), requires_approval=True, is_checkpoint=True),
    )
    first = _build(*items)
    second = _build(*items)

    assert first.nodes == second.nodes
    assert first.edges == second.edges
    assert first.conditions == second.conditions
    assert first.checkpoints == second.checkpoints
    assert first.policies == second.policies
    assert first.metadata == second.metadata
    assert first == second


def test_build_is_deterministic_across_two_fresh_envs():
    goal = make_goal(GOAL)
    request = PlanningRequest(
        work_items=(item("a"), item("b", depends_on=("a",))),
    )
    graph_one = planning_env().planning.service.plan(goal, request).execution_graph
    graph_two = planning_env().planning.service.plan(goal, request).execution_graph

    assert graph_one == graph_two


# --------------------------------------------------------------------------- #
# Acyclicity                                                                  #
# --------------------------------------------------------------------------- #


def test_normal_dag_passes_acyclicity():
    graph = _build(
        item("a"),
        item("b", depends_on=("a",)),
        item("c", depends_on=("b",)),
    )

    # Does not raise.
    validate_acyclic(graph)


def _two_node_cycle_graph(*, loops=()) -> ExecutionGraph:
    """A minimal manually-built graph with edges a->b and b->a."""
    node_a = GraphNode(
        identifier="node-a",
        work_package_ref=Reference(target_type="work_package", identifier="wp-a"),
    )
    node_b = GraphNode(
        identifier="node-b",
        work_package_ref=Reference(target_type="work_package", identifier="wp-b"),
    )
    edge_ab = GraphEdge(
        identifier="edge-a->b",
        edge_type=EdgeType.EXECUTION,
        source_node="node-a",
        target_node="node-b",
    )
    edge_ba = GraphEdge(
        identifier="edge-b->a",
        edge_type=EdgeType.EXECUTION,
        source_node="node-b",
        target_node="node-a",
    )
    return ExecutionGraph(
        identity="graph-cycle",
        parent_goal=Reference(target_type="goal", identifier=GOAL),
        parent_plan=Reference(target_type="plan", identifier="plan-cycle"),
        version="1",
        nodes=(node_a, node_b),
        edges=(edge_ab, edge_ba),
        conditions=(),
        checkpoints=(),
        policies={},
        metadata={},
        loops=loops,
    )


def test_cycle_raises_cyclic_graph_error():
    graph = _two_node_cycle_graph()

    with pytest.raises(CyclicGraphError):
        validate_acyclic(graph)


def test_declared_loop_does_not_raise():
    graph = _two_node_cycle_graph(loops=({"source": "node-b", "target": "node-a"},))

    # The back-edge is a declared loop, so the remaining topology is acyclic.
    validate_acyclic(graph)
