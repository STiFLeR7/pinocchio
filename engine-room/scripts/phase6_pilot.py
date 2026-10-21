"""Bounded operator pilot for the frozen five-case Phase 6 repair gate.

The real operator flow is `prepare` followed by `approve`; they are separate processes.
`rehearse` runs the same commands with explicitly simulated approvals and is not human pilot evidence.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from nexus_context import ContextCategory, ContextSource, RawContextFragment
from nexus_core.contracts.base import Reference
from nexus_execution.actions import RepositoryAction
from nexus_human_interaction import build_human_interaction
from nexus_human_interaction.model import OperatorRequest
from nexus_infra import build_durable_infrastructure
from nexus_planning import WorkItemSpec
from nexus_runtime.events import SystemTimestampSource
from nexus_workflows.spine import SpineControl, SpineStage

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "docs" / "phase6" / "cases.json"
GATE_PATH = ROOT / "docs" / "phase6" / "PHASE6_PILOT_GATE.md"
EVIDENCE_ROOT = ROOT / "docs" / "phase6" / "evidence"
TEST_RUNNER = Path(__file__).with_name("phase6_test_runner.py").resolve()
COMMANDS = {
    "phase6-fixture-tests": (sys.executable, str(TEST_RUNNER)),
    "phase6-fixture-tests-no-report": (sys.executable, str(TEST_RUNNER), "--no-report"),
}
SAFE_EVENT_FIELDS = {
    "action_id",
    "input_digest",
    "kind",
    "actor",
    "decided_by",
    "request_identity",
    "work_item_key",
    "path",
    "command_id",
    "argv",
    "plan",
    "pipeline_session",
    "node",
    "policy_event",
    "approval_event",
    "decision",
    "status",
    "reason",
    "action",
    "session",
    "request",
    "stage",
    "artifact_id",
    "sha256",
    "report",
    "item_id",
    "subject_key",
    "candidate",
    "outcome",
    "error_code",
    "deciding_rule",
    "failure_category",
    "retry_eligible",
    "resumable",
    "exit_status",
}


def _sha(value: bytes | str) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def _cases() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(CASES_PATH.read_text(encoding="utf-8")))


def _identity(run_id: str, case_id: str) -> str:
    return f"phase6-{run_id}-{case_id.lower()}"


def _fixture_request(case: dict[str, Any], run_id: str, workspace: Path) -> OperatorRequest:
    case_id = str(case["id"])
    identity = _identity(run_id, case_id)
    source_expected = _sha(str(case["expected_source"]))
    test_command = (
        "phase6-fixture-tests" if case["junit_report"] else "phase6-fixture-tests-no-report"
    )
    write_action = RepositoryAction.write(
        workspace_root=str(workspace),
        path="src/repair.py",
        content=str(case["proposed_source"]),
        actor="operator",
        request_identity=identity,
        work_item_key="edit",
        correlation=f"cor-{identity}",
    )
    test_action = RepositoryAction.run_test(
        workspace_root=str(workspace),
        command_id=test_command,
        actor="operator",
        request_identity=identity,
        work_item_key="test",
        correlation=f"cor-{identity}",
    )
    items = (
        WorkItemSpec(
            key="edit",
            objective=f"Apply the proposed repair for {case['function']}",
            capability_requirements=("repository_action",),
            skill_refs=(Reference(target_type="skill", identifier="skill-repair-source"),),
            completion_criteria={
                "outcome_conditions": [
                    {
                        "id": "target-source-hash",
                        "type": "file_sha256",
                        "path": "src/repair.py",
                        "expected_sha256": source_expected,
                    }
                ]
            },
            requires_approval=True,
        ),
        WorkItemSpec(
            key="test",
            objective=f"Run the fixed allow-listed fixture tests for {case['function']}",
            capability_requirements=("repository_action",),
            skill_refs=(Reference(target_type="skill", identifier="skill-run-fixture-tests"),),
            depends_on=("edit",),
            completion_criteria={
                "outcome_conditions": [
                    {
                        "id": "fixture-junit",
                        "type": "junit_xml",
                        "command_id": test_command,
                        "paths": ["reports/phase6-junit.xml"],
                    }
                ]
            },
        ),
    )
    return OperatorRequest(
        identity=identity,
        request_text=f"Fix software function: {case['goal']}",
        work_items=items,
        knowledge_subject=f"Phase 6 fixture repair: {case['function']}",
        scope=f"phase6-{case_id}",
        context_fragments=(
            RawContextFragment(
                source=ContextSource.WORKSPACE,
                category=ContextCategory.WORKSPACE,
                key="repository",
            ),
        ),
        correlation_identifier=f"cor-{identity}",
        repository_root=str(workspace),
        repository_actions=(write_action, test_action),
    )


def _validate_workspace(workspace: Path, *, allow_empty: bool = False) -> Path:
    resolved = workspace.resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise ValueError(
            "Phase 6 only writes into disposable workspaces outside the Nexus checkout"
        )
    marker = resolved / ".phase6-fixture"
    if marker.exists():
        if marker.read_text(encoding="utf-8").strip() != "phase6-fixture-v1":
            raise ValueError("workspace fixture marker is invalid")
        return resolved
    if not allow_empty or (resolved.exists() and any(resolved.iterdir())):
        raise ValueError("workspace must be empty or already marked as a Phase 6 fixture")
    resolved.mkdir(parents=True, exist_ok=True)
    marker.write_text("phase6-fixture-v1\n", encoding="utf-8")
    return resolved


def _resolve_db(value: str, workspace: Path) -> Path:
    db = Path(value).resolve()
    if db == ROOT or ROOT in db.parents:
        raise ValueError("pilot database and sidecars must stay outside the Nexus checkout")
    if db == workspace or workspace in db.parents:
        raise ValueError("durable database and sidecars must stay outside the governed workspace")
    if db.exists() and not db.is_file():
        raise ValueError("database path must be a file path")
    return db


def _write_fixture(case: dict[str, Any], workspace: Path) -> None:
    (workspace / "src").mkdir(parents=True, exist_ok=True)
    (workspace / "tests").mkdir(parents=True, exist_ok=True)
    (workspace / "reports").mkdir(parents=True, exist_ok=True)
    (workspace / "src" / "repair.py").write_text(case["initial_source"], encoding="utf-8")
    samples = json.dumps(case["samples"], ensure_ascii=True)
    (workspace / "tests" / "samples.json").write_text(samples + "\n", encoding="utf-8")
    test_text = """from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
