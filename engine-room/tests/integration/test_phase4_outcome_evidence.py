from __future__ import annotations

import gc
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from nexus_core.domain.event import Event
from nexus_execution.actions import RepositoryAction
from nexus_human_interaction import build_human_interaction
from nexus_human_interaction.composition import HumanInteractionContext
from nexus_human_interaction.model import InteractionResponse, OperatorRequest
from nexus_infra import build_durable_infrastructure, build_infrastructure
from nexus_planning import WorkItemSpec

PASSING_XML = '<testsuite><testcase name="works"/></testsuite>'
FAILING_XML = '<testsuite><testcase name="works"><failure message="assertion failed" /></testcase></testsuite>'


def _submit(
    tmp_path: Path,
    case_id: str,
    *,
    file_condition: bool,
    reports: tuple[str, ...],
    contents: tuple[str, ...],
    db_path: Path | None = None,
) -> tuple[HumanInteractionContext, InteractionResponse, Event, OperatorRequest]:
    workspace = tmp_path / "workspace"
    artifacts = tmp_path / "action-artifacts"
    workspace.mkdir()
    (workspace / "README.md").write_text("phase4 fixture\n", encoding="utf-8")
    fails = contents[0] == FAILING_XML
    assertion = "self.assertEqual(1, 2)" if fails else "self.assertEqual(1, 1)"
    code_lines = [
        "from pathlib import Path",
        "import sys, unittest",
        "class Fixture(unittest.TestCase):",
        "    def test_expected(self): " + assertion,
        "suite = unittest.defaultTestLoader.loadTestsFromTestCase(Fixture)",
        "result = unittest.TestResult(); suite.run(result)",
        "failed = bool(result.failures or result.errors)",
        "failure = '<failure message=\"assertion failed\" />' if failed else ''",
        "report = '<testsuite><testcase name=\"works\">' + failure + '</testcase></testsuite>'",
    ]
    for relative, content in zip(reports, contents, strict=True):
        if case_id != "E3":
            source = "report" if relative == reports[0] else repr(content)
            code_lines.append(
                f"p = Path({relative!r}); p.parent.mkdir(parents=True, exist_ok=True); p.write_text({source}, encoding='utf-8')"
            )
    code_lines.append("sys.stdout.write(report)")
    command = (sys.executable, "-c", "\n".join(code_lines))
    identity = f"phase4-{case_id.lower()}"
    conditions: list[dict[str, object]] = [
        {"id": "junit", "type": "junit_xml", "command_id": "fixture-test", "paths": list(reports)}
    ]
    if file_condition:
        conditions.insert(
            0,
            {
                "id": "readme",
                "type": "file_sha256",
                "path": "README.md",
                "expected_sha256": hashlib.sha256(
                    (workspace / "README.md").read_bytes()
                ).hexdigest(),
            },
        )
    item = WorkItemSpec(
        key="respond",
        objective="Run the registered fixture test and check the requested evidence.",
        capability_requirements=("repository_action",),
        completion_criteria={"outcome_conditions": conditions},
    )
    action = RepositoryAction.run_test(
        workspace_root=str(workspace),
        command_id="fixture-test",
        actor="phase4-test",
        request_identity=identity,
        resolved_argv=command,
    )
    operator_request = OperatorRequest(
        identity=identity,
        request_text="Run the fixture test and verify the registered completion conditions.",
        work_items=(item,),
        knowledge_subject="phase4 test",
        scope="phase4",
        repository_root=str(workspace),
        repository_actions=(action,),
    )
    context = build_human_interaction(
        build_durable_infrastructure(str(db_path)) if db_path else build_infrastructure(),
        learning=False,
        action_command_allowlist={"fixture-test": command},
        action_artifact_directory=str(artifacts),
    )
    response = context.facade.submit(operator_request)
    terminal = next(
        event
        for event in context.infrastructure.event_store.read_all()
        if event.type in {"validation.completed", "validation.failed"}
    )
    return context, response, terminal, operator_request


