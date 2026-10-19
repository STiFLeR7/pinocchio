"""Planning validation — fail-fast, deterministic, no silent correction.

Validation guards the planning pipeline at its boundaries: the Goal must be
plannable, the decomposition must be well-formed, the produced graph must be
acyclic (except declared loops, INV-10), and every produced reference must
resolve. A failure raises a :class:`PlanningError`; the service turns that into a
``planning.failed`` event. Nothing is auto-corrected.
"""

from __future__ import annotations

from nexus_core.contracts.status import GoalStatus
from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_core.domain.goal import Goal
from nexus_core.domain.work_package import WorkPackage
from nexus_planning.requests import PlanningRequest

# A Goal in a terminal lifecycle state cannot be (re)planned.
_TERMINAL_GOAL_STATES = frozenset({GoalStatus.ACHIEVED, GoalStatus.ABANDONED})


class PlanningError(Exception):
    """Base for every planning failure."""


class GoalNotPlannableError(PlanningError):
    """The Goal cannot be planned (terminal state or malformed)."""


class InvalidDecompositionError(PlanningError):
    """The declared work decomposition is malformed (empty, duplicate, or dangling)."""


class CyclicGraphError(PlanningError):
    """The execution topology contains a cycle that is not a declared loop (INV-10)."""


class DanglingReferenceError(PlanningError):
    """A produced object references an identifier that does not exist."""


def validate_goal(goal: Goal) -> None:
    """The Goal must be present, have an outcome, and not be in a terminal state."""
    if not goal.outcome.strip():
        raise GoalNotPlannableError(f"goal {goal.identity!r} has no outcome")
    if goal.status is not None and goal.status in _TERMINAL_GOAL_STATES:
        raise GoalNotPlannableError(
            f"goal {goal.identity!r} is in terminal state {goal.status.value!r}"
        )


def validate_request(request: PlanningRequest) -> None:
    """The decomposition must be non-empty, key-unique, and dependency-closed."""
    items = request.work_items
    if not items:
        raise InvalidDecompositionError("planning request has no work items")
    keys = [item.key for item in items]
    seen: set[str] = set()
    for key in keys:
        if not key.strip():
            raise InvalidDecompositionError("a work item has an empty key")
        if key in seen:
            raise InvalidDecompositionError(f"duplicate work-item key {key!r}")
        seen.add(key)
    known = set(keys)
    for item in items:
        if item.key in item.depends_on:
            raise InvalidDecompositionError(f"work item {item.key!r} depends on itself")
        for dependency in item.depends_on:
            if dependency not in known:
                raise InvalidDecompositionError(
                    f"work item {item.key!r} depends on unknown item {dependency!r}"
                )


def validate_acyclic(graph: ExecutionGraph) -> None:
    """The graph must be a DAG except for explicitly declared loops (INV-10)."""
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
            raise DanglingReferenceError(f"edge {edge.identifier!r} references an unknown node")
        adjacency[edge.source_node].append(edge.target_node)
        indegree[edge.target_node] += 1

    # Kahn's algorithm — deterministic order by sorted node id.
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
        raise CyclicGraphError(f"execution graph {graph.identity!r} contains a non-loop cycle")


def validate_outputs(
    plan_graph_ref: str,
    graph: ExecutionGraph,
    work_packages: tuple[WorkPackage, ...],
    plan_wp_refs: tuple[str, ...],
) -> None:
    """Cross-check that the produced Plan, Work Packages, and graph agree."""
    wp_ids = {wp.identifier for wp in work_packages}
    if set(plan_wp_refs) != wp_ids:
        raise DanglingReferenceError("plan work-package references do not match generated packages")
    if plan_graph_ref != graph.identity:
        raise DanglingReferenceError("plan execution-graph reference does not match the graph")
    for node in graph.nodes:
        if node.work_package_ref.identifier not in wp_ids:
            raise DanglingReferenceError(
                f"graph node {node.identifier!r} references unknown work package"
            )
