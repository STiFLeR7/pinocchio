"""Step 2 — Dependency Tracker (readiness determination only, never execution).

Evaluates, for every node in the Execution Graph, whether its dependencies are
satisfied. Dependencies are the inbound ordering edges (``execution`` / ``data`` /
``conditional`` / ``synchronization`` — INV-10); approval and recovery edges are
not ordering dependencies. A node is:

- **satisfied** — every dependency is in the ``completed`` set (root nodes, whose
  dependency set is empty, are trivially satisfied);
- **pending** — at least one dependency is not yet complete;
- **blocked** — it transitively depends on an unsatisfiable source (a paused node
  or a node whose approval was rejected).

It determines readiness; it never starts work, assigns a runtime, or completes a
node. Output is deterministic: nodes and their dependency lists are sorted.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, ValueObject
from nexus_core.contracts.enums import EdgeType
from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_orchestration import ids
from nexus_orchestration.vocabulary import (
    SESSION_TARGET_TYPE,
    DependencyOutcome,
)

# Inbound edges that impose ordering (and therefore readiness) on a node (INV-10).
DEPENDENCY_EDGE_TYPES = frozenset(
    {EdgeType.EXECUTION, EdgeType.DATA, EdgeType.CONDITIONAL, EdgeType.SYNCHRONIZATION}
)


class NodeDependency(ValueObject):
    """One node's dependency verdict: its direct dependencies and which remain unmet."""

    node: str
    outcome: DependencyOutcome
    dependencies: tuple[str, ...] = ()
    unmet: tuple[str, ...] = ()


class DependencyState(ValueObject):
    """The deterministic dependency snapshot for one orchestration instance."""

    identity: str
    session_ref: Reference
    nodes: tuple[NodeDependency, ...]
    satisfied: tuple[str, ...]
    pending: tuple[str, ...]
    blocked: tuple[str, ...]
    completed: tuple[str, ...]


class DependencyTracker:
    """Computes the deterministic dependency state for a graph (readiness only)."""

    def track(
        self,
        graph: ExecutionGraph,
        session_identity: str,
        *,
        completed: tuple[str, ...] = (),
        blocked_sources: tuple[str, ...] = (),
    ) -> DependencyState:
        """Evaluate every node's dependency readiness, deterministically."""
        node_ids = [node.identifier for node in graph.nodes]
        direct = self._direct_dependencies(graph, node_ids)
        forward = self._forward_adjacency(graph, node_ids)
        completed_set = {n for n in completed if n in direct}
        blocked_set = self._blocked_set(forward, blocked_sources)

        nodes: list[NodeDependency] = []
        satisfied: list[str] = []
        pending: list[str] = []
        blocked: list[str] = []
        for node in sorted(direct):
            deps = tuple(sorted(direct[node]))
            unmet = tuple(d for d in deps if d not in completed_set)
            if node in blocked_set:
                outcome = DependencyOutcome.BLOCKED
                blocked.append(node)
            elif unmet:
                outcome = DependencyOutcome.PENDING
                pending.append(node)
            else:
                outcome = DependencyOutcome.SATISFIED
                satisfied.append(node)
            nodes.append(NodeDependency(node=node, outcome=outcome, dependencies=deps, unmet=unmet))

        return DependencyState(
            identity=ids.dependency_state_id(session_identity),
            session_ref=Reference(target_type=SESSION_TARGET_TYPE, identifier=session_identity),
            nodes=tuple(nodes),
            satisfied=tuple(satisfied),
            pending=tuple(pending),
            blocked=tuple(blocked),
            completed=tuple(sorted(completed_set)),
        )

    @staticmethod
    def _direct_dependencies(graph: ExecutionGraph, node_ids: list[str]) -> dict[str, set[str]]:
        direct: dict[str, set[str]] = {node: set() for node in node_ids}
        for edge in graph.edges:
            if edge.edge_type not in DEPENDENCY_EDGE_TYPES:
                continue
            if edge.target_node in direct and edge.source_node in direct:
                direct[edge.target_node].add(edge.source_node)
        return direct

    @staticmethod
    def _forward_adjacency(graph: ExecutionGraph, node_ids: list[str]) -> dict[str, list[str]]:
        forward: dict[str, list[str]] = {node: [] for node in node_ids}
        for edge in graph.edges:
            if edge.edge_type not in DEPENDENCY_EDGE_TYPES:
                continue
            if edge.source_node in forward and edge.target_node in forward:
                forward[edge.source_node].append(edge.target_node)
        return forward

    @staticmethod
    def _blocked_set(forward: dict[str, list[str]], sources: tuple[str, ...]) -> set[str]:
        """All nodes transitively downstream of an unsatisfiable source (the sources excluded)."""
        blocked: set[str] = set()
        stack = [s for s in sources if s in forward]
        while stack:
            current = stack.pop()
            for nxt in forward.get(current, ()):
                if nxt not in blocked:
                    blocked.add(nxt)
                    stack.append(nxt)
        return blocked