repair = importlib.import_module("repair")
samples = json.loads(Path(__file__).with_name("samples.json").read_text(encoding="utf-8"))

@pytest.mark.parametrize(("arguments", "expected"), samples)
def test_repair(arguments: list[object], expected: object) -> None:
    assert getattr(repair, "FUNCTION_NAME")(*arguments) == expected
""".replace("FUNCTION_NAME", str(case["function"]))
    (workspace / "tests" / "test_repair.py").write_text(test_text, encoding="utf-8")


def _manifest(workspace: Path) -> dict[str, str]:
    return {
        path.relative_to(workspace).as_posix(): _sha(path.read_bytes())
        for path in sorted(workspace.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def _request_for_resume(request: OperatorRequest) -> OperatorRequest:
    return replace(request, repository_actions=())


def _context(db: Path) -> Any:
    infrastructure = build_durable_infrastructure(str(db))
    context = build_human_interaction(
        infrastructure,
        timestamps=SystemTimestampSource(),
        action_command_allowlist=COMMANDS,
        action_artifact_directory=os.path.abspath(f"{db}.action_artifacts"),
    )
    return context


def _write_plan_review(
    response: Any, case: dict[str, Any], db: Path, workspace: Path
) -> dict[str, Any]:
    plan = response.execution_plan
    if plan is None:
        raise RuntimeError(
            f"Planning did not produce a reviewable plan: status={response.status!r}, "
            f"plan_ref={response.plan_ref!r}, stages={response.progress!r}"
        )
    packages = {package.identifier: package for package in plan.work_packages}
    nodes = []
    for node in plan.execution_graph.nodes:
        package = packages[node.work_package_ref.identifier]
        nodes.append(
            {
                "node_id": node.identifier,
                "work_package_id": package.identifier,
                "objective": package.objective,
                "dependencies": [
                    [source, target]
                    for source, target in plan.coordination.dependency_edges
                    if target == node.identifier
                ],
                "action_refs": [
                    ref.identifier for ref in package.inputs if ref.target_type == "action_request"
                ],
                "completion_criteria": package.completion_criteria,
            }
        )
    review = {
        "run_id": response.session_id,
        "case_id": case["id"],
        "goal": case["goal"],
        "intent_input_transformation": {
            "raw_frozen_goal": case["goal"],
            "submitted_intent_text": f"Fix software function: {case['goal']}",
            "reason": "Current deterministic Intent requires a software-domain signal; this prefix is a harness intervention, not part of the frozen goal.",
        },
        "case_note": (
            "Intentionally incorrect proposed repair; tests are expected to fail."
            if case["id"] == "P4"
            else "Report omission probe; no JUnit report will be produced, so test acceptance should require review."
            if case["id"] == "P5"
            else ""
        ),
        "proposed_diff": "".join(
            difflib.unified_diff(
                str(case["initial_source"]).splitlines(keepends=True),
                str(case["proposed_source"]).splitlines(keepends=True),
                fromfile="a/src/repair.py",
                tofile="b/src/repair.py",
            )
        ),
        "test_samples": case["samples"],
        "workspace": "<fixture-workspace>",
        "plan_id": plan.identity,
        "goal_ref": plan.goal_ref.model_dump(mode="json"),
        "nodes": nodes,
        "source_refs": [ref.model_dump(mode="json") for ref in plan.context_references],
        "assumptions": list(plan.plan.assumptions),
        "status": response.status,
        "clarification_count": len(response.clarification_requests),
        "runtime_started_before_approval": False,
        "action_started_before_approval": False,
        "db": db.name,
    }
    output_dir = Path(f"{db}.phase6") / str(case["id"])
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "plan_review.json").write_text(
        json.dumps(review, indent=2) + "\n", encoding="utf-8"
    )
    return review


def _prepare(args: argparse.Namespace) -> int:
    case = next(item for item in _cases()["cases"] if item["id"] == args.case_id)
    candidate_workspace = Path(args.workspace).resolve()
    if (candidate_workspace / ".phase6-fixture").exists():
        raise ValueError(
            "prepare refuses to overwrite an existing fixture; choose a new disposable workspace"
        )
    workspace = _validate_workspace(candidate_workspace, allow_empty=True)
    _write_fixture(case, workspace)
    db = _resolve_db(args.db, workspace)
    if args.case_id == "P1" and db.exists():
        raise ValueError("first case requires a new database path")
    db.parent.mkdir(parents=True, exist_ok=True)
    request = _fixture_request(case, args.run_id, workspace)
    context = _context(db)
    try:
        before = _manifest(workspace)
        response = context.facade.submit(
            request, control=SpineControl(stop_after_stage=SpineStage.PLANNING)
        )
        events = tuple(
            event
            for event in context.infrastructure.event_store.read_all()
            if event.correlation_identifier == request.correlation
        )
        if any(event.type == "repository_action.started" for event in events):
            raise RuntimeError("an action started before the plan was approved")
        after = _manifest(workspace)
        if before != after:
            raise RuntimeError("planning modified the fixture workspace")
        review = _write_plan_review(response, case, db, workspace)
        case_dir = Path(f"{db}.phase6") / str(case["id"])
        (case_dir / "before_files.json").write_text(
            json.dumps(before, indent=2) + "\n", encoding="utf-8"
        )
        (case_dir / "prepare_trace.json").write_text(
            json.dumps(_trace(events), indent=2) + "\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {"status": response.status, "session": request.identity, "plan": review}, indent=2
            )
        )
    finally:
        context.infrastructure.close()
    return 0


def _approve(args: argparse.Namespace) -> int:
    case = next(item for item in _cases()["cases"] if item["id"] == args.case_id)
    workspace = _validate_workspace(Path(args.workspace))
    db = _resolve_db(args.db, workspace)
    request = _fixture_request(case, args.run_id, workspace)
    context = _context(db)
    try:
        review_path = Path(f"{db}.phase6") / str(case["id"]) / "plan_review.json"
        if not review_path.is_file():
            raise ValueError("plan review artifact is missing; prepare and inspect the plan first")
        review = json.loads(review_path.read_text(encoding="utf-8"))
        if not args.simulate_approval:
            print("Prepared plan and proposed change for operator review:")
            print(json.dumps(review, indent=2))
        pending_response = context.facade.restart(_request_for_resume(request))
        pending = context.facade.pending_approvals(request.identity)
        edit_node = (
            next(
                node.identifier
                for node in pending_response.execution_plan.execution_graph.nodes
                if any(
                    item.identifier == node.work_package_ref.identifier
                    and "Apply the proposed repair" in item.objective
                    for item in pending_response.execution_plan.work_packages
                )
            )
            if pending_response.execution_plan
            else ""
        )
        if not edit_node or not any(item.node == edit_node for item in pending):
            raise RuntimeError("expected write approval is not pending for the edit node")
        decision_mode = "simulated" if args.simulate_approval else "human"
        if args.simulate_approval:
            decision = "approve"
            decided_by = "SIMULATED_REHEARSAL_OPERATOR"
        else:
            print(f"Review plan first. Write node: {edit_node}")
            typed = input(f"Type APPROVE to authorize the Phase 6 workspace write ({case['id']}): ")
            decision = "approve" if typed.strip() == "APPROVE" else "deny"
            decided_by = args.operator
        if decision == "approve":
            context.facade.approve(
                _request_for_resume(request),
                edit_node,
                decided_by=decided_by,
                reason="Phase 6 pilot approval",
            )
        else:
            context.facade.deny(
                _request_for_resume(request),
                edit_node,
                decided_by=decided_by,
                reason="operator declined",
            )
        events = tuple(
            event
            for event in context.infrastructure.event_store.read_all()
            if event.correlation_identifier == request.correlation
        )
        (Path(f"{db}.phase6") / str(case["id"]) / "approval_trace.json").write_text(
            json.dumps(
                {
                    "mode": decision_mode,
                    "decided_by": decided_by,
                    "decision": decision,
                    "events": _trace(events),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {"decision": decision, "mode": decision_mode, "decided_by": decided_by}, indent=2
            )
        )
    finally:
        context.infrastructure.close()
    return 0


def _replay(args: argparse.Namespace) -> int:
    case = next(item for item in _cases()["cases"] if item["id"] == args.case_id)
    workspace = _validate_workspace(Path(args.workspace))
    db = _resolve_db(args.db, workspace)
    request = _fixture_request(case, args.run_id, workspace)
    context = _context(db)
    try:
        before_all = tuple(context.infrastructure.event_store.read_all())
        before = tuple(
            event for event in before_all if event.correlation_identifier == request.correlation
        )
        replay = context.facade.restart(_request_for_resume(request))
        after_all = tuple(context.infrastructure.event_store.read_all())
        after = tuple(
            event for event in after_all if event.correlation_identifier == request.correlation
        )
        result = {
            "status": replay.status,
            "validation_decisions": list(replay.validation_decisions),
            "knowledge_item_ids": list(replay.knowledge_item_ids),
            "action_starts_before_after": [
                sum(e.type == "repository_action.started" for e in before),
                sum(e.type == "repository_action.started" for e in after),
            ],
            "runtime_starts_before_after": [
                sum(e.type == "runtime.started" for e in before),
                sum(e.type == "runtime.started" for e in after),
            ],
            "validation_terminals_before_after": [
                sum(e.type in {"validation.completed", "validation.failed"} for e in before),
                sum(e.type in {"validation.completed", "validation.failed"} for e in after),
            ],
            "model_call_events_before_after": [
                sum(event.type.startswith(("model.", "llm.", "provider.")) for event in before),
                sum(event.type.startswith(("model.", "llm.", "provider.")) for event in after),
            ],
            "knowledge_decisions_before_after": [
                sum(
                    event.type in {"knowledge.candidate_accepted", "knowledge.candidate_rejected"}
                    for event in before
                ),
                sum(
                    event.type in {"knowledge.candidate_accepted", "knowledge.candidate_rejected"}
                    for event in after
                ),
            ],
            "new_event_types": [
                e.type for e in after if e.identifier not in {old.identifier for old in before}
            ],
        }
        replay_path = Path(f"{db}.phase6") / str(case["id"]) / "replay_trace.json"
        replay_path.parent.mkdir(parents=True, exist_ok=True)
        replay_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
    finally:
        context.infrastructure.close()
    return 0


def _assess(args: argparse.Namespace) -> int:
    """Capture a named human's usefulness judgment after the run; never used in rehearsal."""
    case = next(item for item in _cases()["cases"] if item["id"] == args.case_id)
    db = Path(args.db).resolve()
    approval_path = Path(f"{db}.phase6") / str(case["id"]) / "approval_trace.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if approval.get("mode") != "human":
        raise ValueError("operator assessments are accepted only for a real human approval run")
    context = _context(db)
    try:
        correlation = f"cor-{_identity(args.run_id, str(case['id']))}"
        events = tuple(
            event
            for event in context.infrastructure.event_store.read_all()
            if event.correlation_identifier == correlation
        )
        verdicts = _node_verdicts(events)
        if len(verdicts) != 2:
            raise ValueError(
                "both validation node verdicts must exist before usefulness assessment"
            )
        approved = any(event.type == "approval.approved" for event in events)
        if not approved:
            raise ValueError("no recorded human approval was found for this run")
    finally:
        context.infrastructure.close()
    answer = input(
        "Was this plan and outcome useful for your repair goal? Type USEFUL or NOT_USEFUL: "
    ).strip()
    if answer not in {"USEFUL", "NOT_USEFUL"}:
        raise ValueError("assessment must be exactly USEFUL or NOT_USEFUL")
    notes = input("Optional short reason (press Enter to leave blank): ").strip()
    assessment = {
        "case_id": case["id"],
        "run_id": args.run_id,
        "actor": args.operator,
        "useful": answer == "USEFUL",
        "assessment": answer.lower(),
        "notes": notes,
        "source_correlation": correlation,
        "validation_verdicts": [item["verdict"] for item in verdicts],
        "approval_mode": "human",
        "recorded_at": datetime.now().astimezone().isoformat(),
    }
    target = EVIDENCE_ROOT / "pilot" / args.run_id / f"{case['id']}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(assessment, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"assessment_file": str(target), "assessment": assessment}, indent=2))
    return 0


