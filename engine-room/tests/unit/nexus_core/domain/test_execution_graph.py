"""Unit tests for the ExecutionGraph domain model (contract: execution_graph.md)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import EdgeType
from nexus_core.domain.execution_graph import ExecutionGraph, GraphEdge, GraphNode
from nexus_core.state.transitions import MACHINES


def _valid_graph() -> ExecutionGraph:
    node_a = GraphNode(
        identifier="n-a",
        work_package_ref=Reference(target_type="work_package", identifier="wp-1"),
    )
    node_b = GraphNode(
        identifier="n-b",
        work_package_ref=Reference(target_type="work_package", identifier="wp-2"),
        execution_strategy_ref=Reference(target_type="execution_strategy", identifier="es-1"),
        required_skill_refs=(Reference(target_type="skill", identifier="sk-1"),),
    )
    edge = GraphEdge(
        identifier="e-1",
        edge_type=EdgeType.EXECUTION,
        source_node="n-a",
        target_node="n-b",
    )
    return ExecutionGraph(
        identity="eg-1",
        parent_goal=Reference(target_type="goal", identifier="g-1"),
        parent_plan=Reference(target_type="plan", identifier="p-1"),
        version="1.0.0",
        nodes=(node_a, node_b),
        edges=(edge,),
        conditions=(),
        checkpoints=(Reference(target_type="checkpoint", identifier="cp-1"),),
        policies={"approval": "human_review"},
        metadata={"node_count": 2},
    )


def test_construction() -> None:
    graph = _valid_graph()
    assert graph.identity == "eg-1"
    assert graph.nodes[0].identifier == "n-a"
    assert graph.edges[0].edge_type is EdgeType.EXECUTION
    assert graph.status is None
    assert graph.loops == ()


def test_immutable() -> None:
    graph = _valid_graph()
    with pytest.raises(ValidationError):
        graph.version = "2.0.0"  # type: ignore[misc]


def test_missing_required_raises() -> None:
    with pytest.raises(ValidationError):
        ExecutionGraph(  # type: ignore[call-arg]
            identity="eg-1",
            parent_goal=Reference(target_type="goal", identifier="g-1"),
            parent_plan=Reference(target_type="plan", identifier="p-1"),
            version="1.0.0",
            nodes=(),
            edges=(),
            conditions=(),
            checkpoints=(),
            policies={},
            # metadata missing
        )


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        ExecutionGraph(
            identity="eg-1",
            parent_goal=Reference(target_type="goal", identifier="g-1"),
            parent_plan=Reference(target_type="plan", identifier="p-1"),
            version="1.0.0",
            nodes=(),
            edges=(),
            conditions=(),
            checkpoints=(),
            policies={},
            metadata={},
            unexpected="boom",  # type: ignore[call-arg]
        )


def test_serialization_round_trip() -> None:
    graph = _valid_graph()
    assert ExecutionGraph.model_validate(graph.model_dump()) == graph


def test_lifecycle_name() -> None:
    assert ExecutionGraph.LIFECYCLE_NAME == "execution_graph"
    assert ExecutionGraph.LIFECYCLE_NAME in MACHINES
