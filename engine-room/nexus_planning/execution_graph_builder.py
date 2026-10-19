"""Step 4 — Execution Graph construction (ADR-003 §3.3, INV-10).

Builds the Plan's operational topology: one node per Work Package, and typed
edges for declared dependencies. It expresses the requested flow features without
ever executing:

- **sequential flow / dependencies** — an ``execution`` edge per ``depends_on``.
- **parallel branches / joins** — emerge naturally from the edge set; join nodes
  (in-degree > 1) are recorded as synchronization points.
- **conditional nodes** — an item with a ``condition`` produces ``conditional``
  inbound edges and a deterministic predicate in ``conditions``.
- **approval gates** — recorded as node constraints + a graph approval policy.
- **checkpoints** — declared checkpoint references for flagged items.

The graph is directed and acyclic (validated separately). It is a *sibling* of
the Plan, referenced by id, never nested (INV-10).
"""

from __future__ import annotations

from nexus_core.contracts.base import Constraint, Correlation, Reference
from nexus_core.contracts.enums import CoordinationModel, EdgeType
from nexus_core.domain.execution_graph import ExecutionGraph, GraphEdge, GraphNode
from nexus_core.domain.goal import Goal
from nexus_planning import ids
from nexus_planning.capability_resolver import CAPABILITY_TARGET_TYPE
from nexus_planning.requests import PlanningRequest, WorkItemSpec
from nexus_planning.work_package_generator import (
    CONTEXT_TARGET_TYPE,
    GOAL_TARGET_TYPE,
    PLAN_TARGET_TYPE,
    STRATEGY_TARGET_TYPE,
    WORK_PACKAGE_TARGET_TYPE,
)

CHECKPOINT_TARGET_TYPE = "checkpoint"


class ExecutionGraphBuilder:
    """Constructs the deterministic Execution Graph for a planning request."""

    def build(
        self,
        goal: Goal,
        request: PlanningRequest,
        *,
        plan_identity: str,
        strategy_identity: str,
        coordination: CoordinationModel,
        correlation_identifier: str,
    ) -> ExecutionGraph:
        """Assemble nodes, edges, conditions, checkpoints, policies, and metadata."""
        context_ref = request.context_ref or Reference(
            target_type=CONTEXT_TARGET_TYPE, identifier=f"context-{goal.identity}"
        )
        strategy_ref = Reference(target_type=STRATEGY_TARGET_TYPE, identifier=strategy_identity)

        nodes = tuple(
            self._node(goal, item, strategy_ref=strategy_ref, context_ref=context_ref)
            for item in request.work_items
        )
        edges = self._edges(request)
        conditions = tuple(
            {"node": ids.node_id(item.key), "predicate": item.condition}
            for item in request.work_items
            if item.condition is not None
        )
        checkpoints = tuple(
            Reference(
                target_type=CHECKPOINT_TARGET_TYPE,
                identifier=f"ckpt-{ids.node_id(item.key)}",
            )
            for item in request.work_items
            if item.is_checkpoint
        )
        indegree = self._indegree(request)
        approval_gates = sorted(
            ids.node_id(item.key) for item in request.work_items if item.requires_approval
        )
        synchronization_points = sorted(node for node, degree in indegree.items() if degree > 1)
        return ExecutionGraph(
            identity=ids.graph_id(goal.identity, request.plan_version),
            parent_goal=Reference(target_type=GOAL_TARGET_TYPE, identifier=goal.identity),
            parent_plan=Reference(target_type=PLAN_TARGET_TYPE, identifier=plan_identity),
            version=request.plan_version,
            nodes=nodes,
            edges=edges,
            conditions=conditions,
            checkpoints=checkpoints,
            policies={
                "coordination": coordination.value,
                "approval_gates": approval_gates,
                "synchronization_points": synchronization_points,
            },
            metadata=self._metadata(goal, request, nodes, edges),
            correlation=Correlation(correlation_identifier=correlation_identifier),
        )

    def _node(
        self,
        goal: Goal,
        item: WorkItemSpec,
        *,
        strategy_ref: Reference,
        context_ref: Reference,
    ) -> GraphNode:
        capability_refs = tuple(
            Reference(target_type=CAPABILITY_TARGET_TYPE, identifier=capability)
            for capability in item.capability_requirements
        )
        constraints = item.constraints
        if item.requires_approval:
            constraints = (*constraints, Constraint(kind="approval"))
        return GraphNode(
            identifier=ids.node_id(item.key),
            work_package_ref=Reference(
                target_type=WORK_PACKAGE_TARGET_TYPE,
                identifier=ids.work_package_id(goal.identity, item.key),
            ),
            execution_strategy_ref=strategy_ref,
            required_skill_refs=item.skill_refs + capability_refs,
            required_context_ref=context_ref,
            constraints=constraints,
        )

    def _edges(self, request: PlanningRequest) -> tuple[GraphEdge, ...]:
        edges: list[GraphEdge] = []
        for item in request.work_items:
            target = ids.node_id(item.key)
            conditional = item.condition is not None
            edge_type = EdgeType.CONDITIONAL if conditional else EdgeType.EXECUTION
            for dependency in item.depends_on:
                source = ids.node_id(dependency)
                edges.append(
                    GraphEdge(
                        identifier=ids.edge_id(source, target, edge_type.value),
                        edge_type=edge_type,
                        source_node=source,
                        target_node=target,
                        condition=item.condition if conditional else None,
                    )
                )
        return tuple(edges)

    def _indegree(self, request: PlanningRequest) -> dict[str, int]:
        indegree = {ids.node_id(item.key): 0 for item in request.work_items}
        for item in request.work_items:
            indegree[ids.node_id(item.key)] = len(item.depends_on)
        return indegree

    def _metadata(
        self,
        goal: Goal,
        request: PlanningRequest,
        nodes: tuple[GraphNode, ...],
        edges: tuple[GraphEdge, ...],
    ) -> dict[str, object]:
        depended_on = {dep for item in request.work_items for dep in item.depends_on}
        roots = sorted(ids.node_id(item.key) for item in request.work_items if not item.depends_on)
        terminals = sorted(
            ids.node_id(item.key) for item in request.work_items if item.key not in depended_on
        )
        return {
            "goal": goal.identity,
            "plan": ids.plan_id(goal.identity, request.plan_version),
            "version": request.plan_version,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "root_nodes": roots,
            "terminal_nodes": terminals,
        }
