"""Unit tests for the Execution Queue builder (Phase 5 — Orchestration, Step 3).

The builder assigns every node a deterministic queue state derived from its
dependency readiness and its approval gate, then orders the queue by topological
rank (stable, sorted tie-break) then node id. It schedules; it never executes.

The state mapping under test (``_state``):

- in ``completed`` → COMPLETED; in ``paused`` → PAUSED;
- approval REJECTED → BLOCKED;
- dependency SATISFIED + approval REQUESTED → WAITING;
- dependency SATISFIED + (no gate or GRANTED) → READY;
- dependency PENDING/BLOCKED → BLOCKED (``blocked_by`` = unmet deps).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.enums import ApprovalTaxonomy
from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_orchestration.approvals import ApprovalCoordinator, ApprovalState
from nexus_orchestration.dependency_tracker import DependencyState, DependencyTracker
from nexus_orchestration.queue import ExecutionQueueBuilder, QueueItem, QueueState
from nexus_orchestration.vocabulary import QueueItemState
from tests.unit.nexus_orchestration.helpers import gedge, gnode, make_graph, make_strategy

SESSION = "session-goal-1-v1"


def _deps(
    graph: ExecutionGraph,
    *,
    completed: tuple[str, ...] = (),
    blocked_sources: tuple[str, ...] = (),
) -> DependencyState:
    return DependencyTracker().track(
        graph,
        SESSION,
        completed=completed,
        blocked_sources=blocked_sources,
    )


def _approvals(
    graph: ExecutionGraph,
    *,
    taxonomy: ApprovalTaxonomy = ApprovalTaxonomy.AUTOMATIC,
    approved: tuple[str, ...] = (),
    rejected: tuple[str, ...] = (),
) -> ApprovalState:
    strategy = make_strategy(approval_policy=taxonomy)
    return ApprovalCoordinator().coordinate(
        graph,
        strategy,
        SESSION,
        approved=approved,
        rejected=rejected,
    )


def _build(
    graph: ExecutionGraph,
    *,
    dep_completed: tuple[str, ...] = (),
    blocked_sources: tuple[str, ...] = (),
    taxonomy: ApprovalTaxonomy = ApprovalTaxonomy.AUTOMATIC,
    approved: tuple[str, ...] = (),
    rejected: tuple[str, ...] = (),
    completed: tuple[str, ...] = (),
    paused: tuple[str, ...] = (),
) -> QueueState:
    dependency_state = _deps(graph, completed=dep_completed, blocked_sources=blocked_sources)
    approval_state = _approvals(graph, taxonomy=taxonomy, approved=approved, rejected=rejected)
    return ExecutionQueueBuilder().build(
        graph,
        dependency_state,
        approval_state,
        SESSION,
        completed=completed,
        paused=paused,
    )


def _state_of(queue: QueueState, node: str) -> QueueItemState:
    return next(item.state for item in queue.items if item.node == node)


def _item(queue: QueueState, node: str) -> QueueItem:
    return next(item for item in queue.items if item.node == node)


# --------------------------------------------------------------------------- #
# State mapping                                                                 #
# --------------------------------------------------------------------------- #


def test_completed_node_is_completed() -> None:
    graph = make_graph((gnode("a"),))
    queue = _build(graph, completed=("node-a",))

    assert _state_of(queue, "node-a") is QueueItemState.COMPLETED
    assert queue.completed == ("node-a",)
    assert _item(queue, "node-a").blocked_by == ()


def test_paused_node_is_paused() -> None:
    graph = make_graph((gnode("a"),))
    queue = _build(graph, paused=("node-a",))

    assert _state_of(queue, "node-a") is QueueItemState.PAUSED
    assert queue.paused == ("node-a",)


def test_completed_takes_precedence_over_paused() -> None:
    graph = make_graph((gnode("a"),))
    queue = _build(graph, completed=("node-a",), paused=("node-a",))

    assert _state_of(queue, "node-a") is QueueItemState.COMPLETED


def test_rejected_approval_blocks_node() -> None:
    graph = make_graph((gnode("a", approval=True),))
    queue = _build(graph, taxonomy=ApprovalTaxonomy.HUMAN_REVIEW, rejected=("node-a",))

    assert _state_of(queue, "node-a") is QueueItemState.BLOCKED
    assert queue.blocked == ("node-a",)
    # Rejection-blocked nodes carry no dependency blockers.
    assert _item(queue, "node-a").blocked_by == ()


def test_satisfied_with_requested_approval_is_waiting() -> None:
    graph = make_graph((gnode("a", approval=True),))
    queue = _build(graph, taxonomy=ApprovalTaxonomy.HUMAN_REVIEW)

    assert _state_of(queue, "node-a") is QueueItemState.WAITING
    assert queue.waiting == ("node-a",)


def test_satisfied_without_gate_is_ready() -> None:
    graph = make_graph((gnode("a"),))
    queue = _build(graph)

    assert _state_of(queue, "node-a") is QueueItemState.READY
    assert queue.ready == ("node-a",)


def test_satisfied_with_granted_approval_is_ready() -> None:
    graph = make_graph((gnode("a", approval=True),))
    queue = _build(graph, taxonomy=ApprovalTaxonomy.HUMAN_REVIEW, approved=("node-a",))

    assert _state_of(queue, "node-a") is QueueItemState.READY
    assert queue.ready == ("node-a",)


def test_pending_dependency_blocks_with_unmet_blockers() -> None:
    # a -> b; nothing completed, so b's dependency on a is unmet (PENDING).
    graph = make_graph((gnode("a"), gnode("b")), (gedge("a", "b"),))
    queue = _build(graph)

    assert _state_of(queue, "node-a") is QueueItemState.READY
    assert _state_of(queue, "node-b") is QueueItemState.BLOCKED
    assert _item(queue, "node-b").blocked_by == ("node-a",)
    assert queue.blocked == ("node-b",)


def test_blocked_dependency_blocks_with_dependency_blockers() -> None:
    # a -> b; a is an unsatisfiable (blocked) source, so b is transitively BLOCKED.
    # Its dependencies are met by completing a, so unmet is empty and blocked_by
    # falls back to the full dependency list.
    graph = make_graph((gnode("a"), gnode("b")), (gedge("a", "b"),))
    queue = _build(graph, dep_completed=("node-a",), blocked_sources=("node-a",))

    assert _state_of(queue, "node-b") is QueueItemState.BLOCKED
    assert _item(queue, "node-b").blocked_by == ("node-a",)


# --------------------------------------------------------------------------- #
# Ordering / positions                                                          #
# --------------------------------------------------------------------------- #


def test_chain_is_topologically_ordered() -> None:
    # a -> b -> c must produce order a, b, c with positions 0, 1, 2.
    graph = make_graph(
        (gnode("c"), gnode("a"), gnode("b")),
        (gedge("a", "b"), gedge("b", "c")),
    )
    queue = _build(graph)

    order = tuple(item.node for item in queue.items)
    assert order == ("node-a", "node-b", "node-c")
    assert tuple(item.position for item in queue.items) == (0, 1, 2)


def test_diamond_orders_roots_before_dependents_then_by_id() -> None:
    # a -> b, a -> c, b -> d, c -> d. a first, then b,c (sorted by id), then d.
    graph = make_graph(
        (gnode("d"), gnode("c"), gnode("b"), gnode("a")),
        (gedge("a", "b"), gedge("a", "c"), gedge("b", "d"), gedge("c", "d")),
    )
    queue = _build(graph)

    order = tuple(item.node for item in queue.items)
    assert order == ("node-a", "node-b", "node-c", "node-d")
    # A root always precedes its dependents.
    assert order.index("node-a") < order.index("node-b")
    assert order.index("node-a") < order.index("node-c")
    assert order.index("node-b") < order.index("node-d")
    assert order.index("node-c") < order.index("node-d")


def test_roots_at_same_rank_break_ties_by_node_id() -> None:
    graph = make_graph((gnode("c"), gnode("a"), gnode("b")))
    queue = _build(graph)

    assert tuple(item.node for item in queue.items) == ("node-a", "node-b", "node-c")


def test_position_is_the_item_index() -> None:
    graph = make_graph((gnode("a"), gnode("b"), gnode("c")))
    queue = _build(graph)

    for index, item in enumerate(queue.items):
        assert item.position == index


# --------------------------------------------------------------------------- #
# Partition / identity / determinism                                            #
# --------------------------------------------------------------------------- #


def test_buckets_partition_the_nodes() -> None:
    # ready: node-a; waiting: node-w (gated, requested); blocked: node-b (pending);
    # paused: node-p; completed: node-c.
    graph = make_graph(
        (
            gnode("a"),
            gnode("w", approval=True),
            gnode("dep"),
            gnode("b"),
            gnode("p"),
            gnode("c"),
        ),
        (gedge("dep", "b"),),
    )
    queue = _build(
        graph,
        taxonomy=ApprovalTaxonomy.HUMAN_REVIEW,
        paused=("node-p",),
        completed=("node-c",),
    )

    all_nodes = {item.node for item in queue.items}
    partitioned = (
        set(queue.ready)
        | set(queue.waiting)
        | set(queue.blocked)
        | set(queue.paused)
        | set(queue.completed)
    )
    assert partitioned == all_nodes
    total = (
        len(queue.ready)
        + len(queue.waiting)
        + len(queue.blocked)
        + len(queue.paused)
        + len(queue.completed)
    )
    assert total == len(all_nodes)

    assert "node-w" in queue.waiting
    assert "node-b" in queue.blocked
    assert "node-p" in queue.paused
    assert "node-c" in queue.completed
    assert "node-a" in queue.ready


def test_identity_and_session_reference() -> None:
    graph = make_graph((gnode("a"),))
    queue = _build(graph)

    assert queue.identity == f"queue-{SESSION}"
    assert queue.session_ref.identifier == SESSION
    assert queue.session_ref.target_type == "execution_session"


def test_determinism_same_inputs_same_state() -> None:
    nodes = (gnode("d"), gnode("c"), gnode("b"), gnode("a"))
    edges = (gedge("a", "b"), gedge("a", "c"), gedge("b", "d"), gedge("c", "d"))

    first = _build(make_graph(nodes, edges))
    second = _build(make_graph(nodes, edges))

    assert first == second
    assert first.items == second.items


# --------------------------------------------------------------------------- #
# Immutability                                                                  #
# --------------------------------------------------------------------------- #


def test_queue_item_is_frozen() -> None:
    graph = make_graph((gnode("a"),))
    item = _item(_build(graph), "node-a")
    with pytest.raises(ValidationError):
        item.state = QueueItemState.BLOCKED  # type: ignore[misc]


def test_queue_state_is_frozen() -> None:
    queue = _build(make_graph((gnode("a"),)))
    with pytest.raises(ValidationError):
        queue.items = ()  # type: ignore[misc]
