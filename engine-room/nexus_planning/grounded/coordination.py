"""Deterministic coordination analysis over the frozen Execution Graph (no reasoning, no inference).

``analyze_coordination(graph, strategy)`` reads the graph's nodes and dependency edges and derives the
P10 coordination metadata: the dependency edges (the "Dependency Graph" — INV-10), topological levels
(parallel groups and the sequential barriers between them), fan-out/fan-in (merge) boundaries, and the
governed checkpoint/approval/recovery boundaries. It is a pure function of already-recorded facts —
identical graphs yield identical views. The graph is directed-acyclic (the incumbent validates this
before this runs), so leveling is well-defined.
"""

from __future__ import annotations

from collections import deque

from nexus_core.contracts.enums import EdgeType
from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_planning.grounded.model import CoordinationView

_CHECKPOINT_PREFIX = "ckpt-"


def _dependency_edges(graph: ExecutionGraph) -> tuple[tuple[str, str], ...]:
    """The execution-dependency edges (source → target), sorted — dependencies ARE edges (INV-10)."""
    return tuple(
        sorted(
            (edge.source_node, edge.target_node)
            for edge in graph.edges
            if edge.edge_type is EdgeType.EXECUTION
        )
    )


def _levels(node_ids: list[str], edges: tuple[tuple[str, str], ...]) -> list[tuple[str, ...]]:
    """Longest-path topological levels (Kahn); deterministic regardless of processing order."""
    successors: dict[str, list[str]] = {n: [] for n in node_ids}
    indegree: dict[str, int] = dict.fromkeys(node_ids, 0)
    for source, target in edges:
        successors[source].append(target)
        indegree[target] += 1

    level: dict[str, int] = dict.fromkeys(node_ids, 0)
    remaining = dict(indegree)
    queue: deque[str] = deque(sorted(n for n in node_ids if indegree[n] == 0))
    while queue:
        node = queue.popleft()
        for succ in sorted(successors[node]):
            level[succ] = max(level[succ], level[node] + 1)
            remaining[succ] -= 1
            if remaining[succ] == 0:
                queue.append(succ)

    max_level = max(level.values(), default=0)
    return [
        tuple(sorted(n for n in node_ids if level[n] == depth)) for depth in range(max_level + 1)
    ]


def _checkpoint_nodes(graph: ExecutionGraph) -> tuple[str, ...]:
    """The node ids that carry a checkpoint (recovery resume points — INV-18)."""
    nodes = []
    for ref in graph.checkpoints:
        identifier = ref.identifier
        nodes.append(
            identifier[len(_CHECKPOINT_PREFIX) :]
            if identifier.startswith(_CHECKPOINT_PREFIX)
            else identifier
        )
    return tuple(sorted(nodes))


def analyze_coordination(graph: ExecutionGraph, strategy: ExecutionStrategy) -> CoordinationView:
    """Derive the deterministic coordination view from the graph topology and the strategy."""
    node_ids = sorted(node.identifier for node in graph.nodes)
    edges = _dependency_edges(graph)

    outdegree: dict[str, int] = dict.fromkeys(node_ids, 0)
    indegree: dict[str, int] = dict.fromkeys(node_ids, 0)
    for source, target in edges:
        outdegree[source] += 1
        indegree[target] += 1

    levels = _levels(node_ids, edges)
    checkpoints = _checkpoint_nodes(graph)
    approval_gates = tuple(sorted(str(n) for n in graph.policies.get("approval_gates", ())))

    return CoordinationView(
        coordination_model=strategy.coordination.value,
        dependency_edges=edges,
        parallel_groups=tuple(level for level in levels if len(level) > 1),
        sequential_levels=tuple(levels),
        fan_out_points=tuple(sorted(n for n in node_ids if outdegree[n] > 1)),
        merge_boundaries=tuple(sorted(n for n in node_ids if indegree[n] > 1)),
        checkpoint_boundaries=checkpoints,
        approval_boundaries=approval_gates,
        # Recovery resumes from checkpoints + event replay (INV-18); those are its boundaries.
        recovery_boundaries=checkpoints,
    )