def _scorecard(args: argparse.Namespace) -> int:
    cases = _cases()["cases"]
    db = Path(args.db).resolve()
    workspace_root = Path(args.workspace_root).resolve()
    observations: list[dict[str, Any]] = []
    assessments: list[dict[str, Any] | None] = []
    approvals: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case["id"])
        directory = Path(f"{db}.phase6") / case_id
        workspace = _validate_workspace(workspace_root / case_id)
        observation = _case_observation(case, db, workspace, args.run_id)
        replay_path = directory / "replay_trace.json"
        observation["replay"] = (
            json.loads(replay_path.read_text(encoding="utf-8")) if replay_path.is_file() else None
        )
        approval_path = directory / "approval_trace.json"
        approval = (
            json.loads(approval_path.read_text(encoding="utf-8")) if approval_path.is_file() else {}
        )
        approvals.append(approval)
        observation["approval_mode"] = approval.get("mode", "missing")
        review_path = directory / "plan_review.json"
        observation["plan_conditions_frozen"] = review_path.is_file() and _plan_is_frozen_correctly(
            case, json.loads(review_path.read_text(encoding="utf-8"))
        )
        assessment_path = EVIDENCE_ROOT / "pilot" / args.run_id / f"{case_id}.json"
        assessment = (
            json.loads(assessment_path.read_text(encoding="utf-8"))
            if assessment_path.is_file()
            else None
        )
        assessments.append(assessment)
        observation["assessment"] = assessment
        observations.append(observation)

    actors = {str(approval["decided_by"]) for approval in approvals if approval.get("decided_by")}
    actors.update(
        str(assessment["actor"])
        for assessment in assessments
        if assessment is not None and assessment.get("actor")
    )
    feedback_path = EVIDENCE_ROOT / "pilot" / args.run_id / "operator_feedback.json"
    feedback = (
        json.loads(feedback_path.read_text(encoding="utf-8")) if feedback_path.is_file() else {}
    )
    feedback_valid = (
        feedback.get("run_id") == args.run_id
        and feedback.get("actor") in actors
        and type(feedback.get("false_denials")) is int
        and 0 <= feedback["false_denials"] <= len(cases)
    )
    passed_and_useful = sum(
        assessment is not None
        and assessment.get("useful") is True
        and assessment.get("approval_mode") == "human"
        and assessment.get("run_id") == args.run_id
        and assessment.get("case_id") == case["id"]
        and assessment.get("source_correlation") == f"cor-{_identity(args.run_id, str(case['id']))}"
        and assessment.get("actor") in observation["approval_actors"]
        and observation["actual_node_verdicts"] == ["passed", "passed"]
        for case, assessment, observation in zip(cases, assessments, observations, strict=True)
    )
    false_passed = sum(
        actual == "passed" and actual != expected
        for case, observation in zip(cases, observations, strict=True)
        for actual, expected in zip(
            observation["actual_node_verdicts"], case["expected_verdicts"], strict=False
        )
    )
    replay_ok = all(
        observation["replay"] is not None
        and not observation["replay"]["new_event_types"]
        and observation["replay"]["action_starts_before_after"][0]
        == observation["replay"]["action_starts_before_after"][1]
        and observation["replay"]["validation_terminals_before_after"][0]
        == observation["replay"]["validation_terminals_before_after"][1]
        and observation["replay"]["model_call_events_before_after"][0]
        == observation["replay"]["model_call_events_before_after"][1]
        and observation["replay"]["knowledge_decisions_before_after"][0]
        == observation["replay"]["knowledge_decisions_before_after"][1]
        for observation in observations
    )
    checks = {
        "five_attempted_goals": len(observations) == 5,
        "all_expected_node_verdicts": all(item["verdicts_match"] for item in observations),
        "one_named_human_operator": len(actors) == 1
        and all(item.get("mode") == "human" for item in approvals)
        and all(item["approval_actors"] == list(actors) for item in observations),
        "all_five_operator_assessments_recorded": all(item is not None for item in assessments),
        "operator_false_denial_report_recorded": feedback_valid,
        "frozen_plan_conditions_for_all_five": all(
            item["plan_conditions_frozen"] for item in observations
        ),
        "at_least_three_independently_passed_and_useful": passed_and_useful >= 3,
        "zero_unauthorized_actions": all(not item["authorization_gaps"] for item in observations),
        "zero_false_passed": false_passed == 0,
        "complete_lineage_for_all_five": all(item["lineage_complete"] for item in observations),
        "fresh_process_replay_without_duplicate_work": replay_ok,
    }
    restore_path = EVIDENCE_ROOT / "pilot" / args.run_id / "backup_restore.json"
    backup_restore = (
        json.loads(restore_path.read_text(encoding="utf-8")) if restore_path.is_file() else {}
    )
    backup_record_trusted = (
        backup_restore.get("frozen_cases_sha256") == _sha(CASES_PATH.read_bytes())
        and backup_restore.get("frozen_gate_sha256") == _sha(GATE_PATH.read_bytes())
        and bool(backup_restore.get("sqlite_online_backup"))
        and bool(backup_restore.get("sidecar_backup"))
        and bool(backup_restore.get("restored_to_same_paths"))
        and bool(backup_restore.get("artifact_hashes_valid"))
        and bool(backup_restore.get("rollback_pair_preserved"))
        and not backup_restore.get("replay_new_event_types")
    )
    checks["backup_restore_record_valid"] = backup_record_trusted
    report = {
        "evidence_kind": "human_operator_pilot_scorecard",
        "frozen_cases_sha256": _sha(CASES_PATH.read_bytes()),
        "frozen_gate_sha256": _sha(GATE_PATH.read_bytes()),
        "run_id": args.run_id,
        "release_gate_complete": False,
        "operator_count": len(actors),
        "attempt_denominator": 5,
        "human_assessments": {
            "useful": sum(item is not None and item.get("useful") is True for item in assessments),
            "not_useful": sum(
                item is not None and item.get("useful") is False for item in assessments
            ),
            "missing": sum(item is None for item in assessments),
            "passed_and_useful": passed_and_useful,
        },
        "scorecard": {
            "completion_rate": sum(
                item["actual_node_verdicts"] == ["passed", "passed"] for item in observations
            )
            / 5,
            "failed_cases": sum(
                any(verdict == "failed" for verdict in item["actual_node_verdicts"])
                for item in observations
            ),
            "clarification_count": sum(item["clarification_count"] for item in observations),
            "operator_interventions": {
                "count": 5,
                "denominator": 5,
                "kind": "harness added software-domain prefix required by current Intent route",
            },
            "approval_time_seconds": {
                "denominator": 5,
                "human_review_time": None,
                "status": "unknown; chat review start was not durably timestamped",
                "approval_exchange_seconds_per_case": [
                    item["approval_time_seconds"] for item in observations
                ],
            },
            "false_denials": {
                "count": feedback["false_denials"] if feedback_valid else None,
                "denominator": 5,
                "status": "operator reported" if feedback_valid else "unknown",
            },
            "recovery_outcomes": {
                "denominator": sum(len(item["recovery_decisions"]) for item in observations),
                "decisions": {
                    decision: sum(
                        item["recovery_decisions"].count(decision) for item in observations
                    )
                    for decision in sorted(
                        {
                            decision
                            for item in observations
                            for decision in item["recovery_decisions"]
                        }
                    )
                },
            },
            "latency_seconds": {
                "denominator": 5,
                "per_case": [item["run_latency_seconds"] for item in observations],
            },
            "provider_cost": {"value": None, "status": "unknown; no provider cost source"},
            "evidence_completeness": {
                "complete": sum(item["lineage_complete"] for item in observations),
                "denominator": 5,
            },
        },
        "backup_restore_record": backup_restore,
        "checks": checks,
        "technical_pilot_thresholds_met": all(checks.values()) and backup_record_trusted,
        "cases": observations,
    }
    target = EVIDENCE_ROOT / "pilot" / args.run_id / "scorecard.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "scorecard": str(target),
                "technical_pilot_thresholds_met": report["technical_pilot_thresholds_met"],
                "checks": checks,
            },
            indent=2,
        )
    )
    return 0 if all(checks.values()) else 1


