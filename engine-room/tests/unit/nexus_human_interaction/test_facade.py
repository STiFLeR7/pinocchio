"""P14/B unit — the Human Interaction façade drives + projects the constitutional pipeline."""

from __future__ import annotations

from nexus_core.contracts.enums import KnowledgeType
from nexus_human_interaction import build_human_interaction, reference_operator_request
from nexus_human_interaction.events import INTERACTION_PRODUCER
from nexus_infra import build_infrastructure


def _facade():
    return build_human_interaction(build_infrastructure()).facade


def test_submit_drives_the_whole_pipeline_to_knowledge() -> None:
    facade = _facade()
    response = facade.submit(reference_operator_request(run="r1"))
    assert response.status == "completed" and response.succeeded
    assert response.execution_status == "completed"
    assert response.validation_decisions and all(
        d == "passed" for d in response.validation_decisions
    )
    assert response.knowledge_item_ids  # reached evidence-backed Knowledge (INV-24)
    assert len(response.progress) == 9  # every constitutional stage participated


def test_inspection_projects_the_platform() -> None:
    facade = _facade()
    facade.submit(reference_operator_request(run="r1"))

    status = facade.status("op-arch-r1")
    assert status.is_complete and status.stages_completed[0] == "intent"

    graph = facade.execution_graph("op-arch-r1")
    assert graph.nodes == ("node-draft", "node-review")

    knowledge = facade.knowledge(
        subject="architecture summary generation", kind=KnowledgeType.LESSON
    )
    assert knowledge.items and knowledge.items[0][0].startswith("ki-")

    lineage = facade.explain_lineage("op-arch-r1")
    assert lineage.total_events > 0 and lineage.stages


def test_interaction_session_reconstructs_from_the_log() -> None:
    facade = _facade()
    facade.submit(reference_operator_request(run="r1"))
    session = facade.session("op-arch-r1")  # reconstructed from interaction.* facts
    assert session.identity == "hi-op-arch-r1"
    assert session.submitted and session.responded
    assert session.status == "completed"
    assert session.pipeline_session_ref.identifier == "pipe-op-arch-r1"


def test_facade_records_only_single_producer_interaction_facts() -> None:
    infra = build_infrastructure()
    build_human_interaction(infra).facade.submit(reference_operator_request(run="r1"))
    interaction = [e for e in infra.event_store.read_all() if e.type.startswith("interaction.")]
    assert interaction  # the façade recorded its operator-session facts
    assert all(e.producer == INTERACTION_PRODUCER for e in interaction)  # one owner (INV-02)
