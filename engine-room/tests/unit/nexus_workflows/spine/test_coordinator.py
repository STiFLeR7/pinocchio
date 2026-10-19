"""P13 unit — the constitutional pipeline drives every owner once, deterministically (F-1)."""

from __future__ import annotations

from nexus_infra import build_infrastructure
from nexus_workflows.spine import (
    ORDERED_STAGES,
    SpineStatus,
    build_constitutional_pipeline,
    spine_reference_request,
)
from nexus_workflows.spine.events import PIPELINE_PRODUCER

_ALL_STAGES = tuple(stage.value for stage in ORDERED_STAGES)


def _run(request=None):
    infra = build_infrastructure()
    ctx = build_constitutional_pipeline(infra)
    return infra, ctx.coordinator.run(request or spine_reference_request(run="r1"))


def test_pipeline_drives_every_constitutional_stage_exactly_once() -> None:
    _infra, run = _run()
    assert run.status is SpineStatus.COMPLETED
    assert run.succeeded
    assert run.executed_stages == _ALL_STAGES  # all nine owners, in order, once
    assert run.reconstructed_stages == ()  # a fresh run reconstructs nothing
    assert run.pipeline_session.stages_completed == _ALL_STAGES


def test_pipeline_reaches_evidence_backed_knowledge() -> None:
    _infra, run = _run()
    assert run.execution_outcomes and all(o == "completed" for o in run.execution_outcomes)
    assert all(d == "passed" for d in run.validation_decisions)  # F-3: clean handoff → corroborated
    assert run.recovery_decisions  # Recovery decided continuation
    assert run.reflection_ref is not None  # Reflection produced a report
    assert run.knowledge_item_ids  # Knowledge recorded (evidence-backed, INV-24)


def test_pipeline_is_deterministic() -> None:
    def once():
        _infra, run = _run()
        return (
            run.goal_ref.identifier,
            run.strategy_ref.identifier,
            run.plan_ref.identifier,
            run.execution_state.identity,
            run.validation_decisions,
            run.knowledge_item_ids,
            tuple((e.identifier, e.type) for e in run.events),
        )

    assert once() == once()  # identical Goal→Knowledge across independent runs, byte-for-byte


def test_pipeline_events_carry_the_single_pipeline_producer() -> None:
    infra, _ = _run()
    pipeline_events = [e for e in infra.event_store.read_all() if e.type.startswith("pipeline.")]
    assert pipeline_events  # the coordinator recorded its stage-coordination facts
    assert all(e.producer == PIPELINE_PRODUCER for e in pipeline_events)  # one owner (INV-02)
    # Exactly one stage_completed per constitutional stage (each owner invoked once).
    completed = [
        str(e.payload["stage"]) for e in pipeline_events if e.type == "pipeline.stage_completed"
    ]
    assert completed == list(_ALL_STAGES)


def test_failure_propagates_without_accepting_unvalidated_knowledge() -> None:
    _infra, run = _run(spine_reference_request(run="r1", fail=True))
    assert run.status is SpineStatus.COMPLETED  # the pipeline still reaches Knowledge
    assert not run.succeeded
    assert all(o == "failed" for o in run.execution_outcomes)  # execution reports failure
    assert all(d == "failed" for d in run.validation_decisions)  # Validation declines completion
    assert all(
        d == "retry" for d in run.recovery_decisions
    )  # Recovery decides continuation, bounded
    assert not run.knowledge_item_ids  # Failed validation cannot support accepted guidance.
    assert any(event.type == "knowledge.candidate_rejected" for event in run.events)