def _trace(events: tuple[Any, ...]) -> list[dict[str, Any]]:
    rows = []
    for event in events:
        if event.producer == "repository_action" or event.type.startswith(
            (
                "policy.",
                "approval.",
                "validation.",
                "knowledge.",
                "pipeline.",
                "interaction.",
                "runtime.",
                "execution.",
                "planning.",
                "recovery.",
                "intent.",
                "engineering.",
                "estimation.",
                "context.",
                "reflection.",
            )
        ):
            raw = event.payload
            safe = {key: raw[key] for key in SAFE_EVENT_FIELDS if key in raw}
            if event.type == "repository_action.requested":
                safe["input_digest"] = raw.get("input_digest")
                action = raw.get("action")
                if isinstance(action, dict):
                    safe["action"] = {
                        key: action.get(key)
                        for key in ("kind", "path", "command_id", "work_item_key")
                        if key in action
                    }
            if event.type == "repository_action.completed" and isinstance(raw.get("outcome"), dict):
                outcome = raw["outcome"]
                safe["outcome"] = {
                    key: outcome.get(key)
                    for key in (
                        "kind",
                        "status",
                        "input_digest",
                        "before_sha256",
                        "after_sha256",
                        "path",
                        "command_id",
                        "exit_status",
                        "event_refs",
                    )
                    if key in outcome
                }
            if isinstance(safe.get("argv"), list):
                argv = list(safe["argv"])
                safe["argv"] = [
                    "<python>"
                    if index == 0
                    else "<phase6_test_runner.py>"
                    if index == 1 and "phase6_test_runner.py" in str(value)
                    else value
                    for index, value in enumerate(argv)
                ]
            if event.type == "repository_action.artifact":
                safe.pop("path", None)
                safe["artifact_ref"] = f"<artifact>/{raw.get('artifact_id', '')}"
            if event.type == "policy.evaluated":
                safe["action_class"] = raw.get("action_class")
                attributes = raw.get("attributes")
                if isinstance(attributes, dict):
                    safe["policy_binding"] = {
                        key: (
                            "<fixture-workspace>"
                            if key == "workspace_root"
                            else attributes.get(key)
                        )
                        for key in (
                            "action_id",
                            "input_digest",
                            "workspace_root",
                            "plan_identity",
                            "pipeline_session",
                            "node",
                            "actor",
                            "request_identity",
                            "work_item_key",
                        )
                        if key in attributes
                    }
            if event.type.startswith("validation.") and isinstance(raw.get("report"), dict):
                report = raw["report"]
                safe["report"] = {
                    key: report.get(key)
                    for key in (
                        "identity",
                        "decision",
                        "session_ref",
                        "work_package_ref",
                        "evidence_refs",
                    )
                    if key in report
                }
            rows.append(
                {
                    "id": event.identifier,
                    "type": event.type,
                    "producer": event.producer,
                    "correlation": event.correlation_identifier,
                    "facts": safe,
                }
            )
    return rows


