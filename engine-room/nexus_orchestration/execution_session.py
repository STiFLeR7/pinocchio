"""Step 1 — Execution Session (the immutable orchestration instance).

An Execution Session binds, by reference, the five artifacts one orchestration
instance coordinates — Goal, Context Package, Plan, Execution Graph, Execution
Strategy — and records the coordination model and checkpoint references it will
honor. It is immutable and carries no execution state: it *names* what is being
coordinated, never how it runs (doc 07 *Outputs*).

There is no frozen core contract for an Execution Session; it is an Orchestration
output, so the value object is defined here in the orchestration layer.
"""

from __future__ import annotations

from nexus_core.contracts.base import Correlation, Reference, ValueObject
from nexus_core.contracts.enums import CoordinationModel
from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_orchestration import ids
from nexus_orchestration.vocabulary import (
    GRAPH_TARGET_TYPE,
    STRATEGY_TARGET_TYPE,
    SessionStatus,
)


class ExecutionSession(ValueObject):
    """One orchestration instance: the five bound artifacts plus coordination metadata."""

    identity: str
    goal_ref: Reference
    context_ref: Reference
    plan_ref: Reference
    execution_graph_ref: Reference
    execution_strategy_ref: Reference
    coordination: CoordinationModel
    correlation: Correlation
    checkpoints: tuple[Reference, ...] = ()
    node_count: int = 0
    version: str = "1"
    status: SessionStatus | None = None
    """Current lifecycle state — a projection of the event log; optional until projected."""


class ExecutionSessionBuilder:
    """Binds the five artifacts into one immutable Execution Session (deterministic)."""

    def build(
        self,
        graph: ExecutionGraph,
        strategy: ExecutionStrategy,
        *,
        context_ref: Reference,
        correlation_identifier: str,
        version: str = "1",
    ) -> ExecutionSession:
        """Assemble the session from the graph's lineage and the strategy."""
        return ExecutionSession(
            identity=ids.session_id(graph.parent_goal.identifier, version),
            goal_ref=graph.parent_goal,
            context_ref=context_ref,
            plan_ref=graph.parent_plan,
            execution_graph_ref=Reference(target_type=GRAPH_TARGET_TYPE, identifier=graph.identity),
            execution_strategy_ref=Reference(
                target_type=STRATEGY_TARGET_TYPE, identifier=strategy.identity
            ),
            coordination=strategy.coordination,
            correlation=Correlation(correlation_identifier=correlation_identifier),
            checkpoints=graph.checkpoints,
            node_count=len(graph.nodes),
            version=version,
        )