@pytest.mark.parametrize(
    ("case_id", "file_condition", "reports", "contents", "expected"),
    [
        ("E1", True, ("reports/junit.xml",), (PASSING_XML,), "passed"),
        ("E2", False, ("reports/junit.xml",), (FAILING_XML,), "failed"),
        ("E3", False, ("reports/missing.xml",), (PASSING_XML,), "requires_review"),
        ("E4", True, ("reports/junit.xml",), (FAILING_XML,), "partial"),
        (
            "E5",
            False,
            ("reports/one.xml", "reports/two.xml"),
            (PASSING_XML, FAILING_XML),
            "requires_review",
        ),
    ],
)
def test_phase4_frozen_case_through_operator_path(
    tmp_path: Path,
    case_id: str,
    file_condition: bool,
    reports: tuple[str, ...],
    contents: tuple[str, ...],
    expected: str,
) -> None:
    context, response, terminal, _request = _submit(
        tmp_path,
        case_id,
        file_condition=file_condition,
        reports=reports,
        contents=contents,
        db_path=tmp_path / "events.sqlite",
    )
    assert terminal.payload["decision"] == expected
    assert response.validation_decisions == (expected,)
    assert response.runtime_completed
    assert response.outcome_accepted is (expected == "passed")
    plan = response.execution_plan
    assert plan is not None
    package = plan.work_packages[0]
    frozen = package.completion_criteria["outcome_conditions"]
    assert frozen
    events = tuple(context.infrastructure.event_store.read_all())
    started = next(event for event in events if event.type == "repository_action.started")
    assert started.payload["action_id"] == next(
        event.payload["action_id"]
        for event in events
        if event.type == "repository_action.requested"
    )
    assert (
        terminal.payload["report"]["identity"]
        == f"vr-{terminal.payload['report']['session_ref']['identifier']}"
    )
    completed = next(event for event in events if event.type == "repository_action.completed")
    if case_id in {"E2", "E4"}:
        assert completed.payload["outcome"]["exit_status"] == 0
        runtime_evidence = next(
            item
            for event in events
            if event.type == "validation.evidence_collected"
            for item in event.payload["evidence"]
            if item["source"] == "runtime_metadata"
        )
        assert runtime_evidence["observed"]["exit_status"] == 0
    if case_id == "E3":
        outcome_rule = next(
            item
            for item in terminal.payload["report"]["rule_results"]
            if item["rule_id"] == "outcome_conditions"
        )
        assert "missing" in outcome_rule["rationale"]
    if case_id == "E5":
        outcome_rule = next(
            item
            for item in terminal.payload["report"]["rule_results"]
            if item["rule_id"] == "outcome_conditions"
        )
        assert "conflict" in outcome_rule["rationale"]
        assert len(outcome_rule["evidence_refs"]) == 2
    expected_report_path = tmp_path / "expected-report.json"
    expected_report_path.write_text(
        json.dumps(terminal.payload["report"], sort_keys=True), encoding="utf-8"
    )
    replay_session = str(terminal.payload["report"]["session_ref"]["identifier"])
    del context
    gc.collect()
    replay_process = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.phase4_replay_worker",
            "--db",
            str(tmp_path / "events.sqlite"),
            "--expected",
            str(expected_report_path),
            "--session",
            replay_session,
        ],
        cwd=Path(__file__).resolve().parents[2],
        check=True,
        capture_output=True,
        text=True,
    )
    replay = json.loads(replay_process.stdout)
    assert replay["same_report"] is True
    assert replay["decision"] == expected
    assert replay["operator_restart_decision"] == expected
    assert replay["operator_restart_runtime_completed"] is True
    assert replay["same_store_restart_decision"] == expected
    assert (
        replay["same_store_restart_validation_terminals_before"]
        == replay["same_store_restart_validation_terminals_after"]
        == 1
    )
    assert (
        replay["same_store_restart_action_starts_before"]
        == replay["same_store_restart_action_starts_after"]
        == 1
    )
    assert (
        replay["same_store_restart_responses_before"]
        == replay["same_store_restart_responses_after"]
        == 1
    )
    assert replay["validation_terminals_before"] == replay["validation_terminals_after"] == 1
    assert replay["action_starts_before"] == replay["action_starts_after"] == 1
    assert replay["operator_restart_pipeline_entered"] is True
    assert (
        replay["operator_restart_validation_terminals_before"]
        == replay["operator_restart_validation_terminals_after"]
        == 1
    )
    assert (
        replay["operator_restart_action_starts_before"]
        == replay["operator_restart_action_starts_after"]
        == 1
    )
    assert replay["operator_restart_responses_after"] == 1