def _node_verdicts(events: tuple[Any, ...]) -> list[dict[str, str]]:
    plan_event = next(
        event for event in events if event.type == "planning.execution_plan_assembled"
    )
    raw_plan = plan_event.payload["execution_plan"]
    package_names = {
        package["identifier"]: package["objective"] for package in raw_plan.get("work_packages", [])
    }
    reports = []
    for event in events:
        if event.type not in {"validation.completed", "validation.failed"}:
            continue
        report = event.payload.get("report", {})
        package_ref = report.get("work_package_ref", {})
        package_id = package_ref.get("identifier", "")
        objective = package_names.get(package_id, "unknown")
        node = "edit" if "Apply the proposed repair" in objective else "test"
        reports.append(
            {
                "node": node,
                "work_package": package_id,
                "verdict": str(report.get("decision", "unknown")),
                "report_id": str(report.get("identity", "")),
            }
        )
    return sorted(reports, key=lambda row: (0 if row["node"] == "edit" else 1, row["report_id"]))


def _action_authorization_gaps(events: tuple[Any, ...]) -> list[str]:
    errors = []
    for started in (event for event in events if event.type == "repository_action.started"):
        action_id = started.payload.get("action_id")
        policy_id = started.payload.get("policy_event")
        policy = next((event for event in events if event.identifier == policy_id), None)
        if (
            policy is None
            or policy.type != "policy.evaluated"
            or policy.payload.get("decision") != "allow"
            or policy.payload.get("action_class") != "repository_action"
            or policy.payload.get("attributes", {}).get("action_id") != action_id
            or policy.payload.get("attributes", {}).get("input_digest")
            != started.payload.get("input_digest")
            or policy.payload.get("attributes", {}).get("plan_identity")
            != started.payload.get("plan")
            or policy.payload.get("attributes", {}).get("pipeline_session")
            != started.payload.get("pipeline_session")
            or policy.payload.get("attributes", {}).get("node") != started.payload.get("node")
        ):
            errors.append(f"{action_id}: missing matching Policy ALLOW")
        if started.payload.get("kind") == "write_file":
            approval_id = started.payload.get("approval_event")
            approval = next((event for event in events if event.identifier == approval_id), None)
            if (
                approval is None
                or approval.type != "approval.approved"
                or approval.payload.get("node") != started.payload.get("node")
                or approval.payload.get("session") != started.payload.get("pipeline_session")
            ):
                errors.append(f"{action_id}: missing human approval fact")
    return errors


