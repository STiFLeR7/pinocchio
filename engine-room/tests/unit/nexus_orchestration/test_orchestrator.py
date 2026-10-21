"""Unit tests for the Orchestration Service (Phase 5 — Orchestration).

Exercises the full pipeline end-to-end through a wired, deterministic environment
(:func:`orchestration_env` with a fixed timestamp source): bind session →
coordinate approvals → track dependencies → build queue → build harness requests →
build runtime requests, then persist and emit. Asserts the returned
:class:`OrchestrationResult`, the persisted state, the ordered event stream, the
deterministic identifiers/correlation, and the fail-fast failure path.
"""

from __future__ import annotations

import pytest

from nexus_core.contracts.enums import ApprovalTaxonomy
from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_orchestration.events import (
    APPROVAL_GRANTED,
    DEPENDENCY_SATISFIED,
    EXECUTION_QUEUED,
    EXECUTION_SESSION_CREATED,
    HARNESS_REQUEST_CREATED,
    ORCHESTRATION_COMPLETED,
    ORCHESTRATION_FAILED,
    RUNTIME_REQUEST_CREATED,
    WORK_PACKAGE_READY,
)
from nexus_orchestration.requests import OrchestrationResult
from nexus_orchestration.validators import CyclicDependencyError, UnknownNodeError
from nexus_orchestration.vocabulary import QueueItemState
from tests.unit.nexus_orchestration.helpers import (
    OrchestrationEnv,
    gedge,
    gnode,
    make_graph,
    make_request,
    make_strategy,
    orchestration_env,
)


def _pipeline_graph(*, approval: bool = True) -> ExecutionGraph:
    """research (root, carries a capability) -> build (approval gate) -> test."""
    return make_graph(
        (
            gnode("research", capabilities=("code-search",)),
            gnode("build", approval=approval),
            gnode("test"),
        ),
        (gedge("research", "build"), gedge("build", "test")),
    )


def _event_types(env: OrchestrationEnv) -> list[str]:
    return [event.type for event in env.infrastructure.event_store.read_all()]


# --------------------------------------------------------------------------- #
# Result + persistence                                                          #
# --------------------------------------------------------------------------- #


def test_orchestrate_returns_an_orchestration_result() -> None:
    env = orchestration_env()
    graph = _pipeline_graph()

    result = env.orchestration.service.orchestrate(make_request(graph, make_strategy()))

    assert isinstance(result, OrchestrationResult)
    assert result.session.node_count == 3


def test_orchestrate_persists_every_state_and_request() -> None:
    env = orchestration_env()
    graph = _pipeline_graph()
    repos = env.orchestration.repositories

    result = env.orchestration.service.orchestrate(make_request(graph, make_strategy()))

    assert repos.sessions.get(result.session.identity) is not None
    assert repos.dependency_states.get(result.dependency_state.identity) is not None
    assert repos.queue_states.get(result.queue_state.identity) is not None
    assert repos.approval_states.get(result.approval_state.identity) is not None
    for harness_request in result.harness_requests:
        assert repos.harness_requests.get(harness_request.identity) is not None
    for runtime_request in result.runtime_requests:
        assert repos.runtime_requests.get(runtime_request.identity) is not None


# --------------------------------------------------------------------------- #
# Event emission — order and content                                            #
# --------------------------------------------------------------------------- #


def test_first_event_is_session_created_and_last_is_completed() -> None:
    env = orchestration_env()
    graph = _pipeline_graph()

    env.orchestration.service.orchestrate(make_request(graph, make_strategy()))

    types = _event_types(env)
    assert types[0] == EXECUTION_SESSION_CREATED
    assert types[-1] == ORCHESTRATION_COMPLETED


def test_full_event_order_matches_the_pipeline() -> None:
    env = orchestration_env()
    # AUTOMATIC approval grants the build gate; empty progress leaves only the
    # root ready, so build/test are blocked and never reach the ready stages.
    graph = _pipeline_graph()

    env.orchestration.service.orchestrate(make_request(graph, make_strategy()))

    # session_created
    # → approval per gate (build, GRANTED)
    # → dependency_satisfied per satisfied node (research)
    # → work_package_ready + execution_queued per ready node (research)
    # → harness_request_created per hreq (research)
    # → runtime_request_created per rreq (research)
    # → completed
    assert _event_types(env) == [
        EXECUTION_SESSION_CREATED,
        APPROVAL_GRANTED,
        DEPENDENCY_SATISFIED,
        WORK_PACKAGE_READY,
        EXECUTION_QUEUED,
        HARNESS_REQUEST_CREATED,
        RUNTIME_REQUEST_CREATED,
        ORCHESTRATION_COMPLETED,
    ]


