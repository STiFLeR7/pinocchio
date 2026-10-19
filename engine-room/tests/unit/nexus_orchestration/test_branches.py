"""Targeted coverage for genuine branches the component suites do not exercise.

These pin real, reachable behavior: the ``validate_outputs`` consistency guards, the
``validate_graph`` empty-identifier guard, the three ``_context_ref`` resolution
paths, and the four ``_correlation`` fallback paths. Every case is a real code path,
not a line-touch.
"""

from __future__ import annotations

import pytest

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import CoordinationModel
from nexus_core.domain.execution_graph import ExecutionGraph, GraphNode
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_orchestration import (
    InvalidGraphError,
    OrchestrationResult,
    SessionBindingError,
    validate_graph,
    validate_outputs,
)
from tests.unit.nexus_orchestration.helpers import (
    gedge,
    gnode,
    make_graph,
    make_request,
    make_strategy,
    orchestration_env,
)


def _result() -> tuple[ExecutionGraph, OrchestrationResult]:
    env = orchestration_env()
    graph = make_graph((gnode("a"), gnode("b")), (gedge("a", "b"),))
    strategy = make_strategy()
    return graph, env.orchestration.service.orchestrate(make_request(graph, strategy))


# --------------------------------------------------------------------------- #
# validate_outputs consistency guards                                         #
# --------------------------------------------------------------------------- #


def test_validate_outputs_passes_on_real_result() -> None:
    graph, result = _result()
    validate_outputs(result, graph)  # does not raise


def test_validate_outputs_rejects_queue_count_mismatch() -> None:
    graph, result = _result()
    broken = result.model_copy(
        update={"queue_state": result.queue_state.model_copy(update={"items": ()})}
    )
    with pytest.raises(InvalidGraphError):
        validate_outputs(broken, graph)


def test_validate_outputs_rejects_dependency_count_mismatch() -> None:
    graph, result = _result()
    broken = result.model_copy(
        update={"dependency_state": result.dependency_state.model_copy(update={"nodes": ()})}
    )
    with pytest.raises(InvalidGraphError):
        validate_outputs(broken, graph)


def test_validate_outputs_rejects_node_count_mismatch() -> None:
    graph, result = _result()
    broken = result.model_copy(
        update={"session": result.session.model_copy(update={"node_count": 99})}
    )
    with pytest.raises(SessionBindingError):
        validate_outputs(broken, graph)


def test_validate_outputs_rejects_harness_ready_mismatch() -> None:
    graph, result = _result()
    broken = result.model_copy(update={"harness_requests": ()})
    with pytest.raises(InvalidGraphError):
        validate_outputs(broken, graph)


def test_validate_outputs_rejects_runtime_harness_mismatch() -> None:
    graph, result = _result()
    broken = result.model_copy(update={"runtime_requests": ()})
    with pytest.raises(InvalidGraphError):
        validate_outputs(broken, graph)


# --------------------------------------------------------------------------- #
# validate_graph empty-identifier guard                                       #
# --------------------------------------------------------------------------- #


def test_validate_graph_rejects_empty_node_identifier() -> None:
    node = GraphNode(
        identifier="   ",
        work_package_ref=Reference(target_type="work_package", identifier="wp-1"),
    )
    graph = make_graph((node,))
    with pytest.raises(InvalidGraphError):
        validate_graph(graph)


# --------------------------------------------------------------------------- #
# _context_ref resolution paths (via the session the service binds)           #
# --------------------------------------------------------------------------- #


def test_context_ref_uses_explicit_request_value() -> None:
    env = orchestration_env()
    graph = make_graph((gnode("a", context=None),))
    explicit = Reference(target_type="context_package", identifier="ctx-explicit")
    result = env.orchestration.service.orchestrate(
        make_request(graph, make_strategy(), context_ref=explicit)
    )
    assert result.session.context_ref == explicit


def test_context_ref_derived_from_node() -> None:
    env = orchestration_env()
    graph = make_graph((gnode("a", context="ctx-from-node"),))
    result = env.orchestration.service.orchestrate(make_request(graph, make_strategy()))
    assert result.session.context_ref == Reference(
        target_type="context_package", identifier="ctx-from-node"
    )


def test_context_ref_falls_back_to_goal() -> None:
    env = orchestration_env()
    graph = make_graph((gnode("a", context=None),), goal="goal-1")
    result = env.orchestration.service.orchestrate(make_request(graph, make_strategy()))
    assert result.session.context_ref == Reference(
        target_type="context_package", identifier="context-goal-1"
    )


# --------------------------------------------------------------------------- #
# _correlation fallback paths                                                  #
# --------------------------------------------------------------------------- #


def _correlation_of(
    graph: ExecutionGraph, strategy: ExecutionStrategy, correlation_identifier: str | None = None
) -> str:
    env = orchestration_env()
    result = env.orchestration.service.orchestrate(
        make_request(graph, strategy, correlation_identifier=correlation_identifier)
    )
    return result.session.correlation.correlation_identifier


def test_correlation_prefers_request() -> None:
    graph = make_graph((gnode("a"),), correlation="cor-graph")
    strategy = make_strategy(correlation="cor-strategy")
    assert _correlation_of(graph, strategy, "cor-request") == "cor-request"


def test_correlation_falls_back_to_strategy() -> None:
    graph = make_graph((gnode("a"),), correlation=None)
    strategy = make_strategy(correlation="cor-strategy")
    assert _correlation_of(graph, strategy) == "cor-strategy"


def test_correlation_falls_back_to_graph() -> None:
    graph = make_graph((gnode("a"),), correlation="cor-graph")
    strategy = make_strategy(correlation=None)
    assert _correlation_of(graph, strategy) == "cor-graph"


def test_correlation_falls_back_to_goal() -> None:
    graph = make_graph((gnode("a"),), goal="goal-1", correlation=None)
    strategy = make_strategy(correlation=None)
    assert _correlation_of(graph, strategy) == "cor-goal-1"


def test_coordination_bound_from_strategy() -> None:
    env = orchestration_env()
    graph = make_graph((gnode("a"),))
    strategy = make_strategy(coordination=CoordinationModel.PARALLEL)
    result = env.orchestration.service.orchestrate(make_request(graph, strategy))
    assert result.session.coordination is CoordinationModel.PARALLEL
