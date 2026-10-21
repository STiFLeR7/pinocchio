"""Unit tests for the Execution Session value object and its builder (Step 1).

An Execution Session binds, by reference, the five orchestration artifacts and
records coordination metadata. These tests cover the builder's reference
derivation and pass-through fields, the value object's immutability, and the
hard determinism guarantee (identical inputs yield equal sessions).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import CoordinationModel
from nexus_orchestration import ExecutionSession, ExecutionSessionBuilder
from tests.unit.nexus_orchestration.helpers import (
    gnode,
    make_graph,
    make_strategy,
)

CONTEXT_REF = Reference(target_type="context_package", identifier="context-goal-1")


def _build(
    *,
    correlation_identifier: str = "cor-x",
    version: str = "1",
) -> ExecutionSession:
    """Build an Execution Session from a small deterministic graph + strategy."""
    graph = make_graph(
        (gnode("a"), gnode("b")),
        checkpoints=(Reference(target_type="checkpoint", identifier="cp-1"),),
    )
    strategy = make_strategy(coordination=CoordinationModel.SEQUENTIAL)
    return ExecutionSessionBuilder().build(
        graph,
        strategy,
        context_ref=CONTEXT_REF,
        correlation_identifier=correlation_identifier,
        version=version,
    )


def test_identity_is_session_id_from_goal_and_version() -> None:
    graph = make_graph((gnode("a"),))
    strategy = make_strategy()
    session = ExecutionSessionBuilder().build(
        graph,
        strategy,
        context_ref=CONTEXT_REF,
        correlation_identifier="cor-x",
        version="1",
    )
    assert session.identity == f"session-{graph.parent_goal.identifier}-v1"
    assert session.identity == "session-goal-1-v1"


def test_goal_and_plan_refs_come_from_graph_lineage() -> None:
    graph = make_graph((gnode("a"),))
    strategy = make_strategy()
    session = ExecutionSessionBuilder().build(
        graph,
        strategy,
        context_ref=CONTEXT_REF,
        correlation_identifier="cor-x",
    )
    assert session.goal_ref == graph.parent_goal
    assert session.plan_ref == graph.parent_plan


def test_context_ref_passes_through() -> None:
    session = _build()
    assert session.context_ref == CONTEXT_REF


def test_execution_graph_ref_target_type_and_identifier() -> None:
    graph = make_graph((gnode("a"),))
    strategy = make_strategy()
    session = ExecutionSessionBuilder().build(
        graph,
        strategy,
        context_ref=CONTEXT_REF,
        correlation_identifier="cor-x",
    )
    assert session.execution_graph_ref.target_type == "execution_graph"
    assert session.execution_graph_ref.identifier == graph.identity


def test_execution_strategy_ref_target_type_and_identifier() -> None:
    graph = make_graph((gnode("a"),))
    strategy = make_strategy(identity="strategy-goal-1-v1")
    session = ExecutionSessionBuilder().build(
        graph,
        strategy,
        context_ref=CONTEXT_REF,
        correlation_identifier="cor-x",
    )
    assert session.execution_strategy_ref.target_type == "execution_strategy"
    assert session.execution_strategy_ref.identifier == strategy.identity


def test_coordination_comes_from_strategy() -> None:
    graph = make_graph((gnode("a"),))
    strategy = make_strategy(coordination=CoordinationModel.PARALLEL)
    session = ExecutionSessionBuilder().build(
        graph,
        strategy,
        context_ref=CONTEXT_REF,
        correlation_identifier="cor-x",
    )
    assert session.coordination == strategy.coordination
    assert session.coordination == CoordinationModel.PARALLEL


def test_correlation_identifier_passes_through() -> None:
    session = _build(correlation_identifier="cor-x")
    assert session.correlation.correlation_identifier == "cor-x"


def test_node_count_matches_graph_node_count() -> None:
    graph = make_graph((gnode("a"), gnode("b"), gnode("c")))
    strategy = make_strategy()
    session = ExecutionSessionBuilder().build(
        graph,
        strategy,
        context_ref=CONTEXT_REF,
        correlation_identifier="cor-x",
    )
    assert session.node_count == len(graph.nodes)
    assert session.node_count == 3


def test_checkpoints_come_from_graph() -> None:
    checkpoints = (
        Reference(target_type="checkpoint", identifier="cp-1"),
        Reference(target_type="checkpoint", identifier="cp-2"),
    )
    graph = make_graph((gnode("a"),), checkpoints=checkpoints)
    strategy = make_strategy()
    session = ExecutionSessionBuilder().build(
        graph,
        strategy,
        context_ref=CONTEXT_REF,
        correlation_identifier="cor-x",
    )
    assert session.checkpoints == graph.checkpoints
    assert session.checkpoints == checkpoints


def test_version_passes_through() -> None:
    session = _build(version="7")
    assert session.version == "7"
    assert session.identity == "session-goal-1-v7"


def test_session_is_frozen() -> None:
    session = _build()
    with pytest.raises(ValidationError):
        session.identity = "mutated"  # type: ignore[misc]


def test_build_is_deterministic() -> None:
    first = _build()
    second = _build()
    assert first == second
