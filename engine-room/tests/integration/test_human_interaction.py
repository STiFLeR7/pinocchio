"""P14/B — the Human Interaction surface exposes (never bypasses) the constitutional platform.

End-to-end proof that an operator drives and inspects the whole pipeline through one façade — submit,
status, execution graph, Knowledge, lineage, replay, restart — with durable replay + restart, and that
the learning loop reaches the operator (Goal → Knowledge → next Goal through the surface).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from nexus_core.contracts.base import Struct
from nexus_core.contracts.enums import KnowledgeType
from nexus_engineering.model import EngineeringStrategy, ReasoningInputs
from nexus_engineering.reasoner import DeterministicReasoner
from nexus_execution.actions import RepositoryAction
from nexus_human_interaction import build_human_interaction, reference_operator_request
from nexus_human_interaction.model import OperatorRequest
from nexus_infra import build_durable_infrastructure, build_infrastructure
from nexus_workflows.spine import SpineControl, SpineStage


class _AutomaticEngineeringReasoner:
    """Test EI posture that produces the automatic approval hint from frozen inputs."""

    version = "test-automatic"

    def reason(self, inputs: ReasoningInputs, *, now: str) -> EngineeringStrategy:
        strategy = DeterministicReasoner().reason(inputs, now=now)
        return strategy.model_copy(
            update={
                "autonomy_level": strategy.autonomy_level.model_copy(
                    update={"selection": ("autonomous",)}
                )
            }
        )


def test_operator_submits_and_reaches_knowledge() -> None:
    facade = build_human_interaction(build_infrastructure()).facade
    response = facade.submit(reference_operator_request(run="r1"))
    assert response.succeeded and response.status == "completed"
    assert response.knowledge_item_ids
    # Every operation went through the pipeline; inspection projects it.
    assert facade.status("op-arch-r1").is_complete
    assert facade.execution_graph("op-arch-r1").nodes == ("node-draft", "node-review")
    assert facade.knowledge(kind=KnowledgeType.LESSON).items


def test_repository_write_waits_for_human_approval_even_with_automatic_strategy(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    target = workspace / "README.md"
    target.write_text("before\n", encoding="utf-8")
    request = OperatorRequest(
        identity="repo-write-approval",
        request_text="In a local sandbox, investigate a small fixture and reversibly update the requested file.",
        work_items=(),
        knowledge_subject="repository write",
        scope="repository write",
        repository_root=str(workspace),
        repository_actions=(
            RepositoryAction.write(
                workspace_root=str(workspace),
                path="README.md",
                content="approved write\n",
                actor="operator",
                request_identity="repo-write-approval",
            ),
        ),
    )
    context = build_human_interaction(
        build_infrastructure(), engineering_reasoner=_AutomaticEngineeringReasoner()
    )
    facade = context.facade
    paused = facade.submit(request)

    assert paused.awaiting_approval
    assert paused.execution_plan is not None
    assert paused.goal_ref is not None
    assert paused.execution_plan.execution_strategy.approval_policy.value == "automatic"
    autonomy_event = next(
        event
        for event in context.infrastructure.event_store.read_all()
        if event.type == "engineering.strategized"
        and event.payload.get("subject") == paused.goal_ref.identifier
    )
    assert autonomy_event.payload["autonomy"] == "autonomous"
    assert target.read_text(encoding="utf-8") == "before\n"
    assert not any(
        event.type == "repository_action.started" for event in facade.history(request.identity)
    )
    assert paused.pending_approvals[0].taxonomy == "human_review"

    facade.approve(request, paused.pending_approvals[0].node, decided_by="operator")

    assert target.read_text(encoding="utf-8") == "approved write\n"
    action_events = facade.history(request.identity)
    assert sum(event.type == "repository_action.started" for event in action_events) == 1
    completed = next(
        event for event in action_events if event.type == "repository_action.completed"
    )
    outcome = completed.payload["outcome"]
    assert outcome["before_sha256"] is not None and outcome["after_sha256"] is not None
    assert outcome["diff_ref"] is not None
    assert "before\n" not in str(completed.payload)


def test_operator_flow_is_deterministic() -> None:
    def once() -> list[tuple[str, str, Struct]]:
        facade = build_human_interaction(build_infrastructure()).facade
        facade.submit(reference_operator_request(run="r1"))
        return [(e.identifier, e.type, e.payload) for e in facade.history("op-arch-r1")]

    assert once() == once()  # byte-identical operator + pipeline event stream across runs


def test_interaction_replays_from_the_durable_log(tmp_path: Path) -> None:
    db = str(tmp_path / "hi.db")
    build_human_interaction(build_durable_infrastructure(db)).facade.submit(
        reference_operator_request(run="r1")
    )
    # A fresh façade over the reopened file reconstructs the operator session exactly.
    replayed = build_human_interaction(build_durable_infrastructure(db)).facade.replay("op-arch-r1")
    assert replayed.submitted and replayed.responded
    assert replayed.status == "completed"
    assert replayed.pipeline_session_ref.identifier == "pipe-op-arch-r1"


def test_restart_resumes_without_replaying_completed_stages(tmp_path: Path) -> None:
    db = str(tmp_path / "restart.db")
    request = reference_operator_request(run="r1")

    paused = build_human_interaction(build_durable_infrastructure(db)).facade.submit(
        request, control=SpineControl(stop_after_stage=SpineStage.ACTUATION)
    )
    assert paused.status == "paused"

    resumed = build_human_interaction(build_durable_infrastructure(db)).facade.restart(request)
    assert resumed.status == "completed" and resumed.succeeded
    # The completed constitutional stages are reconstructed — not replayed (INV-18).
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


def test_learning_loop_reaches_the_operator_surface() -> None:
    # Goal → Knowledge → next Goal, through the operator façade.
    first = build_human_interaction(build_infrastructure())
    r1 = first.facade.submit(reference_operator_request(run="r1"))
    assert r1.knowledge_grounding is not None and r1.knowledge_grounding.consumed == 0

    second = build_human_interaction(
        build_infrastructure(), knowledge_repositories=first.spine.pipeline.knowledge.repositories
    )
    r2 = second.facade.submit(reference_operator_request(run="r2"))
    assert r2.knowledge_grounding is not None and r2.knowledge_grounding.consumed >= 1
    # The operator can inspect the provenance of what grounded the run.
    lineage = second.facade.explain_lineage("op-arch-r2")
    assert lineage.knowledge_provenance.get("count") == r2.knowledge_grounding.consumed


def test_shared_correlation_replay_keeps_repository_facts_request_scoped(
    tmp_path: Path,
) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    (first_root / "alpha_module.py").write_text("alpha = True\n", encoding="utf-8")
    (second_root / "beta_module.py").write_text("beta = True\n", encoding="utf-8")

    facade = build_human_interaction(build_infrastructure(), learning=False).facade

    def request(identity: str, root: Path, topic: str) -> OperatorRequest:
        return replace(
            reference_operator_request(run=identity),
            request_text=f"Add a test for {topic} behavior.",
            knowledge_subject=topic,
            scope=topic,
            correlation_identifier="shared-recurring-correlation",
            repository_root=str(root),
        )

    first = request("shared-first", first_root, "alpha")
    second = request("shared-second", second_root, "beta")
    first_response = facade.submit(
        first, control=SpineControl(stop_after_stage=SpineStage.PLANNING)
    )
    second_response = facade.submit(
        second, control=SpineControl(stop_after_stage=SpineStage.PLANNING)
    )
    replayed_first = facade.restart(first)

    assert first_response.execution_plan is not None
    assert second_response.execution_plan is not None
    assert replayed_first.execution_plan is not None
    assert (
        replayed_first.execution_plan.goal_ref.identifier
        == first_response.execution_plan.goal_ref.identifier
    )
    assert replayed_first.repository_profile is not None
    assert replayed_first.repository_profile["root"] == str(first_root.resolve())
    selection = replayed_first.grounding_selection
    assert selection is not None
    selected_rows = selection["selected"]
    assert isinstance(selected_rows, list)
    assert all(isinstance(row, dict) for row in selected_rows)
    selected_ids = {str(row["identifier"]) for row in selected_rows}
    assert "alpha_module.py" in selected_ids
    assert "beta_module.py" not in selected_ids
