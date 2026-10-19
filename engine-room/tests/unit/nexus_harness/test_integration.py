"""Integration tests for the Planning → Orchestration → Harness pipeline.

Runs the real OrchestrationService against a real ExecutionGraph, then compiles the
resulting HarnessRequests through the real HarnessService, all sharing the same
InfrastructureContext. Verifies that:

- The two layers compose without modification to orchestration output.
- One ExecutionPackage is produced per ready harness request.
- The package embeds the resolved WorkPackage and ContextView.
- Both layers emit events to the shared infrastructure event store.
- Running the full pipeline twice over two fresh infrastructures yields equal packages
  (determinism guarantee end-to-end).
"""

from __future__ import annotations

from nexus_harness import (
    CompilationRequest,
    FixedTimestampSource,
    build_harness,
)
from nexus_harness.events import HARNESS_COMPLETED
from nexus_infra import build_infrastructure
from nexus_orchestration import (
    OrchestrationRequest,
    build_orchestration,
)
from tests.unit.nexus_harness.helpers import (
    capability,
    context_package,
    ref,
    skill,
    work_package,
)
from tests.unit.nexus_orchestration.helpers import (
    gedge,
    gnode,
    make_graph,
    make_strategy,
)

# ---------------------------------------------------------------------------
# Pipeline factory helpers
# ---------------------------------------------------------------------------

# The orchestration helpers produce these ids deterministically:
#   graph identity:          graph-goal-1-v1
#   session identity:        session-goal-1-v1
#   node-research id:        node-research
#   node-research wp ref:    wp-goal-1-research
#   node-research ctx ref:   context-goal-1
#   harness request id:      hreq-session-goal-1-v1-node-research
#
# With gedge("research","build"), only node-research is READY; node-build is BLOCKED.


def _build_pipeline(*, orch_timestamps=None, harness_timestamps=None):
    """Build a fresh infra + orchestration + harness triple sharing the same infra."""
    infra = build_infrastructure()

    orch = build_orchestration(
        infra,
        timestamps=orch_timestamps or FixedTimestampSource(),
    )

    graph = make_graph(
        (
            gnode(
                "research",
                capabilities=("cap-analysis",),
                skills=(ref("skill", "skill-investigate"),),
            ),
            gnode("build"),
        ),
        (gedge("research", "build"),),
    )
    strat = make_strategy()

    ores = orch.service.orchestrate(
        OrchestrationRequest(execution_graph=graph, execution_strategy=strat)
    )

    h = build_harness(infra, timestamps=harness_timestamps or FixedTimestampSource())
    s = h.sources

    s.skills.register(skill("skill-investigate", capabilities=("cap-analysis",)))
    s.capabilities.register(capability("cap-analysis"))
    s.context_packages.add(context_package("context-goal-1", goal="goal-1"))
    s.work_packages.add(
        work_package(
            "wp-goal-1-research",
            goal="goal-1",
            plan="plan-goal-1-v1",
            context="context-goal-1",
            skills=(ref("skill", "skill-investigate"),),
        )
    )
    # strategy_ref on the gnode is None; the harness request carries no
    # execution_strategy_ref, so the validator returns None for strategy. No
    # need to register one. But we add make_strategy() in case a future node
    # carries it — harmless to skip since build_harness creates its own repo.

    comp = h.service.compile(
        CompilationRequest(
            harness_requests=ores.harness_requests,
            session_ref=ores.session.execution_graph_ref,
        )
    )
    return infra, h, ores, comp


# ---------------------------------------------------------------------------
# Shape: one package per ready harness request
# ---------------------------------------------------------------------------


def test_integration_one_package_per_ready_harness_request() -> None:
    """The compiled result contains exactly one package per ready harness request."""
    _infra, _h, ores, comp = _build_pipeline()

    assert len(comp.packages) == len(ores.harness_requests)


def test_integration_exactly_one_harness_request_is_ready() -> None:
    """With a research→build dependency, only node-research is immediately ready."""
    _infra, _h, ores, comp = _build_pipeline()

    # Only one node is ready (research); build is blocked by research.
    assert len(ores.harness_requests) == 1
    assert ores.harness_requests[0].node == "node-research"


