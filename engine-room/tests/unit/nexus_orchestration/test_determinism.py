"""Determinism proofs for Nexus Orchestration — the headline Phase 5 guarantee.

The core invariant of Phase 5 is that orchestration is a *pure, reproducible*
function of its inputs: given an identical Goal / Context Package / Plan /
Execution Graph / Execution Strategy (plus identical orchestration progress) the
Orchestrator always produces an identical Execution Session, dependency state,
queue state, approval state, harness requests, runtime requests, *and* event
stream. There is no AI and no randomness; the one captured-as-data value (the
event timestamp) is injected via ``FixedTimestampSource`` so it stays pinned.

These tests prove that guarantee end to end by orchestrating the *same* request
in two completely independent environments (separate infrastructure, separate
repositories, separate emitters) and asserting byte-identical outputs — across a
trivial graph, a rich diamond graph with an approval gate / capability /
registered harness / progress, and graphs whose nodes and edges are supplied in
different construction orders (the builders sort internally).

Every run uses a *fresh* :func:`orchestration_env`: the service appends events
and adds to repositories, so re-running in the same environment would duplicate
state. A fresh environment per run isolates each orchestration cycle.
"""

from __future__ import annotations

from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_orchestration.events import ORCHESTRATION_PRODUCER
from nexus_orchestration.requests import OrchestrationRequest, OrchestrationResult
from tests.unit.nexus_orchestration.helpers import (
    OrchestrationEnv,
    gedge,
    gnode,
    harness,
    make_graph,
    make_request,
    make_strategy,
    orchestration_env,
)

# --------------------------------------------------------------------------- #
# Helpers.                                                                     #
# --------------------------------------------------------------------------- #


def _orchestration_events(env: OrchestrationEnv) -> list[tuple[str, str]]:
    """The ``(identifier, type)`` stream this env's orchestration emitted, in order."""
    return [
        (event.identifier, event.type)
        for event in env.infrastructure.event_store.read_all()
        if event.producer == ORCHESTRATION_PRODUCER
    ]


def _assert_results_equal(result1: OrchestrationResult, result2: OrchestrationResult) -> None:
    """Assert two orchestration results are byte-identical, field by field."""
    assert result1.session == result2.session
    assert result1.dependency_state == result2.dependency_state
    assert result1.queue_state == result2.queue_state
    assert result1.approval_state == result2.approval_state
    assert result1.harness_requests == result2.harness_requests
    assert result1.runtime_requests == result2.runtime_requests
    # And, because frozen pydantic models compare by value, the whole thing.
    assert result1 == result2


# --------------------------------------------------------------------------- #
# 1. Two fresh environments orchestrating the SAME request are identical.      #
# --------------------------------------------------------------------------- #


def test_two_fresh_envs_produce_identical_result() -> None:
    graph = make_graph((gnode("research"), gnode("build")), (gedge("research", "build"),))
    strategy = make_strategy()
    request = make_request(graph, strategy)

    env1 = orchestration_env()
    env2 = orchestration_env()

    result1 = env1.orchestration.service.orchestrate(request)
    result2 = env2.orchestration.service.orchestrate(request)

    _assert_results_equal(result1, result2)


def test_two_fresh_envs_emit_identical_event_streams() -> None:
    graph = make_graph((gnode("research"), gnode("build")), (gedge("research", "build"),))
    strategy = make_strategy()
    request = make_request(graph, strategy)

    env1 = orchestration_env()
    env2 = orchestration_env()

    env1.orchestration.service.orchestrate(request)
    env2.orchestration.service.orchestrate(request)

    stream1 = _orchestration_events(env1)
    stream2 = _orchestration_events(env2)

    assert stream1 == stream2
    # Sanity: a non-trivial, internally unique event stream was actually emitted.
    assert stream1
    identifiers = [identifier for identifier, _ in stream1]
    assert len(identifiers) == len(set(identifiers))


# --------------------------------------------------------------------------- #
# 2. Determinism across a rich graph (diamond + approval + capability +        #
#    registered harness + non-empty progress).                                #
# --------------------------------------------------------------------------- #


def _rich_graph() -> ExecutionGraph:
    """A diamond (research → {analysis, docs} → review) with an approval gate.

    ``analysis`` carries a capability (so candidate harnesses can be discovered)
    and ``review`` is an approval gate.
    """
    nodes = (
        gnode("research"),
        gnode("analysis", capabilities=("cap.analysis",)),
        gnode("docs"),
        gnode("review", approval=True),
    )
    edges = (
        gedge("research", "analysis"),
        gedge("research", "docs"),
        gedge("analysis", "review"),
        gedge("docs", "review"),
    )
    return make_graph(nodes, edges, approval_gates=("node-review",))