def _case_observation(
    case: dict[str, Any], db: Path, workspace: Path, run_id: str
) -> dict[str, Any]:
    context = _context(db)
    try:
        events = tuple(context.infrastructure.event_store.read_all())
        case_events = tuple(
            event
            for event in events
            if event.correlation_identifier == f"cor-{_identity(run_id, str(case['id']))}"
        )
        verdicts = _node_verdicts(case_events)
        expected = list(case["expected_verdicts"])
        actual = [row["verdict"] for row in verdicts]
        by_type: dict[str, list[Any]] = {}
        for event in case_events:
            by_type.setdefault(event.type, []).append(event)
        pending = next(iter(by_type.get("approval.pending", [])), None)
        approved = next(iter(by_type.get("approval.approved", [])), None)
        first = next(iter(by_type.get("interaction.session_started", [])), None)
        last_responses = by_type.get("interaction.response_recorded", [])
        approval_seconds = (
            (
                datetime.fromisoformat(approved.timestamp)
                - datetime.fromisoformat(pending.timestamp)
            ).total_seconds()
            if pending is not None and approved is not None
            else None
        )
        latency_seconds = (
            (
                datetime.fromisoformat(last_responses[-1].timestamp)
                - datetime.fromisoformat(first.timestamp)
            ).total_seconds()
            if first is not None and last_responses
            else None
        )
        action_ids = {
            event.payload.get("action_id")
            for event in case_events
            if event.type == "repository_action.started"
        }
        report_ids = {row["report_id"] for row in verdicts}
        artifact_ids = {
            event.identifier for event in case_events if event.type == "repository_action.artifact"
        }
        referenced_artifacts = {
            reference
            for event in case_events
            if event.type == "repository_action.completed"
            for reference in event.payload.get("outcome", {}).get("event_refs", [])
        }
        authorization_gaps = _action_authorization_gaps(case_events)
        recovery_decisions = [
            str(event.payload.get("decision", "unknown"))
            for event in case_events
            if event.type == "recovery.decision_created"
        ]
        return {
            "case_id": case["id"],
            "expected_node_verdicts": expected,
            "actual_node_verdicts": actual,
            "verdicts_match": actual == expected,
            "runtime_terminals": [
                {
                    "type": event.type,
                    "session": event.payload.get("session"),
                    "node": event.payload.get("node"),
                }
                for event in case_events
                if event.type in {"runtime.completed", "runtime.failed"}
            ],
            "action_starts": sum(
                event.type == "repository_action.started" for event in case_events
            ),
            "authorization_gaps": authorization_gaps,
            "approval_actors": sorted(
                {
                    str(event.payload.get("decided_by"))
                    for event in by_type.get("approval.approved", [])
                    if event.payload.get("decided_by")
                }
            ),
            "lineage_complete": (
                len(report_ids) == 2
                and len(action_ids) == 2
                and bool(referenced_artifacts)
                and referenced_artifacts <= artifact_ids
                and not authorization_gaps
            ),
            "approval_time_seconds": approval_seconds,
            "run_latency_seconds": latency_seconds,
            "clarification_count": sum(
                len(event.payload.get("clarifications", []))
                for event in case_events
                if event.type == "intent.resolved"
            ),
            "recovery_decisions": recovery_decisions,
            "knowledge_disposition": {
                "accepted": sum(
                    event.type == "knowledge.candidate_accepted" for event in case_events
                ),
                "rejected": sum(
                    event.type == "knowledge.candidate_rejected" for event in case_events
                ),
                "none": not any(
                    event.type.startswith("knowledge.candidate_") for event in case_events
                ),
            },
            "file_sha256_before": json.loads(
                (Path(f"{db}.phase6") / str(case["id"]) / "before_files.json").read_text(
                    encoding="utf-8"
                )
            ),
            "file_sha256_after": _manifest(workspace),
            "event_trace": _trace(case_events),
            "validation_report_ids": [row["report_id"] for row in verdicts],
        }
    finally:
        context.infrastructure.close()


def _plan_is_frozen_correctly(case: dict[str, Any], review: dict[str, Any]) -> bool:
    nodes = review.get("nodes", [])
    if len(nodes) != 2:
        return False
    edit = next((node for node in nodes if node.get("work_package_id", "").endswith("-edit")), None)
    test = next((node for node in nodes if node.get("work_package_id", "").endswith("-test")), None)
    if edit is None or test is None:
        return False
    edit_conditions = edit.get("completion_criteria", {}).get("outcome_conditions", [])
    test_conditions = test.get("completion_criteria", {}).get("outcome_conditions", [])
    expected_command = (
        "phase6-fixture-tests" if case["junit_report"] else "phase6-fixture-tests-no-report"
    )
    return (
        any(
            item.get("type") == "file_sha256"
            and item.get("path") == "src/repair.py"
            and item.get("expected_sha256") == _sha(str(case["expected_source"]))
            for item in edit_conditions
        )
        and any(
            item.get("type") == "junit_xml"
            and item.get("command_id") == expected_command
            and item.get("paths") == ["reports/phase6-junit.xml"]
            for item in test_conditions
        )
        and test.get("dependencies") == [[edit.get("node_id"), test.get("node_id")]]
        and {"src/repair.py", "tests/test_repair.py"}.issubset(
            {reference.get("identifier") for reference in review.get("source_refs", [])}
        )
    )


def _run_child(*arguments: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), *arguments],
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"pilot subprocess failed ({completed.returncode}): {completed.stderr[-2000:]}"
        )
    try:
        return cast(dict[str, Any], json.loads(completed.stdout))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"pilot subprocess returned invalid JSON: {completed.stdout[-1000:]}"
        ) from exc


