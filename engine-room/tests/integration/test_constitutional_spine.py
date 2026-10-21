"""P13 — Constitutional Spine Fusion & Durable Pipeline (integration).

End-to-end proof that the single :class:`ConstitutionalPipeline` runs the complete constitutional spine
— Intent → Engineering → Context → Planning → Execution Actuation → Validation → Recovery → Reflection
→ Knowledge — as **one** deterministic, durable, restartable driver over a shared log, with real engines
throughout (no mocked stages). Closes the three P12 findings: F-1 (one Goal→Knowledge driver, no
competing path), F-2 (durable restart from the last completed constitutional boundary), F-3 (Execution
Actuation hands off cleanly to Validation via the frozen ExecutionResult contract).
"""

from __future__ import annotations

from nexus_execution.actuation import ActuationControl
from nexus_infra import build_durable_infrastructure, build_infrastructure
from nexus_workflows.spine import (
    ORDERED_STAGES,
    SpineControl,
    SpineStage,
    SpineStatus,
    build_constitutional_pipeline,
    reconstruct_pipeline_session,
    spine_reference_request,
)
from nexus_workflows.spine.events import PIPELINE_PRODUCER

_ALL_STAGES = tuple(stage.value for stage in ORDERED_STAGES)

# Every constitutional owner that records a fact on the shared spine log. Orchestration and the
# Execution engine participate *through* Execution Actuation, whose runtime/execution facts carry the
# shared ``runtime`` producer (P12/F-6) — so they appear as one deterministic ``runtime`` lineage.
_OWNER_PRODUCERS = {
    "intent",
    "estimation",
    "engineering",
    "policy",
    "context_engineering",
    "planning",
    "runtime",
    "validation",
    "recovery",
    "reflection",
    "knowledge",
}


def _pipeline(infra):
    return build_constitutional_pipeline(infra).coordinator


# --------------------------------------------------------------------------- #
# F-1 — one unified Goal→Knowledge driver                                        #
# --------------------------------------------------------------------------- #


def test_pipeline_runs_the_whole_spine_to_knowledge() -> None:
    infra = build_infrastructure()
    run = _pipeline(infra).run(spine_reference_request(run="r1"))

    assert run.status is SpineStatus.COMPLETED and run.succeeded
    assert run.executed_stages == _ALL_STAGES  # every owner invoked once, in dependency order
    plan_event = next(
        event for event in run.events if event.type == "planning.execution_plan_assembled"
    )
    packages = plan_event.payload["execution_plan"]["work_packages"]
    assert all(
        not any(reference["target_type"] == "action_request" for reference in package["inputs"])
        for package in packages
    )
    assert all(d == "passed" for d in run.validation_decisions)  # F-3 clean handoff → corroborated
    assert run.knowledge_item_ids  # evidence-backed Knowledge reached (INV-24)

    producers = {e.producer for e in infra.event_store.read_all()}
    assert (
        producers >= _OWNER_PRODUCERS
    )  # every constitutional owner participated on one shared log
    assert PIPELINE_PRODUCER in producers  # the pipeline coordinated the stages


def test_pipeline_is_the_only_driver_and_is_deterministic() -> None:
    def once():
        infra = build_infrastructure()
        run = _pipeline(infra).run(spine_reference_request(run="r1"))
        return [(e.identifier, e.type, e.payload) for e in run.events]

    first, second = once(), once()
    assert (
        first == second
    )  # byte-identical event stream across independent runs — one deterministic path


# --------------------------------------------------------------------------- #
# F-2 — durable replay + restart                                                 #
# --------------------------------------------------------------------------- #


def test_pipeline_replays_from_the_durable_log(tmp_path) -> None:
    db = str(tmp_path / "spine.db")
    request = spine_reference_request(run="r1")
    run = _pipeline(build_durable_infrastructure(db)).run(request)

    events = build_durable_infrastructure(db).event_store.read_all()  # reopened file
    session = reconstruct_pipeline_session(events, request.pipeline_session_id)
    assert session.status is SpineStatus.COMPLETED
    assert session.stages_completed == _ALL_STAGES  # the full pipeline reconstructs from the log
    # Its terminal ExecutionState reconstructs exactly (no re-execution).
    from nexus_workflows.spine import find_execution_state

    assert find_execution_state(events) == run.execution_state


