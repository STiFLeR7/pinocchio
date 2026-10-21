"""Unit tests for orchestration validators (Phase 5 — Orchestration).

The validators guard the pipeline boundaries, fail-fast, and never auto-correct:
:func:`validate_graph` (non-empty, key-unique, edge-closed), :func:`validate_acyclic`
(a DAG except for declared loops, INV-10), :func:`validate_request` (real session
version, progress sets reference known nodes), and :func:`validate_outputs`
(internal consistency of the produced structure). Each failure raises an
:class:`OrchestrationError` subclass — never a silent correction.
"""

from __future__ import annotations

import pytest

from nexus_core.contracts.enums import EdgeType
from nexus_core.domain.execution_graph import ExecutionGraph, GraphEdge, GraphNode
from nexus_orchestration.requests import OrchestrationRequest, OrchestrationResult
from nexus_orchestration.validators import (
    CyclicDependencyError,
    InvalidGraphError,
    SessionBindingError,
    UnknownNodeError,
    validate_acyclic,
    validate_graph,
    validate_outputs,
    validate_request,
)
from tests.unit.nexus_orchestration.helpers import (
    gedge,
    gnode,
    make_graph,
    make_request,
    make_strategy,
    orchestration_env,
)

# --------------------------------------------------------------------------- #
# validate_graph                                                               #
# --------------------------------------------------------------------------- #


def test_validate_graph_passes_for_a_valid_graph() -> None:
    graph = make_graph(
        (gnode("research"), gnode("build")),
        (gedge("research", "build"),),
    )

    validate_graph(graph)  # no raise


def test_validate_graph_rejects_empty_nodes() -> None:
    graph = make_graph(())

    with pytest.raises(InvalidGraphError):
        validate_graph(graph)


def test_validate_graph_rejects_duplicate_node_identifiers() -> None:
    # Two distinct GraphNode objects sharing the same identifier.
    duplicate = GraphNode(
        identifier="node-research",
        work_package_ref=gnode("research").work_package_ref,
    )
    graph = make_graph((gnode("research"), duplicate))

    with pytest.raises(InvalidGraphError):
        validate_graph(graph)


def test_validate_graph_rejects_empty_work_package_identifier() -> None:
    blank_wp = GraphNode(
        identifier="node-build",
        work_package_ref=gnode("build", work_package=" ").work_package_ref,
    )
    graph = make_graph((gnode("research"), blank_wp))

    with pytest.raises(InvalidGraphError):
        validate_graph(graph)


def test_validate_graph_rejects_edge_referencing_unknown_node() -> None:
    dangling = GraphEdge(
        identifier="edge-dangling",
        edge_type=EdgeType.EXECUTION,
        source_node="node-research",
        target_node="node-ghost",
    )
    graph = make_graph((gnode("research"),), (dangling,))

    with pytest.raises(InvalidGraphError):
        validate_graph(graph)


# --------------------------------------------------------------------------- #
# validate_acyclic                                                             #
# --------------------------------------------------------------------------- #


def test_validate_acyclic_passes_for_a_dag() -> None:
    graph = make_graph(
        (gnode("a"), gnode("b"), gnode("c")),
        (gedge("a", "b"), gedge("b", "c")),
    )

    validate_acyclic(graph)  # no raise


def test_validate_acyclic_rejects_a_cycle() -> None:
    graph = make_graph(
        (gnode("a"), gnode("b")),
        (gedge("a", "b"), gedge("b", "a")),
    )

    with pytest.raises(CyclicDependencyError):
        validate_acyclic(graph)


def test_validate_acyclic_exempts_a_declared_loop() -> None:
    # The back-edge b->a would be a cycle, but it is a declared loop and exempt.
    graph = make_graph(
        (gnode("a"), gnode("b")),
        (gedge("a", "b"), gedge("b", "a")),
        loops=({"source": "node-b", "target": "node-a"},),
    )

    validate_acyclic(graph)  # no raise — the declared loop is the only exception


# --------------------------------------------------------------------------- #
# validate_request                                                             #
# --------------------------------------------------------------------------- #


def test_validate_request_passes_for_a_valid_request() -> None:
    graph = make_graph((gnode("research"), gnode("build")), (gedge("research", "build"),))
    request = make_request(graph, make_strategy(), completed_nodes=("node-research",))

    validate_request(request)  # no raise


def test_validate_request_rejects_empty_session_version() -> None:
    graph = make_graph((gnode("research"),))
    request = make_request(graph, make_strategy(), session_version="  ")

    with pytest.raises(InvalidGraphError):
        validate_request(request)


def _ghost(field: str) -> OrchestrationRequest:
    """A request whose ``field`` progress set names a node absent from the graph."""
    graph = make_graph((gnode("research"),))
    strategy = make_strategy()
    ghost = ("node-ghost",)
    if field == "completed_nodes":
        return make_request(graph, strategy, completed_nodes=ghost)
    if field == "paused_nodes":
        return make_request(graph, strategy, paused_nodes=ghost)
    if field == "approved_gates":
        return make_request(graph, strategy, approved_gates=ghost)
    return make_request(graph, strategy, rejected_gates=ghost)


@pytest.mark.parametrize(
    "field",
    ("completed_nodes", "paused_nodes", "approved_gates", "rejected_gates"),
)
def test_validate_request_rejects_unknown_node_in_progress_set(field: str) -> None:
    with pytest.raises(UnknownNodeError):
        validate_request(_ghost(field))


# --------------------------------------------------------------------------- #
# validate_outputs                                                             #
# --------------------------------------------------------------------------- #


def _real_result() -> tuple[OrchestrationResult, ExecutionGraph]:
    """Produce a real, internally-consistent OrchestrationResult from the service."""
    graph = make_graph(
        (gnode("research"), gnode("build"), gnode("test")),
        (gedge("research", "build"), gedge("build", "test")),
    )
    env = orchestration_env()
    result = env.orchestration.service.orchestrate(make_request(graph, make_strategy()))
    return result, graph


def test_validate_outputs_passes_for_a_real_result() -> None:
    result, graph = _real_result()

    validate_outputs(result, graph)  # no raise


def test_validate_outputs_rejects_session_node_count_mismatch() -> None:
    result, graph = _real_result()
    # A frozen-object variant whose session disagrees with the graph node count.
    broken_session = result.session.model_copy(update={"node_count": 99})
    broken = result.model_copy(update={"session": broken_session})

    with pytest.raises(SessionBindingError):
        validate_outputs(broken, graph)