def _backup_restore(db: Path, case: dict[str, Any], workspace: Path, run_id: str) -> dict[str, Any]:
    """Exercise SQLite online backup and sidecar restore at their original checked paths."""
    rehearsal_root = db.parent.resolve()
    backup_root = db.parent / f"{db.stem}.backup-check"
    backup_db = backup_root / db.name
    backup_sidecar = Path(f"{backup_db}.action_artifacts")
    original_sidecar = Path(f"{db}.action_artifacts")
    backup_root.mkdir(parents=True, exist_ok=False)
    source = sqlite3.connect(db)
    try:
        target = sqlite3.connect(backup_db)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()
    shutil.copytree(original_sidecar, backup_sidecar)

    displaced_db = db.with_suffix(db.suffix + ".pilot-displaced")
    displaced_sidecar = Path(f"{original_sidecar}.pilot-displaced")
    failed_db = backup_root / "failed-restore.sqlite3"
    failed_sidecar = backup_root / "failed-restore.action_artifacts"
    for candidate in (
        backup_root,
        backup_db,
        backup_sidecar,
        original_sidecar,
        displaced_db,
        displaced_sidecar,
        failed_db,
        failed_sidecar,
    ):
        if not candidate.resolve().is_relative_to(rehearsal_root):
            raise ValueError("backup/restore path escaped the disposable rehearsal root")
    if displaced_db.exists() or displaced_sidecar.exists():
        raise RuntimeError("backup restore destination already has displaced data")
    # Keep original files as rollback copies until the restored log and artifacts validate.
    db.replace(displaced_db)
    original_sidecar.replace(displaced_sidecar)
    try:
        shutil.copy2(backup_db, db)
        shutil.copytree(backup_sidecar, original_sidecar)
        context = _context(db)
        try:
            events = tuple(context.infrastructure.event_store.read_all())
            artifact_events = [
                event for event in events if event.type == "repository_action.artifact"
            ]
            valid_artifacts = []
            for event in artifact_events:
                path = Path(str(event.payload.get("path", "")))
                digest = str(event.payload.get("sha256", ""))
                valid_artifacts.append(
                    path.is_file()
                    and path.resolve().is_relative_to(original_sidecar.resolve())
                    and _sha(path.read_bytes()) == digest
                )
        finally:
            context.infrastructure.close()
        if not valid_artifacts or not all(valid_artifacts):
            raise RuntimeError("restored artifact sidecar did not match durable event hashes")
        replay = _run_child(
            "replay",
            "--case-id",
            str(case["id"]),
            "--run-id",
            run_id,
            "--workspace",
            str(workspace),
            "--db",
            str(db),
        )
        if replay["new_event_types"]:
            raise RuntimeError("restored replay emitted new durable events")
    except Exception:
        # Preserve both the failed restored copy and the original rollback pair for inspection.
        if db.exists():
            db.replace(failed_db)
        if original_sidecar.exists():
            original_sidecar.replace(failed_sidecar)
        displaced_db.replace(db)
        displaced_sidecar.replace(original_sidecar)
        raise
    return {
        "sqlite_online_backup": True,
        "sidecar_backup": True,
        "restored_to_same_paths": True,
        "artifact_count": len(artifact_events),
        "artifact_hashes_valid": all(valid_artifacts),
        "artifact_validation": valid_artifacts,
        "replay_new_event_types": replay["new_event_types"],
        "rollback_pair_preserved": displaced_db.is_file() and displaced_sidecar.is_dir(),
        "relocation_supported": False,
    }


