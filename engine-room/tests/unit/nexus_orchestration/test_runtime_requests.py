"""Unit tests for the Runtime Request Builder (Step 6).

The builder derives one immutable Runtime Request per Harness Request: the runtime
*requirements* (the strategy's capability-based ``runtime_policy`` and the request's
required capabilities) and, when a ``HarnessRegistry`` is injected, the harness
**candidates** that advertise those capabilities — candidates only, never a
selection (INV-37). These tests cover the one-request-per-harness-request contract
and ordering, the deterministic identity, the field derivation (runtime policy,
coordination, capabilities, harness-request reference, work package), the candidate
discovery (none without a registry; sorted candidates with one), immutability, and
determinism.

Real orchestration objects are used throughout (no mocks): a graph is bound into a
session, dependency/approval/queue states, and a tuple of harness requests, which
then feed the runtime builder exactly as in production.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Reference
from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_orchestration import (
    ApprovalCoordinator,
    DependencyTracker,
    ExecutionQueueBuilder,
    ExecutionSession,
    ExecutionSessionBuilder,
    HarnessRequest,
    HarnessRequestBuilder,
    InMemoryHarnessRegistry,
    RuntimeRequest,
    RuntimeRequestBuilder,
)
from tests.unit.nexus_orchestration.helpers import (
    gnode,
    harness,
    make_graph,
    make_strategy,
)

CONTEXT_REF = Reference(target_type="context_package", identifier="ctx-session")
CORRELATION = "cor-x"
RUNTIME_POLICY = {"isolation": "container", "max_parallel": 2}


def _strategy() -> ExecutionStrategy:
    """A strategy carrying a non-trivial runtime policy to assert pass-through."""
    return make_strategy(runtime_policy=RUNTIME_POLICY)


def _session(graph: ExecutionGraph, strategy: ExecutionStrategy) -> ExecutionSession:
    """Bind a graph + strategy into a deterministic Execution Session."""
    return ExecutionSessionBuilder().build(
        graph,
        strategy,
        context_ref=CONTEXT_REF,
        correlation_identifier=CORRELATION,
    )


def _harness_requests(
    graph: ExecutionGraph, session: ExecutionSession, strategy: ExecutionStrategy
) -> tuple[HarnessRequest, ...]:
    """Build the harness requests (only roots are ready with empty progress)."""
    deps = DependencyTracker().track(graph, session.identity)
    approvals = ApprovalCoordinator().coordinate(graph, strategy, session.identity)
    queue_state = ExecutionQueueBuilder().build(graph, deps, approvals, session.identity)
    return HarnessRequestBuilder().build(
        session, graph, queue_state, correlation_identifier=CORRELATION
    )


def _analysis_graph() -> ExecutionGraph:
    """A single ready root advertising the ``cap.analysis`` capability."""
    return make_graph((gnode("research", capabilities=("cap.analysis",)),))


def _run(
    graph: ExecutionGraph,
    *,
    registry: InMemoryHarnessRegistry | None = None,
) -> tuple[RuntimeRequest, ...]:
    """Run the full pipeline and return runtime requests for ``graph``."""
    strategy = _strategy()
    session = _session(graph, strategy)
    harness_requests = _harness_requests(graph, session, strategy)
    return RuntimeRequestBuilder(registry).build(
        session, strategy, harness_requests, correlation_identifier=CORRELATION
    )


def test_one_request_per_harness_request_in_order() -> None:
    graph = make_graph((gnode("alpha"), gnode("beta")))
    strategy = _strategy()
    session = _session(graph, strategy)
    harness_requests = _harness_requests(graph, session, strategy)

    runtime_requests = RuntimeRequestBuilder().build(
        session, strategy, harness_requests, correlation_identifier=CORRELATION
    )

    assert len(runtime_requests) == len(harness_requests)
    assert tuple(r.node for r in runtime_requests) == tuple(h.node for h in harness_requests)


def test_identity_is_runtime_request_id() -> None:
    graph = _analysis_graph()
    strategy = _strategy()
    session = _session(graph, strategy)
    runtime_requests = _run(graph)

    assert runtime_requests[0].identity == f"rreq-{session.identity}-node-research"


def test_runtime_policy_comes_from_strategy() -> None:
    runtime_requests = _run(_analysis_graph())
    assert runtime_requests[0].runtime_policy == RUNTIME_POLICY


def test_coordination_comes_from_session() -> None:
    graph = _analysis_graph()
    strategy = _strategy()
    session = _session(graph, strategy)
    runtime_requests = _run(graph)

    assert runtime_requests[0].coordination == session.coordination


def test_required_capability_refs_carried_from_harness_request() -> None:
    graph = _analysis_graph()
    strategy = _strategy()
    session = _session(graph, strategy)
    harness_requests = _harness_requests(graph, session, strategy)

    runtime_requests = RuntimeRequestBuilder().build(
        session, strategy, harness_requests, correlation_identifier=CORRELATION
    )

    assert (
        runtime_requests[0].required_capability_refs == harness_requests[0].required_capability_refs
    )
    assert runtime_requests[0].required_capability_refs == (
        Reference(target_type="capability", identifier="cap.analysis"),
    )


def test_harness_request_ref_target_type_and_identifier() -> None:
    graph = _analysis_graph()
    strategy = _strategy()
    session = _session(graph, strategy)
    harness_requests = _harness_requests(graph, session, strategy)

    runtime_requests = RuntimeRequestBuilder().build(
        session, strategy, harness_requests, correlation_identifier=CORRELATION
    )

    assert runtime_requests[0].harness_request_ref.target_type == "harness_request"
    assert runtime_requests[0].harness_request_ref.identifier == harness_requests[0].identity


def test_work_package_ref_carried_from_harness_request() -> None:
    graph = _analysis_graph()
    strategy = _strategy()
    session = _session(graph, strategy)
    harness_requests = _harness_requests(graph, session, strategy)

    runtime_requests = RuntimeRequestBuilder().build(
        session, strategy, harness_requests, correlation_identifier=CORRELATION
    )

    assert runtime_requests[0].work_package_ref == harness_requests[0].work_package_ref


def test_no_registry_yields_no_candidates() -> None:
    runtime_requests = _run(_analysis_graph(), registry=None)
    assert runtime_requests[0].candidate_harness_refs == ()


def test_registry_lists_matching_candidates_sorted() -> None:
    registry = InMemoryHarnessRegistry()
    # Registered out of order to prove the output is sorted, not insertion-ordered.
    registry.register(harness("harness-z", capabilities=("cap.analysis",)))
    registry.register(harness("harness-a", capabilities=("cap.analysis",)))

    runtime_requests = _run(_analysis_graph(), registry=registry)

    assert runtime_requests[0].candidate_harness_refs == (
        Reference(target_type="harness", identifier="harness-a"),
        Reference(target_type="harness", identifier="harness-z"),
    )


def test_registry_excludes_harness_advertising_other_capability() -> None:
    registry = InMemoryHarnessRegistry()
    registry.register(harness("harness-match", capabilities=("cap.analysis",)))
    registry.register(harness("harness-other", capabilities=("cap.other",)))

    runtime_requests = _run(_analysis_graph(), registry=registry)

    assert runtime_requests[0].candidate_harness_refs == (
        Reference(target_type="harness", identifier="harness-match"),
    )


def test_candidate_refs_target_type_is_harness() -> None:
    registry = InMemoryHarnessRegistry()
    registry.register(harness("harness-a", capabilities=("cap.analysis",)))

    runtime_requests = _run(_analysis_graph(), registry=registry)

    assert all(ref.target_type == "harness" for ref in runtime_requests[0].candidate_harness_refs)


def test_runtime_request_is_frozen() -> None:
    runtime_requests = _run(_analysis_graph())
    with pytest.raises(ValidationError):
        runtime_requests[0].identity = "mutated"  # type: ignore[misc]


def test_build_is_deterministic() -> None:
    registry_first = InMemoryHarnessRegistry()
    registry_first.register(harness("harness-a", capabilities=("cap.analysis",)))
    registry_second = InMemoryHarnessRegistry()
    registry_second.register(harness("harness-a", capabilities=("cap.analysis",)))

    first = _run(_analysis_graph(), registry=registry_first)
    second = _run(_analysis_graph(), registry=registry_second)
    assert first == second
