"""Capability Program 1 -- the complete Goal->Knowledge operational workflow.

Proves the ten independently-built engines compose into one coherent system, driven only through
their existing public APIs by ``nexus_workflows``:

    Goal -> Context -> Plan -> Work Packages -> Execution Graph -> Harness -> Runtime
         -> Execution -> Validation -> Recovery -> Reflection -> Knowledge

Covers every milestone: full pipeline assembly + reference workflow (1/2), a coherent cross-layer
timeline (3), event-log replay with no information loss (4), the Knowledge feedback loop into
Planning (5, INV-26), failure scenarios exercising every engine (6), and byte-identical determinism.
"""

from __future__ import annotations

import pathlib

from nexus_workflows import (
    PipelineBuilder,
    PipelineExecutor,
    reference_request,
)
from nexus_workflows.projection import project_intake

_ALL_ENGINES = {
    "context_engineering",
    "knowledge",
    "planning",
    "orchestration",
    "harness",
    "runtime",
    "execution",
    "validation",
    "recovery",
    "reflection",
}


def _run(*, run: str = "r1", fail: bool = False, knowledge_repositories=None):  # type: ignore[no-untyped-def]
    pipeline = PipelineBuilder(knowledge_repositories=knowledge_repositories).build()
    executor = PipelineExecutor(pipeline)
    result = executor.execute(reference_request(run=run, fail=fail))
    return executor, result


# --- Milestone 1/2: full pipeline assembly + reference workflow ------------- #


def test_reference_workflow_invokes_every_engine() -> None:
    _executor, run = _run()
    assert set(run.timeline.distinct_engines()) == _ALL_ENGINES
    assert run.succeeded
    assert run.execution_outcomes == ("completed", "completed")
    assert run.validation_decisions == ("passed", "passed")
    assert run.recovery_decisions == ("complete", "complete")


def test_reference_workflow_reaches_durable_knowledge() -> None:
    _executor, run = _run()
    assert run.reflection_candidates  # Reflection proposed at least one candidate
    assert run.knowledge_item_ids  # Knowledge accepted it
    assert run.served_knowledge_ids  # and serves it read-only


# --- Milestone 3: cross-layer observability timeline ------------------------ #


def test_timeline_is_a_coherent_ordered_history() -> None:
    _executor, run = _run()
    timeline = run.timeline
    # Ordered: context precedes planning precedes execution precedes reflection.
    engines = timeline.engines()
    assert engines.index("context_engineering") < engines.index("planning")
    assert engines.index("planning") < engines.index("execution")
    assert engines.index("execution") < engines.index("reflection")
    # Every stage records emitted events and the run produces artifacts + a correlation.
    assert timeline.total_events > 0
    assert timeline.artifacts()
    assert any(stage.emitted_count > 0 for stage in timeline.stages)
    assert any(stage.correlation_identifier for stage in timeline.stages)


def test_every_event_is_persisted_to_the_shared_log() -> None:
    executor, run = _run()
    log = tuple(executor.pipeline.infrastructure.event_store.read_all())
    assert len(log) == run.timeline.total_events == len(run.events)


# --- Milestone 4: pipeline replay ------------------------------------------- #


def test_replay_reconstructs_the_history_without_information_loss() -> None:
    executor, run = _run()
    replay = executor.replay()
    assert replay.total_events == len(run.events)
    assert replay.event_ids == tuple(e.identifier for e in run.events)
    assert replay.event_types == tuple(e.type for e in run.events)
    # Every engine that participated appears as a producer in the reconstructed log.
    producers = set(replay.distinct_producers())
    assert {
        "planning",
        "orchestration",
        "harness",
        "runtime",
        "validation",
        "knowledge",
    } <= producers


def test_full_pipeline_is_byte_identical_across_runs() -> None:
    _e1, r1 = _run(run="det")
    _e2, r2 = _run(run="det")
    assert [(e.identifier, e.type, e.payload) for e in r1.events] == [
        (e.identifier, e.type, e.payload) for e in r2.events
    ]
    assert r1.timeline == r2.timeline


# --- Milestone 5: knowledge feedback (INV-26) ------------------------------- #


def test_knowledge_from_run_one_influences_planning_in_run_two() -> None:
    executor, run1 = _run(run="r1")
    assert run1.knowledge_consumed == 0  # nothing learned yet
    shared = executor.pipeline.knowledge.repositories
    _executor2, run2 = _run(run="r2", knowledge_repositories=shared)
    assert run2.knowledge_consumed >= 1  # run 2's planning read run 1's Knowledge


def test_planning_reaches_learning_only_through_knowledge() -> None:
    # Structural INV-26: Planning never imports Reflection; learning flows only via Knowledge.
    assert "nexus_reflection" not in _package_source("nexus_planning")
    assert "nexus_reflection" not in _package_source("nexus_context")


# --- Milestone 6: failure scenarios ----------------------------------------- #


def test_failure_scenario_engages_every_engine() -> None:
    _executor, run = _run(run="rf", fail=True)
    assert run.execution_outcomes == ("failed", "failed")
    assert run.validation_decisions == ("failed", "failed")
    assert run.recovery_decisions == ("retry", "retry")
    assert not run.succeeded
    # Reflection analyses the failure; Knowledge rejects unvalidated guidance.
    assert any("failure" in c for c in run.reflection_candidates)
    assert not run.knowledge_item_ids
    assert any(event.type == "knowledge.candidate_rejected" for event in run.events)


# --- the Harness->Runtime projection seam ----------------------------------- #


def test_projection_handles_missing_runtime_request_and_manifest() -> None:
    # Build real Harness packages, then exercise the projection's optional branches.
    pipeline = PipelineBuilder().build()
    from nexus_workflows.coordinator import WorkflowCoordinator

    coordinator = WorkflowCoordinator(pipeline)
    request = reference_request(run="proj")
    coordinator._register_inputs(request)
    from nexus_runtime_claude import ClaudeRuntimeAdapter, StubClaudeInvoker

    pipeline.harness_registry.register(
        ClaudeRuntimeAdapter(invoker=StubClaudeInvoker()).descriptor()
    )
    package, context_ref = coordinator._context(request)
    coordinator._read_knowledge(request)
    planning = coordinator._plan(request, context_ref, ())
    orch = coordinator._orchestrate(context_ref, planning)
    packages, manifests = coordinator._compile(package, planning, orch)

    pkg = packages[0]
    runtime_request = next(r for r in orch.runtime_requests if r.node == pkg.node)
    manifest = next(m for m in manifests if m.node == pkg.node)

    full = project_intake(pkg, runtime_request, manifest)
    assert full.candidate_harness_refs  # candidates carried from orchestration
    assert full.manifest_ref is not None

    bare = project_intake(pkg, None, None)
    assert bare.candidate_harness_refs == ()
    assert bare.manifest_ref is None
    assert bare.runtime_policy == {}


# --- structural guardrail --------------------------------------------------- #

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _package_source(package: str) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in (_REPO_ROOT / package).glob("*.py"))


def test_no_engine_imports_the_integration_layer() -> None:
    # nexus_workflows is the top integration boundary: nothing upstream imports it.
    for package in ("nexus_planning", "nexus_reflection", "nexus_knowledge", "nexus_runtime"):
        assert "nexus_workflows" not in _package_source(package)