def _rehearse(args: argparse.Namespace) -> int:
    cases = _cases()["cases"]
    run_id = f"rehearsal-{uuid.uuid4().hex[:10]}"
    root = Path(tempfile.mkdtemp(prefix="nexus-phase6-")).resolve()
    db = root / "pilot.sqlite3"
    observations: list[dict[str, Any]] = []
    for case in cases:
        workspace = root / "workspaces" / str(case["id"])
        workspace.parent.mkdir(parents=True, exist_ok=True)
        prepared = _run_child(
            "prepare",
            "--case-id",
            str(case["id"]),
            "--run-id",
            run_id,
            "--workspace",
            str(workspace),
            "--db",
            str(db),
        )
        reviewed = json.loads(
            (Path(f"{db}.phase6") / str(case["id"]) / "plan_review.json").read_text(
                encoding="utf-8"
            )
        )
        prepare_trace = json.loads(
            (Path(f"{db}.phase6") / str(case["id"]) / "prepare_trace.json").read_text(
                encoding="utf-8"
            )
        )
        approved = _run_child(
            "approve",
            "--case-id",
            str(case["id"]),
            "--run-id",
            run_id,
            "--workspace",
            str(workspace),
            "--db",
            str(db),
            "--simulate-approval",
        )
        replay = _run_child(
            "replay",
            "--case-id",
            str(case["id"]),
            "--run-id",
            run_id,
            "--workspace",
            str(workspace),
            "--db",
            str(db),
        )
        observation = _case_observation(case, db, workspace, run_id)
        observation["prepare_status"] = prepared.get("status")
        observation["plan_review"] = reviewed
        observation["plan_conditions_frozen"] = _plan_is_frozen_correctly(case, reviewed)
        observation["prepare_action_starts"] = sum(
            row["type"] == "repository_action.started" for row in prepare_trace
        )
        observation["prepare_trace"] = prepare_trace
        observation["prepare_clarification_count"] = reviewed["clarification_count"]
        observation["approval_mode"] = approved.get("mode")
        observation["replay"] = replay
        observations.append(observation)

    restore = _backup_restore(db, cases[0], root / "workspaces" / str(cases[0]["id"]), run_id)
    checks = {
        "all_expected_verdicts": all(item["verdicts_match"] for item in observations),
        "zero_unauthorized_actions": all(not item["authorization_gaps"] for item in observations),
        "zero_false_passed": all(
            not (verdict == "passed" and expected != "passed")
            for case, item in zip(cases, observations, strict=True)
            for verdict, expected in zip(
                item["actual_node_verdicts"], case["expected_verdicts"], strict=True
            )
        ),
        "five_distinct_goals": len({item["case_id"] for item in observations}) == 5,
        "five_complete_lineages": all(item["lineage_complete"] for item in observations),
        "plan_conditions_frozen_before_approval": all(
            item["plan_conditions_frozen"] for item in observations
        ),
        "zero_action_starts_before_approval": all(
            item["prepare_action_starts"] == 0 for item in observations
        ),
        "exactly_two_action_starts_each": all(item["action_starts"] == 2 for item in observations),
        "simulated_approvals_only": all(
            item["approval_mode"] == "simulated" for item in observations
        ),
        "replay_no_new_events": all(not item["replay"]["new_event_types"] for item in observations),
        "replay_no_duplicate_work_or_verdicts": all(
            item["replay"]["action_starts_before_after"][0]
            == item["replay"]["action_starts_before_after"][1]
            and item["replay"]["runtime_starts_before_after"][0]
            == item["replay"]["runtime_starts_before_after"][1]
            and item["replay"]["validation_terminals_before_after"][0]
            == item["replay"]["validation_terminals_before_after"][1]
            and item["replay"]["model_call_events_before_after"][0]
            == item["replay"]["model_call_events_before_after"][1]
            and item["replay"]["knowledge_decisions_before_after"][0]
            == item["replay"]["knowledge_decisions_before_after"][1]
            for item in observations
        ),
        "backup_restore_artifacts_valid": restore["artifact_hashes_valid"],
    }
    report = {
        "evidence_kind": "automated_rehearsal",
        "frozen_cases_sha256": _sha(CASES_PATH.read_bytes()),
        "frozen_gate_sha256": _sha(GATE_PATH.read_bytes()),
        "human_pilot": False,
        "release_gate_complete": False,
        "run_id": run_id,
        "fixture_root": "<temporary-fixture-root>",
        "case_count": len(observations),
        "human_assessments": {"useful": 0, "not_useful": 0, "missing": 5},
        "scorecard": {
            "completion_rate": sum(
                item["actual_node_verdicts"] == ["passed", "passed"] for item in observations
            )
            / len(observations),
            "failed_cases": sum(
                any(value == "failed" for value in item["actual_node_verdicts"])
                for item in observations
            ),
            "clarification_count": sum(
                item["prepare_clarification_count"] for item in observations
            ),
            "intent_input_interventions": {
                "count": len(observations),
                "denominator": len(observations),
                "kind": "harness added the software-domain phrase before Intent",
            },
            "unprefixed_goal_attempt": "not exercised as a five-case comparison",
            "approval_time_seconds": {
                "denominator": len(observations),
                "measured_count": sum(
                    item["approval_time_seconds"] is not None for item in observations
                ),
                "per_case": [item["approval_time_seconds"] for item in observations],
                "mean": (
                    sum(
                        item["approval_time_seconds"]
                        for item in observations
                        if item["approval_time_seconds"] is not None
                    )
                    / sum(item["approval_time_seconds"] is not None for item in observations)
                    if any(item["approval_time_seconds"] is not None for item in observations)
                    else None
                ),
                "mode": "simulated approval timing; not human pilot timing",
            },
            "false_denials": {
                "count": None,
                "denominator": len(observations),
                "status": "unknown without operator classification",
            },
            "recovery_outcomes": {
                "denominator": sum(len(item["recovery_decisions"]) for item in observations),
                "decisions": {
                    decision: sum(
                        item["recovery_decisions"].count(decision) for item in observations
                    )
                    for decision in sorted(
                        {
                            decision
                            for item in observations
                            for decision in item["recovery_decisions"]
                        }
                    )
                },
            },
            "replay_success_rate": sum(
                not item["replay"]["new_event_types"] for item in observations
            )
            / len(observations),
            "replay_denominator": len(observations),
            "latency_seconds": {
                "denominator": len(observations),
                "per_case": [item["run_latency_seconds"] for item in observations],
            },
            "provider_cost": "unknown; no provider cost source",
            "evidence_completeness_rate": sum(item["lineage_complete"] for item in observations)
            / len(observations),
            "evidence_completeness_denominator": len(observations),
        },
        "metric_definitions": {
            "completion_rate": "goals with both expected node verdicts PASSED divided by five attempted goals",
            "failed_cases": "goals with at least one FAILED node verdict; expected probe failures remain counted",
            "clarification_count": "Intent clarification requests observed in durable intent.resolved events",
            "operator_interventions": "five harness-added software-domain phrases divided by five; recorded transformations, not operator clarifications",
            "approval_time_seconds": "approval.approved timestamp minus approval.pending timestamp; simulated approval in rehearsal",
            "false_denials": "unknown in rehearsal because no human classified a denied action as false",
            "recovery_outcomes": "counts of durable recovery.decision_created decisions across ten work nodes",
            "replay_success_rate": "case replays with no new event IDs divided by five attempted goals",
            "latency_seconds": "interaction.session_started to last interaction.response_recorded timestamp per goal",
            "provider_cost": "unknown; no provider cost source is instrumented",
            "evidence_completeness_rate": "goals with two validation reports, two actions, artifact references resolving to action artifact events, and no authorization gaps divided by five",
        },
        "schema_migration": "not applicable; this rehearsal introduces no durable schema changes",
        "backup_restore": restore,
        "checks": checks,
        "cases": observations,
        "thresholds": _cases()["thresholds"],
    }
    report["release_gate_status"] = "rehearsal_only" if all(checks.values()) else "failed_rehearsal"
    output = (
        Path(args.output).resolve()
        if args.output
        else EVIDENCE_ROOT / "rehearsal" / f"{run_id}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "report": str(output),
                "release_gate_status": report["release_gate_status"],
                "checks": checks,
            },
            indent=2,
        )
    )
    return 0 if all(checks.values()) else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "approve", "replay"):
        sub = commands.add_parser(name)
        sub.add_argument("--case-id", required=True)
        sub.add_argument("--run-id", required=True)
        sub.add_argument("--workspace", required=True)
        sub.add_argument("--db", required=True)
        if name == "approve":
            sub.add_argument("--simulate-approval", action="store_true")
            sub.add_argument("--operator", default="operator")
    assess = commands.add_parser("assess")
    assess.add_argument("--case-id", required=True)
    assess.add_argument("--run-id", required=True)
    assess.add_argument("--db", required=True)
    assess.add_argument("--operator", required=True)
    scorecard = commands.add_parser("scorecard")
    scorecard.add_argument("--run-id", required=True)
    scorecard.add_argument("--db", required=True)
    scorecard.add_argument("--workspace-root", required=True)
    rehearse = commands.add_parser("rehearse")
    rehearse.add_argument("--output")
    return parser


def main() -> int:
    args = _parser().parse_args()
    return {
        "prepare": _prepare,
        "approve": _approve,
        "replay": _replay,
        "assess": _assess,
        "scorecard": _scorecard,
        "rehearse": _rehearse,
    }[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
