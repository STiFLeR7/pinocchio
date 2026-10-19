"""Phase 5: durable outcome-linked Knowledge acceptance, serving, and replay."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from nexus_core.contracts.base import Reference
from nexus_infra import build_durable_infrastructure
from nexus_knowledge.candidate import KnowledgeCandidate
from nexus_knowledge.provenance import verify_candidate_sources
from nexus_workflows.spine import build_constitutional_pipeline, spine_reference_request


def test_passed_source_is_scoped_served_and_replayed_in_a_fresh_process(tmp_path: Path) -> None:
    database = tmp_path / "phase5.db"
    infrastructure = build_durable_infrastructure(str(database))
    pipeline = build_constitutional_pipeline(infrastructure).coordinator

    source = pipeline.run(spine_reference_request(run="phase5-source"))
    assert source.knowledge_item_ids
    item_id = source.knowledge_item_ids[0]
    item = next(item for item in pipeline.inspect_knowledge() if item.identity == item_id)
    assert item.metadata is not None
    assert item.metadata["source_goal_ref"]["identifier"] == "goal-spine-arch-phase5-source"
    assert item.metadata["source_run_refs"]
    assert item.metadata["validation_report_refs"]
    assert item.evidence_refs

    second_request = spine_reference_request(run="phase5-second")
    second = pipeline.run(second_request)
    selection = second.knowledge_grounding
    assert selection is not None and item_id in selection.selected_ids
    context_event = next(
        event
        for event in second.events
        if event.type == "context.grounding.selected"
        and event.correlation_identifier == "cor-spine-arch-phase5-second"
    )
    context_knowledge = {
        row["identifier"]
        for row in context_event.payload["selected"]
        if row["artifact_type"] == "knowledge" and row["selected"]
    }
    assert item_id in context_knowledge
    expected_item = next(
        item for item in pipeline.inspect_knowledge() if item.identity == item_id
    ).model_dump(mode="json")

    before = tuple(infrastructure.event_store.read_all())
    infrastructure.close()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    worker = Path(__file__).resolve().parents[1] / "e2e" / "phase5_replay_worker.py"
    completed = subprocess.run(
        [sys.executable, str(worker), str(database), "phase5-second"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    replay = json.loads(completed.stdout)
    assert replay["status"] == "completed"
    assert item_id in replay["selection"]
    assert any(item_id in refs for refs in replay["context_refs"])
    assert expected_item in replay["items"]
    assert replay["knowledge_candidates_after"] == replay["knowledge_candidates_before"]
    assert replay["runtime_after"] == replay["runtime_before"]
    assert replay["after_types"].count("pipeline.knowledge_grounded") == sum(
        event.type == "pipeline.knowledge_grounded" for event in before
    )


def test_failed_validation_source_is_not_accepted_as_knowledge() -> None:
    infrastructure = build_durable_infrastructure(":memory:")
    pipeline = build_constitutional_pipeline(infrastructure).coordinator
    failed = pipeline.run(spine_reference_request(run="phase5-failed", fail=True))
    assert not failed.knowledge_item_ids
    assert any(
        decision in {"failed", "partial", "requires_review"}
        for decision in failed.validation_decisions
    )
    assert not any(
        event.type == "knowledge.candidate_accepted"
        and event.correlation_identifier == "cor-spine-arch-phase5-failed"
        for event in infrastructure.event_store.read_all()
    )
    assert any(
        event.type == "knowledge.candidate_rejected"
        and event.correlation_identifier == "cor-spine-arch-phase5-failed"
        for event in infrastructure.event_store.read_all()
    )


def test_candidate_provenance_rejects_wrong_reference_target_type() -> None:
    infrastructure = build_durable_infrastructure(":memory:")
    pipeline = build_constitutional_pipeline(infrastructure).coordinator
    result = pipeline.run(spine_reference_request(run="phase5-wrong-ref-type"))
    events = tuple(infrastructure.event_store.read_all())
    accepted = next(
        event
        for event in events
        if event.type == "knowledge.candidate_accepted"
        and event.correlation_identifier == "cor-spine-arch-phase5-wrong-ref-type"
    )
    candidate = KnowledgeCandidate.model_validate(accepted.payload["candidate_data"])
    wrong_ref = candidate.validation_report_refs[0].model_copy(
        update={"target_type": "runtime_session"}
    )
    tampered = candidate.model_copy(
        update={"validation_report_refs": (wrong_ref, *candidate.validation_report_refs[1:])}
    )
    assert result.knowledge_item_ids
    assert not verify_candidate_sources(tampered, events)


def test_feedback_is_attributed_and_contradiction_deprecates() -> None:
    infrastructure = build_durable_infrastructure(":memory:")
    pipeline = build_constitutional_pipeline(infrastructure).coordinator
    source = pipeline.run(spine_reference_request(run="phase5-feedback"))
    item_id = source.knowledge_item_ids[0]
    source_run = Reference(
        target_type="runtime_session",
        identifier="rts-actuation-pkg-session-goal-spine-arch-phase5-feedback-v1-node-draft-01",
    )
    feedback = pipeline.record_knowledge_feedback(
        item_id,
        actor="operator-17",
        source_run_ref=source_run,
        effect="contradict",
        feedback_id="feedback-phase5-contradiction",
    )
    item = next(
        event.payload["item_data"]
        for event in infrastructure.event_store.read_all()
        if event.type == "knowledge.item_deprecated" and event.payload.get("subject_key") == item_id
    )
    assert item["freshness"] == "deprecated"
    event = next(
        event
        for event in infrastructure.event_store.read_all()
        if event.identifier == feedback.identifier
    )
    assert event.payload["actor"] == "operator-17"
    assert event.payload["effect"] == "contradict"
    assert event.payload["source_run_ref"]["identifier"] == source_run.identifier