def test_event_identifiers_follow_the_scheme_and_are_unique() -> None:
    env = orchestration_env()
    graph = _pipeline_graph()

    result = env.orchestration.service.orchestrate(make_request(graph, make_strategy()))
    session = result.session.identity

    identifiers = [event.identifier for event in env.infrastructure.event_store.read_all()]
    assert len(identifiers) == len(set(identifiers))  # unique
    for identifier in identifiers:
        assert identifier.startswith(f"evt-{session}-")
        # evt-{session}-{kind}-{seq:04d}: the trailing field is a 4-digit sequence.
        sequence = identifier.rsplit("-", 1)[-1]
        assert len(sequence) == 4
        assert sequence.isdigit()


def test_correlation_defaults_to_goal_when_unset() -> None:
    env = orchestration_env()
    graph = _pipeline_graph()

    # No request/strategy/graph correlation → falls back to f"cor-{goal}".
    env.orchestration.service.orchestrate(make_request(graph, make_strategy()))

    correlations = {
        event.correlation_identifier for event in env.infrastructure.event_store.read_all()
    }
    assert correlations == {"cor-goal-1"}


def test_correlation_prefers_the_request_identifier() -> None:
    env = orchestration_env()
    graph = _pipeline_graph()

    env.orchestration.service.orchestrate(
        make_request(
            graph, make_strategy(correlation="cor-strategy"), correlation_identifier="cor-explicit"
        )
    )

    correlations = {
        event.correlation_identifier for event in env.infrastructure.event_store.read_all()
    }
    assert correlations == {"cor-explicit"}


# --------------------------------------------------------------------------- #
# Readiness                                                                      #
# --------------------------------------------------------------------------- #


def test_only_the_root_is_ready_with_empty_progress() -> None:
    env = orchestration_env()
    graph = _pipeline_graph()

    result = env.orchestration.service.orchestrate(make_request(graph, make_strategy()))

    assert result.queue_state.ready == ("node-research",)
    assert "node-build" in result.queue_state.blocked
    assert "node-test" in result.queue_state.blocked
    # Ready-only requests: exactly one harness request and one runtime request.
    assert len(result.harness_requests) == 1
    assert len(result.runtime_requests) == 1
    assert result.harness_requests[0].node == "node-research"
    assert result.runtime_requests[0].node == "node-research"


def test_completed_root_leaves_gated_build_waiting() -> None:
    env = orchestration_env()
    # A human-review gate stays REQUESTED, so a satisfied-but-gated node WAITS.
    graph = _pipeline_graph(approval=True)
    strategy = make_strategy(approval_policy=ApprovalTaxonomy.HUMAN_REVIEW)

    result = env.orchestration.service.orchestrate(
        make_request(graph, strategy, completed_nodes=("node-research",))
    )

    queue = result.queue_state
    assert "node-build" in queue.waiting
    assert "node-build" not in queue.ready
    assert "node-test" in queue.blocked


def test_completed_root_makes_ungated_build_ready() -> None:
    env = orchestration_env()
    # No approval gate on build: once research completes, build becomes READY.
    graph = _pipeline_graph(approval=False)

    result = env.orchestration.service.orchestrate(
        make_request(graph, make_strategy(), completed_nodes=("node-research",))
    )

    queue = result.queue_state
    assert "node-build" in queue.ready
    assert "node-research" in queue.completed
    assert "node-test" in queue.blocked
    # build's queue item carries the READY state.
    states = {item.node: item.state for item in queue.items}
    assert states["node-build"] is QueueItemState.READY


# --------------------------------------------------------------------------- #
# Failure path                                                                  #
# --------------------------------------------------------------------------- #


def test_cycle_raises_and_emits_exactly_one_failed_event() -> None:
    env = orchestration_env()
    graph = make_graph(
        (gnode("a"), gnode("b")),
        (gedge("a", "b"), gedge("b", "a")),
    )

    with pytest.raises(CyclicDependencyError):
        env.orchestration.service.orchestrate(make_request(graph, make_strategy()))

    types = _event_types(env)
    assert types == [ORCHESTRATION_FAILED]


def test_unknown_node_raises_and_emits_only_a_failed_event() -> None:
    env = orchestration_env()
    graph = _pipeline_graph()

    with pytest.raises(UnknownNodeError):
        env.orchestration.service.orchestrate(
            make_request(graph, make_strategy(), completed_nodes=("node-ghost",))
        )

    types = _event_types(env)
    assert types == [ORCHESTRATION_FAILED]
    # No success events leaked into the log.
    assert EXECUTION_SESSION_CREATED not in types
    assert ORCHESTRATION_COMPLETED not in types


# --------------------------------------------------------------------------- #
# Context reference derivation                                                  #
# --------------------------------------------------------------------------- #


def test_context_ref_derived_from_a_node_when_request_omits_it() -> None:
    env = orchestration_env()
    # gnode defaults required_context_ref to "context-goal-1"; the request omits
    # context_ref, so the session's context is derived from a node.
    graph = _pipeline_graph()

    result = env.orchestration.service.orchestrate(make_request(graph, make_strategy()))

    assert result.session.context_ref.identifier == "context-goal-1"
    assert result.session.context_ref.target_type == "context_package"
