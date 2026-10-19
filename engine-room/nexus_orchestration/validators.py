"""Orchestration validation — fail-fast, deterministic, no silent correction.

Guards the orchestration pipeline at its boundaries: the bound graph must be
well-formed (non-empty, unique node ids, edges resolve), it must be acyclic except
for explicitly declared loops, the request's progress sets must reference known
nodes, and the produced structure must be internally consistent (one queue item and
one dependency record per node; one harness/runtime request per ready node). A
failure raises an :class:`OrchestrationError`; the service turns that into an
``orchestration.failed`` event. Nothing is auto-corrected.
"""

from __future__ import annotations

from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_orchestration.requests import OrchestrationRequest, OrchestrationResult


class OrchestrationError(Exception):
    """Base for every orchestration failure."""


class InvalidGraphError(OrchestrationError):
    """The bound Execution Graph is malformed (empty, duplicate, or dangling)."""


class CyclicDependencyError(OrchestrationError):
    """The dependency topology contains a cycle that is not a declared loop (INV-10)."""


class UnknownNodeError(OrchestrationError):
    """A request progress set references a node that is not in the graph."""


class SessionBindingError(OrchestrationError):
    """The artifacts to bind into an Execution Session are inconsistent."""


def validate_graph(graph: ExecutionGraph) -> None:
    """The graph must be non-empty, key-unique, and edge-closed."""
    if not graph.nodes:
        raise InvalidGraphError(f"execution graph {graph.identity!r} has no nodes")
    seen: set[str] = set()
    for node in graph.nodes:
        if not node.identifier.strip():
            raise InvalidGraphError("a graph node has an empty identifier")
        if node.identifier in seen:
            raise InvalidGraphError(f"duplicate graph node {node.identifier!r}")
        seen.add(node.identifier)
        if not node.work_package_ref.identifier.strip():
            raise InvalidGraphError(f"graph node {node.identifier!r} has no work package")
    for edge in graph.edges:
        if edge.source_node not in seen or edge.target_node not in seen:
            raise InvalidGraphError(f"edge {edge.identifier!r} references an unknown node")


def validate_acyclic(graph: ExecutionGraph) -> None:
    """The dependency topology must be a DAG except for explicitly declared loops (INV-10)."""
    loop_edges = {
        (str(loop.get("source")), str(loop.get("target")))
        for loop in graph.loops
        if "source" in loop and "target" in loop
    }
    adjacency: dict[str, list[str]] = {node.identifier: [] for node in graph.nodes}
    indegree: dict[str, int] = {node.identifier: 0 for node in graph.nodes}
    for edge in graph.edges:
        if (edge.source_node, edge.target_node) in loop_edges:
            continue
        if edge.source_node not in adjacency or edge.target_node not in indegree:
            continue
        adjacency[edge.source_node].append(edge.target_node)
        indegree[edge.target_node] += 1

    ready = sorted(n for n, d in indegree.items() if d == 0)
    visited = 0
    while ready:
        node = ready.pop(0)
        visited += 1
        for target in sorted(adjacency[node]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
        ready.sort()
    if visited != len(graph.nodes):
        raise CyclicDependencyError(f"execution graph {graph.identity!r} contains a non-loop cycle")


def validate_request(request: OrchestrationRequest) -> None:
    """The request must name a real session version and reference only known nodes."""
    if not request.session_version.strip():
        raise InvalidGraphError("orchestration request has an empty session version")
    validate_graph(request.execution_graph)
    known = {node.identifier for node in request.execution_graph.nodes}
    for field, members in (
        ("completed_nodes", request.completed_nodes),
        ("paused_nodes", request.paused_nodes),
        ("approved_gates", request.approved_gates),
        ("rejected_gates", request.rejected_gates),
    ):
        for node in members:
            if node not in known:
                raise UnknownNodeError(f"{field} references unknown node {node!r}")


def validate_outputs(result: OrchestrationResult, graph: ExecutionGraph) -> None:
    """Cross-check that the produced structure is internally consistent."""
    node_count = len(graph.nodes)
    if len(result.queue_state.items) != node_count:
        raise InvalidGraphError("queue does not cover every node exactly once")
    if len(result.dependency_state.nodes) != node_count:
        raise InvalidGraphError("dependency state does not cover every node exactly once")
    if result.session.node_count != node_count:
        raise SessionBindingError("session node_count disagrees with the graph")
    if len(result.harness_requests) != len(result.queue_state.ready):
        raise InvalidGraphError("harness requests do not match the ready set")
    if len(result.runtime_requests) != len(result.harness_requests):
        raise InvalidGraphError("runtime requests do not match the harness requests")