def test_pipeline_restarts_from_the_last_completed_stage(tmp_path) -> None:
    db = str(tmp_path / "restart.db")
    request = spine_reference_request(run="r1")

    # Interrupt after Execution Actuation completes, before the Validate→Learn tail.
    partial = _pipeline(build_durable_infrastructure(db)).run(
        request, control=SpineControl(stop_after_stage=SpineStage.ACTUATION)
    )
    assert partial.status is SpineStatus.PAUSED
    assert partial.executed_stages[-1] == SpineStage.ACTUATION.value

    # Restart over the reopened file with fresh engines.
    resumed = _pipeline(build_durable_infrastructure(db)).run(request)
    assert resumed.status is SpineStatus.COMPLETED and resumed.succeeded
    # The front + actuation owners are reconstructed from the log — never re-invoked (INV-18).
    assert resumed.reconstructed_stages == (
        SpineStage.INTENT.value,
        SpineStage.ENGINEERING.value,
        SpineStage.CONTEXT.value,
        SpineStage.PLANNING.value,
        SpineStage.ACTUATION.value,
    )
    assert resumed.executed_stages == (
        SpineStage.VALIDATION.value,
        SpineStage.RECOVERY.value,
        SpineStage.REFLECTION.value,
        SpineStage.KNOWLEDGE.value,
    )

    # The resumed outcome equals an uninterrupted run's (restart never replans — INV-18/22).
    uninterrupted = _pipeline(build_durable_infrastructure(str(tmp_path / "whole.db"))).run(request)
    assert resumed.execution_state == uninterrupted.execution_state
    assert resumed.validation_decisions == uninterrupted.validation_decisions
    assert resumed.knowledge_item_ids == uninterrupted.knowledge_item_ids


def test_pipeline_restarts_after_a_mid_execution_interruption(tmp_path) -> None:
    db = str(tmp_path / "mid.db")
    request = spine_reference_request(run="r1")

    # Interrupt *inside* Execution Actuation (after one node) — the actuation itself is left resumable.
    partial = _pipeline(build_durable_infrastructure(db)).run(
        request, control=SpineControl(actuation=ActuationControl(stop_after=1))
    )
    assert partial.status is SpineStatus.PAUSED
    assert SpineStage.ACTUATION.value not in partial.pipeline_session.stages_completed

    # Restart resumes at Actuation; the actuator continues node-level from its own log, then Knowledge.
    resumed = _pipeline(build_durable_infrastructure(db)).run(request)
    assert resumed.status is SpineStatus.COMPLETED and resumed.succeeded
    assert SpineStage.ACTUATION.value in resumed.executed_stages  # re-entered, resumed node-level
    assert resumed.reconstructed_stages == (
        SpineStage.INTENT.value,
        SpineStage.ENGINEERING.value,
        SpineStage.CONTEXT.value,
        SpineStage.PLANNING.value,
    )
    assert resumed.knowledge_item_ids


# --------------------------------------------------------------------------- #
# Failure propagation + event lineage                                            #
# --------------------------------------------------------------------------- #


def test_failure_propagates_to_recovery_without_promoting_failed_knowledge() -> None:
    infra = build_infrastructure()
    request = spine_reference_request(run="r1", fail=True)
    run = _pipeline(infra).run(request)
    assert run.status is SpineStatus.COMPLETED  # the pipeline still reaches Knowledge
    assert not run.succeeded
    assert all(o == "failed" for o in run.execution_outcomes)
    assert all(d == "failed" for d in run.validation_decisions)  # Validation declines completion
    assert all(
        d == "retry" for d in run.recovery_decisions
    )  # Recovery decides continuation, bounded
    assert not run.knowledge_item_ids  # failed outcomes cannot become served guidance (Phase 5)
    assert not any(
        event.type == "knowledge.candidate_accepted"
        and event.correlation_identifier == request.correlation
        for event in infra.event_store.read_all()
    )


