"""Unit tests for the Harness Request Builder (Step 5).

The builder turns every *ready* node the execution queue reports into one
immutable, runtime-independent Harness Request. These tests cover the
one-request-per-ready-node contract and ordering, the deterministic identity,
the field derivation (work package, strategy, coordination, correlation,
session reference), the required-skill/required-capability split, the
context-reference fallback to the session, immutability, and determinism.

Real orchestration objects are used throughout (no mocks): a graph is built
directly, then bound into a session, dependency state, approval state, and a
queue state, so the queue's notion of "ready" drives the builder exactly as it
does in production.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Reference
from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_orchestration import (
    ApprovalCoordinator,
    DependencyTracker,
    ExecutionQueueBuilder,
    ExecutionSession,
    ExecutionSessionBuilder,
    HarnessRequest,
    HarnessRequestBuilder,
    QueueState,
)
from tests.unit.nexus_orchestration.helpers import (
    gedge,
    gnode,
    make_graph,
    make_strategy,
)

CONTEXT_REF = Reference(target_type="context_package", identifier="ctx-session")
CORRELATION = "cor-x"


def _session(graph: ExecutionGraph) -> ExecutionSession:
    """Bind a graph + strategy into a deterministic Execution Session."""
    strategy = make_strategy()
    return ExecutionSessionBuilder().build(
        graph,
        strategy,
        context_ref=CONTEXT_REF,
        correlation_identifier=CORRELATION,
    )


def _queue_state(graph: ExecutionGraph, session: ExecutionSession) -> QueueState:
    """Build the queue state for a graph with empty progress (only roots ready)."""
    deps = DependencyTracker().track(graph, session.identity)
    approvals = ApprovalCoordinator().coordinate(graph, make_strategy(), session.identity)
    return ExecutionQueueBuilder().build(graph, deps, approvals, session.identity)


def _two_node_graph() -> ExecutionGraph:
    """A graph where ``research`` is a root and ``build`` depends on it."""
    return make_graph(
        (gnode("research"), gnode("build")),
        (gedge("research", "build"),),
    )


def _build(graph: ExecutionGraph) -> tuple[HarnessRequest, ...]:
    """Run the full pipeline and return the harness requests for ``graph``."""
    session = _session(graph)
    queue_state = _queue_state(graph, session)
    return HarnessRequestBuilder().build(
        session,
        graph,
        queue_state,
        correlation_identifier=CORRELATION,
    )


def test_one_request_per_ready_node_in_order() -> None:
    graph = _two_node_graph()
    session = _session(graph)
    queue_state = _queue_state(graph, session)

    # With empty progress, only the root (research) is ready.
    assert queue_state.ready == ("node-research",)

    requests = HarnessRequestBuilder().build(
        session, graph, queue_state, correlation_identifier=CORRELATION
    )

    assert tuple(request.node for request in requests) == queue_state.ready


def test_non_ready_nodes_produce_no_request() -> None:
    graph = _two_node_graph()
    requests = _build(graph)

    nodes = {request.node for request in requests}
    # ``build`` is waiting on ``research`` and therefore not yet ready.
    assert "node-build" not in nodes
    assert nodes == {"node-research"}


def test_ready_order_is_preserved_for_multiple_roots() -> None:
    # Two independent roots: both ready, queue orders them deterministically.
    graph = make_graph((gnode("alpha"), gnode("beta")))
    session = _session(graph)
    queue_state = _queue_state(graph, session)

    requests = HarnessRequestBuilder().build(
        session, graph, queue_state, correlation_identifier=CORRELATION
    )

    assert tuple(request.node for request in requests) == queue_state.ready
    assert tuple(request.node for request in requests) == ("node-alpha", "node-beta")


def test_identity_is_harness_request_id() -> None:
    graph = _two_node_graph()
    session = _session(graph)
    requests = _build(graph)

    assert requests[0].identity == f"hreq-{session.identity}-node-research"


def test_request_fields_derive_from_node_and_session() -> None:
    graph = _two_node_graph()
    session = _session(graph)
    requests = _build(graph)
    request = requests[0]
    node = next(n for n in graph.nodes if n.identifier == "node-research")

    assert request.node == node.identifier
    assert request.work_package_ref == node.work_package_ref
    assert request.execution_strategy_ref == node.execution_strategy_ref
    assert request.coordination == session.coordination
    assert request.correlation is not None
    assert request.correlation.correlation_identifier == CORRELATION


def test_session_ref_target_type_and_identifier() -> None:
    graph = _two_node_graph()
    session = _session(graph)
    requests = _build(graph)

    assert requests[0].session_ref.target_type == "execution_session"
    assert requests[0].session_ref.identifier == session.identity


def test_required_skill_and_capability_refs_are_split() -> None:
    skill = Reference(target_type="skill", identifier="s1")
    graph = make_graph(
        (gnode("research", capabilities=("cap.analysis",), skills=(skill,)),),
    )
    requests = _build(graph)
    request = requests[0]

    # Capability references go to required_capability_refs.
    assert request.required_capability_refs == (
        Reference(target_type="capability", identifier="cap.analysis"),
    )
    # Everything else (the skill) goes to required_skill_refs.
    assert request.required_skill_refs == (skill,)


def test_capability_refs_excluded_from_skill_refs() -> None:
    skill = Reference(target_type="skill", identifier="s1")
    graph = make_graph(
        (gnode("research", capabilities=("cap.analysis",), skills=(skill,)),),
    )
    request = _build(graph)[0]

    assert all(ref.target_type != "capability" for ref in request.required_skill_refs)
    assert all(ref.target_type == "capability" for ref in request.required_capability_refs)


def test_context_ref_uses_node_required_context_when_present() -> None:
    graph = make_graph((gnode("research", context="ctx-node"),))
    request = _build(graph)[0]

    assert request.context_ref == Reference(target_type="context_package", identifier="ctx-node")


def test_context_ref_falls_back_to_session_when_node_has_none() -> None:
    graph = make_graph((gnode("research", context=None),))
    session = _session(graph)
    request = _build(graph)[0]

    assert request.context_ref == session.context_ref
    assert request.context_ref == CONTEXT_REF


def test_harness_request_is_frozen() -> None:
    request = _build(_two_node_graph())[0]
    with pytest.raises(ValidationError):
        request.identity = "mutated"  # type: ignore[misc]


def test_build_is_deterministic() -> None:
    first = _build(_two_node_graph())
    second = _build(_two_node_graph())
    assert first == second
