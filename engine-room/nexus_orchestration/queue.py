"""Step 3 — Execution Queue (deterministic scheduling; never execution).

Assigns every node a queue state derived from its dependency readiness and its
approval gate, and orders the queue deterministically by topological rank then node
identifier. States (pre-execution subset):

- **completed** — already done (supplied as orchestration progress);
- **paused** — explicitly paused;
- **ready** — dependencies satisfied and approval granted (or not required);
- **waiting** — dependencies satisfied but an approval is pending;
- **blocked** — dependencies unmet, or transitively blocked, or approval rejected.

Ordering is a stable topological sort (sorted tie-break), so identical inputs yield
an identical queue. The queue schedules; it never starts work.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, ValueObject
from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_orchestration import ids
from nexus_orchestration.approvals import ApprovalState
from nexus_orchestration.dependency_tracker import (
    DEPENDENCY_EDGE_TYPES,
    DependencyState,
    NodeDependency,
)
from nexus_orchestration.vocabulary import (
    SESSION_TARGET_TYPE,
    ApprovalStatus,
    DependencyOutcome,
    QueueItemState,
)


class QueueItem(ValueObject):
    """One node's place in the execution queue: its state, order, and any blockers."""

    node: str
    work_package_ref: Reference
    state: QueueItemState
    position: int
    blocked_by: tuple[str, ...] = ()


class QueueState(ValueObject):
    """The deterministic execution-queue snapshot for one orchestration instance."""

    identity: str
    session_ref: Reference
    items: tuple[QueueItem, ...]
    ready: tuple[str, ...]
    waiting: tuple[str, ...]
    blocked: tuple[str, ...]
    paused: tuple[str, ...]
    completed: tuple[str, ...]


class ExecutionQueueBuilder:
    """Builds the deterministic, topologically ordered execution queue."""

    def build(
        self,
        graph: ExecutionGraph,
        dependency_state: DependencyState,
        approval_state: ApprovalState,
        session_identity: str,
        *,
        completed: tuple[str, ...] = (),
        paused: tuple[str, ...] = (),
    ) -> QueueState:
        """Assign each node a queue state and order the queue deterministically."""
        rank = self._topological_rank(graph)
        wp_ref = {node.identifier: node.work_package_ref for node in graph.nodes}
        dep_by_node = {nd.node: nd for nd in dependency_state.nodes}
        appr_by_node = {gate.node: gate.status for gate in approval_state.gates}
        completed_set = set(completed)
        paused_set = set(paused)

        ordered = sorted(wp_ref, key=lambda node: (rank.get(node, 0), node))
        items: list[QueueItem] = []
        buckets: dict[QueueItemState, list[str]] = {state: [] for state in QueueItemState}
        for position, node in enumerate(ordered):
            state, blocked_by = self._state(
                node, dep_by_node[node], appr_by_node.get(node), completed_set, paused_set
            )
            buckets[state].append(node)
            items.append(
                QueueItem(
                    node=node,
                    work_package_ref=wp_ref[node],
                    state=state,
                    position=position,
                    blocked_by=blocked_by,
                )
            )

        return QueueState(
            identity=ids.queue_state_id(session_identity),
            session_ref=Reference(target_type=SESSION_TARGET_TYPE, identifier=session_identity),
            items=tuple(items),
            ready=tuple(buckets[QueueItemState.READY]),
            waiting=tuple(buckets[QueueItemState.WAITING]),
            blocked=tuple(buckets[QueueItemState.BLOCKED]),
            paused=tuple(buckets[QueueItemState.PAUSED]),
            completed=tuple(buckets[QueueItemState.COMPLETED]),
        )

    @staticmethod
    def _state(
        node: str,
        dependency: NodeDependency,
        approval: ApprovalStatus | None,
        completed: set[str],
        paused: set[str],
    ) -> tuple[QueueItemState, tuple[str, ...]]:
        if node in completed:
            return QueueItemState.COMPLETED, ()
        if node in paused:
            return QueueItemState.PAUSED, ()
        if approval is ApprovalStatus.REJECTED:
            return QueueItemState.BLOCKED, ()
        if dependency.outcome is DependencyOutcome.SATISFIED:
            if approval is ApprovalStatus.REQUESTED:
                return QueueItemState.WAITING, ()
            return QueueItemState.READY, ()
        blockers = dependency.unmet or dependency.dependencies
        return QueueItemState.BLOCKED, blockers

    @staticmethod
    def _topological_rank(graph: ExecutionGraph) -> dict[str, int]:
        node_ids = [node.identifier for node in graph.nodes]
        adjacency: dict[str, list[str]] = {node: [] for node in node_ids}
        indegree: dict[str, int] = dict.fromkeys(node_ids, 0)
        loop_edges = {
            (str(loop.get("source")), str(loop.get("target")))
            for loop in graph.loops
            if "source" in loop and "target" in loop
        }
        for edge in graph.edges:
            if edge.edge_type not in DEPENDENCY_EDGE_TYPES:
                continue
            if (edge.source_node, edge.target_node) in loop_edges:
                continue
            if edge.source_node in adjacency and edge.target_node in indegree:
                adjacency[edge.source_node].append(edge.target_node)
                indegree[edge.target_node] += 1

        ready = sorted(n for n, d in indegree.items() if d == 0)
        rank: dict[str, int] = {}
        index = 0
        while ready:
            node = ready.pop(0)
            rank[node] = index
            index += 1
            for target in sorted(adjacency[node]):
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
            ready.sort()
        # Any node left out by a cycle (defensively) keeps a high stable rank.
        for node in node_ids:
            rank.setdefault(node, index)
            index += 1
        return rank
