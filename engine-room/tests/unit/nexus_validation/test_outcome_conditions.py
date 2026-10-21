from __future__ import annotations

import hashlib
from pathlib import Path

from nexus_core.contracts.base import Reference
from nexus_core.domain.event import Event
from nexus_execution.actions.boundary import RepositoryAction
from nexus_validation.outcome_evidence import OutcomeConditionEvaluator
from nexus_validation.rules import RuleContext, ValidationPolicy
from nexus_validation.vocabulary import RuleOutcome
from tests.unit.nexus_validation.helpers import execution_result, val_work_package


def _event(identifier: str, event_type: str, payload: dict[str, object]) -> Event:
    return Event(
        identifier=identifier,
        type=event_type,
        version="1",
        timestamp="2026-01-01T00:00:00Z",
        producer="repository_action",
        correlation_identifier="cor-phase4",
        execution_identifier=None,
        payload=payload,
        source="nexus_execution.actions",
    )


def _action_events(root: Path, output: str, reports: tuple[str, ...]) -> tuple[Event, ...]:
    command_id = "fixture-test"
    action = RepositoryAction.run_test(
        workspace_root=str(root),
        command_id=command_id,
        actor="operator",
        request_identity="case-e1",
        resolved_argv=("python", "fixture-test"),
    )
    digest = action.input_digest
    for relative, content in zip(reports, (output, *([""] * (len(reports) - 1))), strict=True):
        path = root / relative
        if "missing" not in path.name and not any(
            part.is_symlink() for part in (path, *path.parents)
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    artifact_root = root.parent / "artifacts" / action.identity
    artifact_root.mkdir(parents=True)
    output_path = artifact_root / f"output-{hashlib.sha256(output.encode()).hexdigest()}.txt"
    output_path.write_text(output, encoding="utf-8")
    artifact_id = f"evt-{action.identity}-artifact-output"
    outcome_ref = "evt-" + action.identity + "-completed"
    return (
        _event(
            f"evt-{action.identity}-requested",
            "repository_action.requested",
            {
                "action_id": action.identity,
                "action": action.model_dump(mode="json"),
                "input_digest": digest,
            },
        ),
        _event(
            f"evt-{action.identity}-started",
            "repository_action.started",
            {
                "action_id": action.identity,
                "input_digest": digest,
                "workspace_root": str(root),
                "plan": "plan-e1",
                "node": "node-e1",
                "pipeline_session": "pipe-case-e1",
            },
        ),
        _event(
            artifact_id,
            "repository_action.artifact",
            {
                "action_id": action.identity,
                "artifact_id": f"{action.identity}-output",
                "kind": "action_output",
                "path": str(output_path),
                "sha256": hashlib.sha256(output.encode()).hexdigest(),
            },
        ),
        _event(
            outcome_ref,
            "repository_action.completed",
            {
                "action_id": action.identity,
                "input_digest": digest,
                "plan": "plan-e1",
                "node": "node-e1",
                "pipeline_session": "pipe-case-e1",
                "outcome": {
                    "action_id": action.identity,
                    "kind": "run_test",
                    "status": "completed",
                    "input_digest": digest,
                    "workspace_root": str(root),
                    "command_id": command_id,
                    "argv": ["python", "fixture-test"],
                    "exit_status": 0,
                    "output_ref": artifact_id,
                },
            },
        ),
    )


def _context(
    root: Path, reports: tuple[str, ...], output: str, *, runtime_node: str = "node-e1"
) -> RuleContext:
    events = _action_events(root, output, reports)
    result = execution_result()
    runtime_event = _event(
        f"evt-{result.session_ref.identifier}-created-0000",
        "runtime.session_created",
        {"node": runtime_node, "package": "actuation-pkg-session-node-e1", "attempt": 1},
    ).model_copy(update={"producer": "runtime", "source": "nexus_runtime"})
    events = (*events, runtime_event)
    criteria = {
        "outcome_conditions": [
            {
                "id": "tests",
                "type": "junit_xml",
                "command_id": "fixture-test",
                "paths": list(reports),
            }
        ]
    }
    package = val_work_package(completion_criteria=criteria).model_copy(
        update={
            "parent_plan": Reference(target_type="plan", identifier="plan-e1"),
            "inputs": (
                Reference(
                    target_type="action_request",
                    identifier=str(events[0].payload["action_id"]),
                ),
            ),
        }
    )
    return RuleContext(
        result=result,
        work_package=package,
        evidence=(),
        policy=ValidationPolicy(
            require_explicit_conditions=True,
            action_artifact_directory=str(root.parent / "artifacts"),
        ),
        events=events,
    )


def test_junit_failure_overrides_zero_exit_and_is_traceable(tmp_path: Path) -> None:
    report = (
        '<testsuite><testcase name="x"><failure message="no">bad</failure></testcase></testsuite>'
    )
    ctx = _context(tmp_path, ("reports/junit.xml",), report)
    result, evidence = OutcomeConditionEvaluator().evaluate(ctx)
    assert result.outcome is RuleOutcome.VIOLATED
    assert evidence[0].observed["failures"] == 1
    assert ctx.result.exit_status == 0
    assert evidence[0].derived_from


def test_two_valid_reports_that_disagree_require_review(tmp_path: Path) -> None:
    passing = '<testsuite><testcase name="x"/></testsuite>'
    failing = '<testsuite><testcase name="x"><failure/></testcase></testsuite>'
    reports = ("reports/one.xml", "reports/two.xml")
    ctx = _context(tmp_path, reports, passing)
    # Both named files have to be valid and independently hashed; distinct content is retained.
    (tmp_path / reports[1]).write_text(failing, encoding="utf-8")
    result, evidence = OutcomeConditionEvaluator().evaluate(ctx)
    assert result.outcome is RuleOutcome.INSUFFICIENT_EVIDENCE
    assert "conflict" in result.rationale
    assert len(evidence) == 2


def test_absent_report_requires_review_even_when_stdout_is_valid(tmp_path: Path) -> None:
    report = '<testsuite><testcase name="x"/></testsuite>'
    ctx = _context(tmp_path, ("reports/missing.xml",), report)
    result, _evidence = OutcomeConditionEvaluator().evaluate(ctx)
    assert result.outcome is RuleOutcome.INSUFFICIENT_EVIDENCE


def test_runtime_session_node_mismatch_requires_review(tmp_path: Path) -> None:
    report = '<testsuite><testcase name="x"/></testsuite>'
    ctx = _context(tmp_path, ("reports/junit.xml",), report, runtime_node="node-other")
    result, evidence = OutcomeConditionEvaluator().evaluate(ctx)
    assert result.outcome is RuleOutcome.INSUFFICIENT_EVIDENCE
    assert "action lineage" in result.rationale
    assert evidence == ()


def test_junit_skipped_testcase_requires_review(tmp_path: Path) -> None:
    report = '<testsuite><testcase name="x"><skipped/></testcase></testsuite>'
    ctx = _context(tmp_path, ("reports/junit.xml",), report)
    result, evidence = OutcomeConditionEvaluator().evaluate(ctx)
    assert result.outcome is RuleOutcome.INSUFFICIENT_EVIDENCE
    assert "skipped" in result.rationale
    assert evidence[0].observed["skipped"] == 1


def test_symlink_component_is_not_read(tmp_path: Path) -> None:
    report = '<testsuite><testcase name="x"/></testsuite>'
    outside = tmp_path.parent / "outside-junit.xml"
    outside.write_text(report, encoding="utf-8")
    (tmp_path / "link").symlink_to(outside)
    ctx = _context(tmp_path, ("link/junit.xml",), report)
    result, _evidence = OutcomeConditionEvaluator().evaluate(ctx)
    assert result.outcome is RuleOutcome.INSUFFICIENT_EVIDENCE