def test_pipeline_events_have_one_producer_and_the_session_reconstructs() -> None:
    infra = build_infrastructure()
    run = _pipeline(infra).run(spine_reference_request(run="r1"))
    events = run.events

    pipeline_events = [e for e in events if e.type.startswith("pipeline.")]
    assert all(e.producer == PIPELINE_PRODUCER for e in pipeline_events)  # one producer (INV-02)
    assert all(e.correlation_identifier for e in events)  # every fact is correlated (INV-39)
    identifiers = [e.identifier for e in events]
    assert len(identifiers) == len(set(identifiers))  # no duplicated producer of the same fact

    session = reconstruct_pipeline_session(events, run.pipeline_session.identity)
    assert session.stages_completed == _ALL_STAGES  # lineage reconstructs the full pipeline


# --------------------------------------------------------------------------- #
# RC2 — cross-goal execution identity isolation                                  #
# --------------------------------------------------------------------------- #
#
# ``spine_reference_request`` always produces work items keyed "draft"/"review" regardless of
# ``run=``, so two requests with different ``run`` values are two different goals whose plans
# collide on work-item key — the exact shape RC1's pre-merge review reproduced as a
# ``DuplicateEventError`` crash (or, under a fixed clock, silently merged facts) inside Runtime
# Session / Validation event scope. These tests drive that scenario for real, over one shared log.


def test_two_goals_with_identical_work_item_keys_do_not_collide() -> None:
    infra = build_infrastructure()
    coordinator = _pipeline(infra)

    first = coordinator.run(spine_reference_request(run="r1"))
    second = coordinator.run(
        spine_reference_request(run="r2")
    )  # must not raise DuplicateEventError

    assert first.status is SpineStatus.COMPLETED and first.succeeded
    assert second.status is SpineStatus.COMPLETED and second.succeeded
    assert all(d == "passed" for d in first.validation_decisions + second.validation_decisions)

    runtime_scopes = {
        e.identifier.rsplit("-created-0000", 1)[0].removeprefix("evt-")
        for e in infra.event_store.read_all()
        if e.type == "runtime.session_created"
    }
    # Two goals x two work items (draft, review) = four distinct runtime-session scopes, not two.
    assert len(runtime_scopes) == 4


def test_replay_after_two_concurrent_goals_reconstructs_each_independently(tmp_path) -> None:
    db = str(tmp_path / "concurrent.db")
    first_request = spine_reference_request(run="r1")
    second_request = spine_reference_request(run="r2")

    infra = build_durable_infrastructure(db)
    coordinator = _pipeline(infra)
    first = coordinator.run(first_request)
    second = coordinator.run(second_request)

    events = build_durable_infrastructure(db).event_store.read_all()  # reopened file
    first_session = reconstruct_pipeline_session(events, first_request.pipeline_session_id)
    second_session = reconstruct_pipeline_session(events, second_request.pipeline_session_id)

    assert first_session.status is SpineStatus.COMPLETED
    assert second_session.status is SpineStatus.COMPLETED
    assert first_session.stages_completed == _ALL_STAGES
    assert second_session.stages_completed == _ALL_STAGES

    from nexus_workflows.spine import find_execution_state

    # find_execution_state scans a caller-supplied slice (RC2's _seed filters by request.correlation
    # the same way) — a reconstruction correctly scoped per goal must not return the other goal's state.
    first_events = tuple(e for e in events if e.correlation_identifier == first_request.correlation)
    second_events = tuple(
        e for e in events if e.correlation_identifier == second_request.correlation
    )
    assert find_execution_state(first_events) == first.execution_state
    assert find_execution_state(second_events) == second.execution_state
    assert (
        first.execution_state != second.execution_state
    )  # distinct sessions, not one overwriting the other
    assert (
        first.execution_state != second.execution_state
    )  # distinct sessions, not one overwriting the other
