"""Unit tests for the Orchestration dependency tracker (Phase 5).

The :class:`DependencyTracker` determines per-node *readiness* over an Execution
Graph and never executes anything. These tests pin its semantics with real
domain objects built through the shared helpers: only ordering edge types impose
dependencies (INV-10), roots are trivially satisfied, completion promotes nodes
to satisfied, a blocked source poisons everything transitively downstream of it,
and the output is deterministic and immutable.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.enums import EdgeType
from nexus_orchestration.dependency_tracker import (
    DEPENDENCY_EDGE_TYPES,
    DependencyState,
    DependencyTracker,
    NodeDependency,
)
from nexus_orchestration.vocabulary import (
    SESSION_TARGET_TYPE,
    DependencyOutcome,
)
from tests.unit.nexus_orchestration.helpers import gedge, gnode, make_graph

SESSION = "session-goal-1-v1"


def _node(state: DependencyState, identifier: str) -> NodeDependency:
    """Return the single :class:`NodeDependency` for ``identifier`` (must exist)."""
    matches = [n for n in state.nodes if n.node == identifier]
    assert len(matches) == 1, f"expected exactly one node {identifier!r}, got {matches}"
    return matches[0]


# --------------------------------------------------------------------------- #
# Dependency edge-type set (INV-10)                                            #
# --------------------------------------------------------------------------- #


def test_dependency_edge_types_are_exactly_the_ordering_edges() -> None:
    assert (
        frozenset(
            {
                EdgeType.EXECUTION,
                EdgeType.DATA,
                EdgeType.CONDITIONAL,
                EdgeType.SYNCHRONIZATION,
            }
        )
        == DEPENDENCY_EDGE_TYPES
    )
    assert EdgeType.APPROVAL not in DEPENDENCY_EDGE_TYPES
    assert EdgeType.RECOVERY not in DEPENDENCY_EDGE_TYPES


# --------------------------------------------------------------------------- #
# Root nodes                                                                   #
# --------------------------------------------------------------------------- #


def test_root_node_with_no_inbound_edges_is_satisfied() -> None:
    graph = make_graph((gnode("research"),))

    state = DependencyTracker().track(graph, SESSION)

    assert state.satisfied == ("node-research",)
    assert state.pending == ()
    assert state.blocked == ()
    node = _node(state, "node-research")
    assert node.outcome is DependencyOutcome.SATISFIED
    assert node.dependencies == ()
    assert node.unmet == ()


def test_isolated_nodes_are_all_satisfied_roots() -> None:
    graph = make_graph((gnode("a"), gnode("b"), gnode("c")))

    state = DependencyTracker().track(graph, SESSION)

    assert state.satisfied == ("node-a", "node-b", "node-c")
    assert state.pending == ()
    assert state.blocked == ()


# --------------------------------------------------------------------------- #
# Pending vs. satisfied via the completed set                                  #
# --------------------------------------------------------------------------- #


def test_dependent_node_is_pending_when_completed_is_empty() -> None:
    graph = make_graph(
        (gnode("research"), gnode("build")),
        (gedge("research", "build"),),
    )

    state = DependencyTracker().track(graph, SESSION)

    # research is a root (satisfied); build depends on research (pending).
    assert state.satisfied == ("node-research",)
    assert state.pending == ("node-build",)
    assert state.blocked == ()

    build = _node(state, "node-build")
    assert build.outcome is DependencyOutcome.PENDING
    assert build.dependencies == ("node-research",)
    assert build.unmet == ("node-research",)


def test_every_non_root_node_is_pending_with_empty_completed() -> None:
    graph = make_graph(
        (gnode("a"), gnode("b"), gnode("c")),
        (gedge("a", "b"), gedge("b", "c")),
    )

    state = DependencyTracker().track(graph, SESSION)

    assert state.satisfied == ("node-a",)
    assert state.pending == ("node-b", "node-c")
    assert state.blocked == ()


def test_node_becomes_satisfied_when_all_dependencies_completed() -> None:
    graph = make_graph(
        (gnode("research"), gnode("build")),
        (gedge("research", "build"),),
    )

    state = DependencyTracker().track(graph, SESSION, completed=("node-research",))

    assert state.satisfied == ("node-build", "node-research")
    assert state.pending == ()
    assert state.blocked == ()

    build = _node(state, "node-build")
    assert build.outcome is DependencyOutcome.SATISFIED
    assert build.dependencies == ("node-research",)
    assert build.unmet == ()


def test_node_with_multiple_deps_stays_pending_until_all_completed() -> None:
    graph = make_graph(
        (gnode("a"), gnode("b"), gnode("target")),
        (gedge("a", "target"), gedge("b", "target")),
    )

    # Only one of two dependencies completed -> still pending, one unmet.
    state = DependencyTracker().track(graph, SESSION, completed=("node-a",))

    target = _node(state, "node-target")
    assert target.outcome is DependencyOutcome.PENDING
    assert target.dependencies == ("node-a", "node-b")
    assert target.unmet == ("node-b",)
    assert "node-target" in state.pending

    # Both completed -> satisfied, nothing unmet.
    state = DependencyTracker().track(graph, SESSION, completed=("node-a", "node-b"))
    target = _node(state, "node-target")
    assert target.outcome is DependencyOutcome.SATISFIED
    assert target.unmet == ()
    assert "node-target" in state.satisfied


def test_completed_entries_for_unknown_nodes_are_dropped() -> None:
    graph = make_graph(
        (gnode("research"), gnode("build")),
        (gedge("research", "build"),),
    )

    state = DependencyTracker().track(
        graph,
        SESSION,
        completed=("node-research", "node-ghost"),
    )

    # The ghost id is not a graph node, so it is filtered out of completed.
    assert state.completed == ("node-research",)
    assert "node-ghost" not in state.completed


# --------------------------------------------------------------------------- #
# Blocked sources poison downstream nodes                                      #
# --------------------------------------------------------------------------- #


def test_blocked_source_blocks_transitive_downstream_but_not_itself() -> None:
    graph = make_graph(
        (gnode("a"), gnode("b"), gnode("c")),
        (gedge("a", "b"), gedge("b", "c")),
    )

    state = DependencyTracker().track(graph, SESSION, blocked_sources=("node-a",))

    # The source itself is only an origin: it stays a satisfied root.
    assert _node(state, "node-a").outcome is DependencyOutcome.SATISFIED
    assert state.satisfied == ("node-a",)
    # Everything transitively downstream is blocked.
    assert state.blocked == ("node-b", "node-c")
    assert _node(state, "node-b").outcome is DependencyOutcome.BLOCKED
    assert _node(state, "node-c").outcome is DependencyOutcome.BLOCKED
    assert state.pending == ()


def test_blocked_takes_precedence_over_completed_dependencies() -> None:
    graph = make_graph(
        (gnode("a"), gnode("b")),
        (gedge("a", "b"),),
    )

    # Even with the dependency completed, a poisoned node remains blocked.
    state = DependencyTracker().track(
        graph,
        SESSION,
        completed=("node-a",),
        blocked_sources=("node-a",),
    )

    assert _node(state, "node-b").outcome is DependencyOutcome.BLOCKED
    assert state.blocked == ("node-b",)
    assert "node-b" not in state.satisfied


def test_unrelated_branch_is_unaffected_by_a_blocked_source() -> None:
    graph = make_graph(
        (gnode("a"), gnode("b"), gnode("x"), gnode("y")),
        (gedge("a", "b"), gedge("x", "y")),
    )

    state = DependencyTracker().track(graph, SESSION, blocked_sources=("node-a",))

    assert state.blocked == ("node-b",)
    # The x->y branch is untouched by blocking a in the other branch.
    assert _node(state, "node-x").outcome is DependencyOutcome.SATISFIED
    assert _node(state, "node-y").outcome is DependencyOutcome.PENDING


def test_blocked_source_not_in_graph_is_ignored() -> None:
    graph = make_graph(
        (gnode("a"), gnode("b")),
        (gedge("a", "b"),),
    )

    state = DependencyTracker().track(graph, SESSION, blocked_sources=("node-ghost",))

    assert state.blocked == ()
    assert _node(state, "node-b").outcome is DependencyOutcome.PENDING


# --------------------------------------------------------------------------- #
# Only ordering edge types count                                              #
# --------------------------------------------------------------------------- #


def test_approval_edge_does_not_create_a_dependency() -> None:
    graph = make_graph(
        (gnode("gate"), gnode("build")),
        (gedge("gate", "build", edge_type=EdgeType.APPROVAL),),
    )

    state = DependencyTracker().track(graph, SESSION)

    # An approval edge is not an ordering edge: build stays a satisfied root.
    build = _node(state, "node-build")
    assert build.outcome is DependencyOutcome.SATISFIED
    assert build.dependencies == ()
    assert build.unmet == ()
    assert state.satisfied == ("node-build", "node-gate")
    assert state.pending == ()


def test_recovery_edge_does_not_create_a_dependency() -> None:
    graph = make_graph(
        (gnode("source"), gnode("target")),
        (gedge("source", "target", edge_type=EdgeType.RECOVERY),),
    )

    state = DependencyTracker().track(graph, SESSION)

    assert _node(state, "node-target").outcome is DependencyOutcome.SATISFIED
    assert state.satisfied == ("node-source", "node-target")


def test_recovery_edge_does_not_propagate_blocking() -> None:
    graph = make_graph(
        (gnode("a"), gnode("b")),
        (gedge("a", "b", edge_type=EdgeType.RECOVERY),),
    )

    # b is reachable from a only via a non-ordering edge -> blocking a leaves b alone.
    state = DependencyTracker().track(graph, SESSION, blocked_sources=("node-a",))

    assert state.blocked == ()
    assert _node(state, "node-b").outcome is DependencyOutcome.SATISFIED


@pytest.mark.parametrize(
    "edge_type",
    [
        EdgeType.EXECUTION,
        EdgeType.DATA,
        EdgeType.CONDITIONAL,
        EdgeType.SYNCHRONIZATION,
    ],
)
def test_each_ordering_edge_type_creates_a_dependency(edge_type: EdgeType) -> None:
    graph = make_graph(
        (gnode("source"), gnode("target")),
        (gedge("source", "target", edge_type=edge_type),),
    )

    state = DependencyTracker().track(graph, SESSION)

    target = _node(state, "node-target")
    assert target.dependencies == ("node-source",)
    assert target.outcome is DependencyOutcome.PENDING


# --------------------------------------------------------------------------- #
# Diamond topology                                                            #
# --------------------------------------------------------------------------- #


def _diamond() -> object:
    """a -> b, a -> c, b -> d, c -> d."""
    return make_graph(
        (gnode("a"), gnode("b"), gnode("c"), gnode("d")),
        (gedge("a", "b"), gedge("a", "c"), gedge("b", "d"), gedge("c", "d")),
    )


def test_diamond_empty_completed() -> None:
    state = DependencyTracker().track(_diamond(), SESSION)  # type: ignore[arg-type]

    assert _node(state, "node-a").outcome is DependencyOutcome.SATISFIED
    for nid in ("node-b", "node-c", "node-d"):
        assert _node(state, nid).outcome is DependencyOutcome.PENDING
    assert state.satisfied == ("node-a",)
    assert state.pending == ("node-b", "node-c", "node-d")

    d = _node(state, "node-d")
    assert d.dependencies == ("node-b", "node-c")
    assert d.unmet == ("node-b", "node-c")


def test_diamond_apex_completed() -> None:
    state = DependencyTracker().track(
        _diamond(),  # type: ignore[arg-type]
        SESSION,
        completed=("node-a",),
    )

    assert _node(state, "node-b").outcome is DependencyOutcome.SATISFIED
    assert _node(state, "node-c").outcome is DependencyOutcome.SATISFIED
    # d still waits on both b and c.
    d = _node(state, "node-d")
    assert d.outcome is DependencyOutcome.PENDING
    assert d.unmet == ("node-b", "node-c")
    assert state.pending == ("node-d",)


def test_diamond_all_predecessors_completed_satisfies_sink() -> None:
    state = DependencyTracker().track(
        _diamond(),  # type: ignore[arg-type]
        SESSION,
        completed=("node-a", "node-b", "node-c"),
    )

    d = _node(state, "node-d")
    assert d.outcome is DependencyOutcome.SATISFIED
    assert d.unmet == ()
    assert state.satisfied == ("node-a", "node-b", "node-c", "node-d")
    assert state.pending == ()


def test_diamond_blocked_apex_poisons_entire_graph_below() -> None:
    state = DependencyTracker().track(
        _diamond(),  # type: ignore[arg-type]
        SESSION,
        blocked_sources=("node-a",),
    )

    assert _node(state, "node-a").outcome is DependencyOutcome.SATISFIED
    assert state.blocked == ("node-b", "node-c", "node-d")
    assert state.satisfied == ("node-a",)
    assert state.pending == ()


# --------------------------------------------------------------------------- #
# Identity, references, determinism                                            #
# --------------------------------------------------------------------------- #


def test_identity_and_session_reference() -> None:
    graph = make_graph((gnode("a"),))

    state = DependencyTracker().track(graph, SESSION)

    assert state.identity == f"deps-{SESSION}"
    assert state.session_ref.target_type == SESSION_TARGET_TYPE
    assert state.session_ref.target_type == "execution_session"
    assert state.session_ref.identifier == SESSION


def test_nodes_are_sorted_by_identifier() -> None:
    # Provide nodes out of sorted order; output must be deterministic.
    graph = make_graph((gnode("c"), gnode("a"), gnode("b")))

    state = DependencyTracker().track(graph, SESSION)

    node_ids = [n.node for n in state.nodes]
    assert node_ids == sorted(node_ids)
    assert node_ids == ["node-a", "node-b", "node-c"]


def test_dependencies_and_unmet_are_sorted() -> None:
    graph = make_graph(
        (gnode("z"), gnode("m"), gnode("a"), gnode("target")),
        (
            gedge("z", "target"),
            gedge("m", "target"),
            gedge("a", "target"),
        ),
    )

    state = DependencyTracker().track(graph, SESSION)

    target = _node(state, "node-target")
    assert target.dependencies == ("node-a", "node-m", "node-z")
    assert target.unmet == ("node-a", "node-m", "node-z")


def test_track_is_deterministic_across_calls() -> None:
    graph = _diamond()

    tracker = DependencyTracker()
    first = tracker.track(graph, SESSION, completed=("node-a",))  # type: ignore[arg-type]
    second = tracker.track(graph, SESSION, completed=("node-a",))  # type: ignore[arg-type]

    assert first == second


def test_completed_output_is_sorted() -> None:
    graph = make_graph(
        (gnode("a"), gnode("b"), gnode("c"), gnode("sink")),
        (gedge("a", "sink"), gedge("b", "sink"), gedge("c", "sink")),
    )

    state = DependencyTracker().track(
        graph,
        SESSION,
        completed=("node-c", "node-a", "node-b"),
    )

    assert state.completed == ("node-a", "node-b", "node-c")


def test_every_node_appears_in_exactly_one_outcome_bucket() -> None:
    graph = make_graph(
        (gnode("root"), gnode("ready"), gnode("waiting"), gnode("poisoned")),
        (
            gedge("root", "ready"),
            gedge("root", "waiting"),
            gedge("root", "poisoned"),
        ),
    )

    state = DependencyTracker().track(
        graph,
        SESSION,
        completed=("node-root",),
        blocked_sources=("node-poisoned",),
    )

    all_ids = {n.node for n in state.nodes}
    bucketed = list(state.satisfied) + list(state.pending) + list(state.blocked)
    assert sorted(bucketed) == sorted(all_ids)
    # No duplicates across buckets.
    assert len(bucketed) == len(set(bucketed))


# --------------------------------------------------------------------------- #
# Immutability                                                                 #
# --------------------------------------------------------------------------- #


def test_dependency_state_is_frozen() -> None:
    graph = make_graph((gnode("a"),))
    state = DependencyTracker().track(graph, SESSION)

    with pytest.raises(ValidationError):
        state.identity = "tampered"  # type: ignore[misc]


def test_node_dependency_is_frozen() -> None:
    graph = make_graph(
        (gnode("a"), gnode("b")),
        (gedge("a", "b"),),
    )
    state = DependencyTracker().track(graph, SESSION)
    node = _node(state, "node-b")

    with pytest.raises(ValidationError):
        node.outcome = DependencyOutcome.SATISFIED  # type: ignore[misc]