def _rich_request() -> OrchestrationRequest:
    """The rich graph plus non-empty progress (a completed node, an approved gate)."""
    graph = _rich_graph()
    strategy = make_strategy()
    return make_request(
        graph,
        strategy,
        completed_nodes=("node-research",),
        approved_gates=("node-review",),
    )


def test_rich_graph_is_deterministic_across_fresh_envs() -> None:
    request = _rich_request()
    descriptor = harness("harness-analysis", capabilities=("cap.analysis",))

    env1 = orchestration_env(descriptor)
    env2 = orchestration_env(harness("harness-analysis", capabilities=("cap.analysis",)))

    result1 = env1.orchestration.service.orchestrate(request)
    result2 = env2.orchestration.service.orchestrate(request)

    _assert_results_equal(result1, result2)


def test_rich_graph_emits_identical_event_streams() -> None:
    request = _rich_request()

    env1 = orchestration_env(harness("harness-analysis", capabilities=("cap.analysis",)))
    env2 = orchestration_env(harness("harness-analysis", capabilities=("cap.analysis",)))

    env1.orchestration.service.orchestrate(request)
    env2.orchestration.service.orchestrate(request)

    assert _orchestration_events(env1) == _orchestration_events(env2)


def test_rich_graph_populates_identical_candidate_harness_refs() -> None:
    request = _rich_request()

    env1 = orchestration_env(harness("harness-analysis", capabilities=("cap.analysis",)))
    env2 = orchestration_env(harness("harness-analysis", capabilities=("cap.analysis",)))

    result1 = env1.orchestration.service.orchestrate(request)
    result2 = env2.orchestration.service.orchestrate(request)

    # The registered harness advertises cap.analysis, so the runtime request for
    # the node requiring that capability has a populated candidate list.
    candidates1 = {
        runtime.node: runtime.candidate_harness_refs for runtime in result1.runtime_requests
    }
    candidates2 = {
        runtime.node: runtime.candidate_harness_refs for runtime in result2.runtime_requests
    }

    populated = [refs for refs in candidates1.values() if refs]
    assert populated, "expected at least one runtime request with candidate harnesses"
    assert any(any(ref.identifier == "harness-analysis" for ref in refs) for refs in populated)
    # Candidates are byte-identical across the two independent runs.
    assert candidates1 == candidates2


# --------------------------------------------------------------------------- #
# 3. Order independence of node/edge construction.                            #
# --------------------------------------------------------------------------- #


def test_node_and_edge_construction_order_does_not_change_result() -> None:
    nodes_a = (
        gnode("research"),
        gnode("analysis"),
        gnode("docs"),
        gnode("review"),
    )
    edges_a = (
        gedge("research", "analysis"),
        gedge("research", "docs"),
        gedge("analysis", "review"),
        gedge("docs", "review"),
    )
    # The same graph, declared with nodes and edges in a different order.
    nodes_b = (
        gnode("review"),
        gnode("docs"),
        gnode("analysis"),
        gnode("research"),
    )
    edges_b = (
        gedge("docs", "review"),
        gedge("analysis", "review"),
        gedge("research", "docs"),
        gedge("research", "analysis"),
    )

    graph_a = make_graph(nodes_a, edges_a)
    graph_b = make_graph(nodes_b, edges_b)
    strategy = make_strategy()

    env_a = orchestration_env()
    env_b = orchestration_env()

    result_a = env_a.orchestration.service.orchestrate(make_request(graph_a, strategy))
    result_b = env_b.orchestration.service.orchestrate(make_request(graph_b, strategy))

    _assert_results_equal(result_a, result_b)


def test_construction_order_yields_identical_event_streams() -> None:
    strategy = make_strategy()

    graph_a = make_graph(
        (gnode("alpha"), gnode("beta")),
        (gedge("alpha", "beta"),),
    )
    graph_b = make_graph(
        (gnode("beta"), gnode("alpha")),
        (gedge("alpha", "beta"),),
    )

    env_a = orchestration_env()
    env_b = orchestration_env()

    env_a.orchestration.service.orchestrate(make_request(graph_a, strategy))
    env_b.orchestration.service.orchestrate(make_request(graph_b, strategy))

    assert _orchestration_events(env_a) == _orchestration_events(env_b)
