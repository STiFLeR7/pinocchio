"""P13 unit — replay reconstruction: the pipeline rebuilds from the durable log alone (F-2)."""

from __future__ import annotations

from nexus_infra import build_durable_infrastructure
from nexus_workflows.spine import (
    ORDERED_STAGES,
    SpineStatus,
    build_constitutional_pipeline,
    find_execution_state,
    find_goal,
    find_plan,
    find_strategy,
    reconstruct_pipeline_session,
    spine_reference_request,
)


def test_replay_reconstructs_owner_artifacts_without_re_invocation(tmp_path) -> None:
    db = str(tmp_path / "s.db")
    request = spine_reference_request(run="r1")
    run = build_constitutional_pipeline(build_durable_infrastructure(db)).coordinator.run(request)

    events = build_durable_infrastructure(db).event_store.read_all()  # reopened file
    # Each owner's artifact reconstructs from its own embedded fact — no owner re-runs (INV-17).
    assert find_goal(events).identity == run.goal_ref.identifier
    assert find_strategy(events).identity == run.strategy_ref.identifier
    assert find_plan(events).plan.identity == run.plan_ref.identifier
    assert find_execution_state(events) == run.execution_state


def test_replay_reconstructs_the_pipeline_session(tmp_path) -> None:
    db = str(tmp_path / "s.db")
    request = spine_reference_request(run="r1")
    build_constitutional_pipeline(build_durable_infrastructure(db)).coordinator.run(request)

    events = build_durable_infrastructure(db).event_store.read_all()
    session = reconstruct_pipeline_session(events, request.pipeline_session_id)
    assert session.status is SpineStatus.COMPLETED
    assert session.stages_completed == tuple(stage.value for stage in ORDERED_STAGES)
    assert session.lineage == tuple(stage.value for stage in ORDERED_STAGES)
