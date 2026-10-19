"""Reopen a durable Phase 4 log and verify report reconstruction without evidence reads."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from nexus_execution.actions import RepositoryAction
from nexus_human_interaction import build_human_interaction
from nexus_human_interaction.model import OperatorRequest
from nexus_infra import build_durable_infrastructure
from nexus_planning.grounded import ExecutionPlan
from nexus_validation import build_validation
from nexus_validation.outcome_evidence import OutcomeConditionEvaluator
from nexus_workflows.spine import find_execution_state
from nexus_workflows.spine.bridge import execution_results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--expected", required=True, type=Path)
    parser.add_argument("--session", required=True)
    args = parser.parse_args()

    infrastructure = build_durable_infrastructure(str(args.db))
    before = tuple(infrastructure.event_store.read_all())
    state = find_execution_state(before)
    if state is None:
        raise RuntimeError("durable execution state is absent")
    results = execution_results(state, before)
    result = next((item for item in results if item.session_ref.identifier == args.session), None)
    if result is None:
        raise RuntimeError("durable execution result is absent")
    plan_event = next(
        event for event in before if event.type == "planning.execution_plan_assembled"
    )
    plan = ExecutionPlan.model_validate(plan_event.payload["execution_plan"])
    work_package = next(
        package
        for package in plan.work_packages
        if package.identifier == result.work_package_ref.identifier
    )
    terminal_count = sum(
        event.type in {"validation.completed", "validation.failed"} for event in before
    )
    started_count = sum(event.type == "repository_action.started" for event in before)
    interaction_response_count = sum(
        event.type == "interaction.response_recorded" for event in before
    )
    expected: dict[str, Any] = json.loads(args.expected.read_text(encoding="utf-8"))

    # Replay must consume only durable facts. Any call to the external evidence evaluator fails.
    with (
        patch.object(
            OutcomeConditionEvaluator,
            "evaluate",
            side_effect=AssertionError("replay attempted external outcome evidence collection"),
        ),
        patch(
            "nexus_execution.actions.boundary.RepositoryActionBoundary.execute",
            side_effect=AssertionError("operator restart attempted action dispatch"),
        ),
    ):
        report = build_validation(infrastructure).engine.replay(before, result, work_package)
        action_event = next(
            event for event in before if event.type == "repository_action.requested"
        )
        action = RepositoryAction.model_validate(action_event.payload["action"])
        submitted = next(
            event
            for event in before
            if event.type == "interaction.request_submitted"
            and action.identity in event.payload.get("action_ids", ())
        )
        workspace = action.workspace_root
        operator_request = OperatorRequest(
            identity=action.request_identity,
            request_text=str(submitted.payload["request_text"]),
            work_items=(),
            knowledge_subject="replay",
            scope="phase4-replay",
            correlation_identifier=submitted.correlation_identifier,
            repository_root=workspace,
            repository_actions=(action,),
        )
        same_store_interaction = build_human_interaction(
            infrastructure,
            learning=False,
            action_command_allowlist=(
                {action.command_id: tuple(action.resolved_argv)} if action.command_id else {}
            ),
            action_artifact_directory=str(args.db.parent / "action-artifacts"),
        )
        same_store_response = same_store_interaction.facade.restart(operator_request)
        same_store_after = tuple(infrastructure.event_store.read_all())
        operator_infrastructure = build_durable_infrastructure(
            str(args.db.with_name(args.db.stem + "-operator-restart.sqlite"))
        )
        # Model the crash window after the validation terminal was durable but before
        # interaction.response_recorded, forcing the public restart route into the pipeline.
        for event in before:
            if event.type != "interaction.response_recorded":
                operator_infrastructure.emit(event)
        operator_before = tuple(operator_infrastructure.event_store.read_all())
        interaction = build_human_interaction(
            operator_infrastructure,
            learning=False,
            action_command_allowlist=(
                {action.command_id: tuple(action.resolved_argv)} if action.command_id else {}
            ),
            action_artifact_directory=str(args.db.parent / "action-artifacts"),
        )
        response = interaction.facade.restart(operator_request)
        operator_after = tuple(operator_infrastructure.event_store.read_all())
    after = tuple(infrastructure.event_store.read_all())
    if report is None:
        raise RuntimeError("durable validation report is absent")
    event_report = next(
        event.payload["report"]
        for event in before
        if event.type in {"validation.completed", "validation.failed"}
        and event.payload.get("report", {}).get("identity") == report.identity
    )
    evidence_event = next(
        event
        for event in before
        if event.type == "validation.evidence_collected"
        and event.identifier.startswith(f"evt-{args.session}-val-evidence-")
    )
    print(
        json.dumps(
            {
                "same_report": report.model_dump(mode="json") == expected == event_report,
                "decision": report.decision.value,
                "operator_restart_decision": response.validation_decisions[0]
                if response.validation_decisions
                else None,
                "operator_restart_runtime_completed": response.runtime_completed,
                "same_store_restart_decision": same_store_response.validation_decisions[0]
                if same_store_response.validation_decisions
                else None,
                "same_store_restart_validation_terminals_before": terminal_count,
                "same_store_restart_validation_terminals_after": sum(
                    event.type in {"validation.completed", "validation.failed"}
                    for event in same_store_after
                ),
                "same_store_restart_action_starts_before": started_count,
                "same_store_restart_action_starts_after": sum(
                    event.type == "repository_action.started" for event in same_store_after
                ),
                "same_store_restart_responses_before": interaction_response_count,
                "same_store_restart_responses_after": sum(
                    event.type == "interaction.response_recorded" for event in same_store_after
                ),
                "report_id": report.identity,
                "evidence_count": len(evidence_event.payload.get("evidence", ())),
                "evidence_refs": [ref.identifier for ref in report.evidence_refs],
                "validation_terminals_before": terminal_count,
                "validation_terminals_after": sum(
                    event.type in {"validation.completed", "validation.failed"} for event in after
                ),
                "action_starts_before": started_count,
                "action_starts_after": sum(
                    event.type == "repository_action.started" for event in after
                ),
                "interaction_responses_before": interaction_response_count,
                "operator_restart_pipeline_entered": any(
                    event.type == "pipeline.resumed" for event in operator_after
                ),
                "operator_restart_validation_terminals_before": sum(
                    event.type in {"validation.completed", "validation.failed"}
                    for event in operator_before
                ),
                "operator_restart_validation_terminals_after": sum(
                    event.type in {"validation.completed", "validation.failed"}
                    for event in operator_after
                ),
                "operator_restart_action_starts_before": sum(
                    event.type == "repository_action.started" for event in operator_before
                ),
                "operator_restart_action_starts_after": sum(
                    event.type == "repository_action.started" for event in operator_after
                ),
                "operator_restart_responses_after": sum(
                    event.type == "interaction.response_recorded" for event in operator_after
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