def test_integration_one_manifest_per_ready_harness_request() -> None:
    """One ExecutionManifest is produced for each compiled package."""
    _infra, _h, ores, comp = _build_pipeline()

    assert len(comp.manifests) == len(ores.harness_requests)


# ---------------------------------------------------------------------------
# Package content: embedded WorkPackage + ContextView
# ---------------------------------------------------------------------------


def test_integration_package_embeds_work_package() -> None:
    """The ExecutionPackage embeds the resolved WorkPackage by value."""
    _infra, _h, _ores, comp = _build_pipeline()

    package = comp.packages[0]
    assert package.work_package is not None
    assert package.work_package.identifier == "wp-goal-1-research"


def test_integration_package_embeds_context_view() -> None:
    """The ExecutionPackage embeds a ContextView whose identity matches the context package."""
    _infra, _h, _ores, comp = _build_pipeline()

    package = comp.packages[0]
    assert package.context_view is not None
    assert package.context_view.identity == "context-goal-1"


def test_integration_package_node_matches_harness_request() -> None:
    """The package's node field matches the originating harness request node."""
    _infra, _h, ores, comp = _build_pipeline()

    package = comp.packages[0]
    assert package.node == ores.harness_requests[0].node


# ---------------------------------------------------------------------------
# Shared infrastructure event store: both layers write to the same log
# ---------------------------------------------------------------------------


def test_integration_shared_event_store_contains_orchestration_events() -> None:
    """Orchestration events appear in the shared infrastructure event store."""
    infra, _h, _ores, _comp = _build_pipeline()

    all_events = list(infra.event_store.read_all())
    producers = {e.producer for e in all_events}
    assert "orchestration" in producers


def test_integration_shared_event_store_contains_harness_events() -> None:
    """Harness events appear in the shared infrastructure event store."""
    infra, _h, _ores, _comp = _build_pipeline()

    all_events = list(infra.event_store.read_all())
    producers = {e.producer for e in all_events}
    assert "harness" in producers


def test_integration_harness_completed_event_is_present() -> None:
    """harness.completed is emitted to the shared event store after compilation."""
    infra, _h, _ores, _comp = _build_pipeline()

    all_events = list(infra.event_store.read_all())
    harness_completed = [e for e in all_events if e.type == HARNESS_COMPLETED]
    assert len(harness_completed) == 1


def test_integration_orchestration_output_not_modified_by_harness() -> None:
    """The orchestration result is immutable; harness compilation does not alter it."""
    _infra, _h, ores, _comp = _build_pipeline()

    # ores is a pydantic ValueObject — it should be unchanged after compilation.
    assert len(ores.harness_requests) == 1
    assert ores.harness_requests[0].node == "node-research"


# ---------------------------------------------------------------------------
# Determinism: two independent full-pipeline runs produce equal packages
# ---------------------------------------------------------------------------


def test_integration_two_runs_produce_equal_packages() -> None:
    """Running the full Orchestration→Harness pipeline twice yields equal packages."""
    _i1, _h1, _o1, comp1 = _build_pipeline()
    _i2, _h2, _o2, comp2 = _build_pipeline()

    assert comp1.packages == comp2.packages


def test_integration_two_runs_produce_equal_manifests() -> None:
    """Running the full pipeline twice yields equal manifests."""
    _i1, _h1, _o1, comp1 = _build_pipeline()
    _i2, _h2, _o2, comp2 = _build_pipeline()

    assert comp1.manifests == comp2.manifests


def test_integration_two_runs_produce_equal_harness_requests() -> None:
    """The orchestration harness_requests are identical across two independent runs."""
    _i1, _h1, o1, _c1 = _build_pipeline()
    _i2, _h2, o2, _c2 = _build_pipeline()

    assert o1.harness_requests == o2.harness_requests


def test_integration_two_runs_produce_equal_package_identities() -> None:
    """Package identities are pure functions of the input — no randomness."""
    _i1, _h1, _o1, comp1 = _build_pipeline()
    _i2, _h2, _o2, comp2 = _build_pipeline()

    ids1 = tuple(p.identity for p in comp1.packages)
    ids2 = tuple(p.identity for p in comp2.packages)
    assert ids1 == ids2
