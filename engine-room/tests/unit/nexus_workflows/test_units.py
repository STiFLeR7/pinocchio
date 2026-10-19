"""Unit tests for the pure nexus_workflows helpers: timeline, replay, request, reference."""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import KnowledgeType
from nexus_core.domain.event import Event
from nexus_workflows import (
    KNOWLEDGE_SUBJECT,
    TimelineRecorder,
    WorkflowTimeline,
    reconstruct,
    reference_request,
)
from nexus_workflows.timeline import StageRecord


def _event(identifier: str, producer: str, event_type: str, correlation: str = "cor") -> Event:
    return Event(
        identifier=identifier,
        type=event_type,
        version="1",
        timestamp="1970-01-01T00:00:00+00:00",
        producer=producer,
        correlation_identifier=correlation,
        execution_identifier=None,
        payload={},
        source=f"nexus_{producer}",
    )


# --- timeline --------------------------------------------------------------- #


def test_timeline_recorder_brackets_stages() -> None:
    log: list[Event] = []
    rec = TimelineRecorder(lambda: tuple(log), lambda: "1970-01-01T00:00:00+00:00")
    rec.enter("planning")
    log.append(_event("e1", "planning", "plan.created"))
    log.append(_event("e2", "planning", "planning.completed"))
    rec.complete((Reference(target_type="plan", identifier="p1"),))
    rec.enter("runtime", "runtime:node-a")
    log.append(_event("e3", "runtime", "runtime.ready"))
    rec.complete()

    timeline = rec.build()
    assert timeline.total_events == 3
    assert timeline.engines() == ("planning", "runtime")
    plan_stage = timeline.stages[0]
    assert plan_stage.label == "planning"
    assert plan_stage.emitted_count == 2
    assert plan_stage.emitted_event_types == ("plan.created", "planning.completed")
    assert plan_stage.correlation_identifier == "cor"
    assert timeline.stages[1].label == "runtime:node-a"


def test_workflow_timeline_aggregations() -> None:
    ref = Reference(target_type="plan", identifier="p1")
    stages = (
        StageRecord(0, "planning", "planning", "t", "t", 0, 1, ("plan.created",), (ref,), "cor"),
        StageRecord(1, "planning", "planning", "t", "t", 1, 2, ("planning.completed",), (), "cor"),
        StageRecord(2, "runtime", "runtime", "t", "t", 2, 3, ("runtime.ready",), (), "cor"),
    )
    timeline = WorkflowTimeline(stages=stages, total_events=3)
    assert timeline.engines() == ("planning", "planning", "runtime")
    assert timeline.distinct_engines() == ("planning", "runtime")
    assert timeline.artifacts() == (ref,)
    assert timeline.emitted_types() == ("plan.created", "planning.completed", "runtime.ready")


def test_empty_timeline_defaults() -> None:
    timeline = WorkflowTimeline()
    assert timeline.stages == ()
    assert timeline.distinct_engines() == ()
    assert timeline.artifacts() == ()


# --- replay ----------------------------------------------------------------- #


def test_reconstruct_groups_consecutive_producers() -> None:
    events = (
        _event("a1", "planning", "plan.created"),
        _event("a2", "planning", "planning.completed"),
        _event("b1", "runtime", "runtime.ready", correlation="cor2"),
        _event("c1", "planning", "plan.superseded"),  # producer returns -> a new stage
    )
    timeline = reconstruct(events)
    assert timeline.total_events == 4
    assert [s.producer for s in timeline.stages] == ["planning", "runtime", "planning"]
    assert timeline.stages[0].count == 2
    assert timeline.stages[1].correlation_identifier == "cor2"
    assert timeline.distinct_producers() == ("planning", "runtime")
    assert timeline.event_ids == ("a1", "a2", "b1", "c1")


def test_reconstruct_empty_stream() -> None:
    timeline = reconstruct(())
    assert timeline.total_events == 0
    assert timeline.stages == ()
    assert timeline.distinct_producers() == ()


# --- request / reference ---------------------------------------------------- #


def test_reference_request_shape() -> None:
    request = reference_request(run="r1")
    assert request.goal.identity == "goal-arch-r1"
    assert len(request.work_items) == 2
    assert all("code_generation" in w.capability_requirements for w in request.work_items)
    assert len(request.skills) == 2
    assert len(request.capabilities) == 1
    assert request.knowledge_subject == KNOWLEDGE_SUBJECT
    assert request.knowledge_kind is KnowledgeType.LESSON
    assert request.scope == "wf-goal-arch-r1"
    assert request.fail is False


def test_reference_request_distinguishes_runs_but_shares_subject() -> None:
    a = reference_request(run="r1")
    b = reference_request(run="r2", fail=True)
    assert a.goal.identity != b.goal.identity
    assert a.knowledge_subject == b.knowledge_subject
    assert b.fail is True
