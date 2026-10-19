"""Run the frozen Phase 3 constrained repository action acceptance gate."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from nexus_core.contracts.enums import PolicyCategory, PolicyDecision
from nexus_core.contracts.status import PolicyStatus
from nexus_core.domain.event import Event
from nexus_core.domain.policy import Policy
from nexus_engineering.model import EngineeringStrategy, ReasoningInputs
from nexus_engineering.reasoner import DeterministicReasoner
from nexus_execution.actions import RepositoryAction
from nexus_execution.actions.boundary import ActionDeniedError, RepositoryActionBoundary
from nexus_execution.actuation import ActuationControl
from nexus_human_interaction import build_human_interaction
from nexus_human_interaction.model import OperatorRequest
from nexus_infra import build_durable_infrastructure, build_infrastructure
from nexus_workflows.spine import SpineControl

ROOT = Path(__file__).resolve().parents[1]
PHASE3 = ROOT / "docs" / "phase3"
EVIDENCE = PHASE3 / "evidence"
FIXTURE_FILES = {
    "README.md": "# Phase 3 fixture\n\nBefore text.\n",
    "src/app.py": "def answer() -> int:\n    return 42\n",
    "tests/test_app.py": "from src.app import answer\n\ndef test_answer() -> None:\n    assert answer() == 42\n",
}


class _AutomaticReasoner:
    version = "phase3-eval-automatic"

    def reason(self, inputs: ReasoningInputs, *, now: str) -> EngineeringStrategy:
        strategy = DeterministicReasoner().reason(inputs, now=now)
        return strategy.model_copy(
            update={
                "autonomy_level": strategy.autonomy_level.model_copy(
                    update={"selection": ("autonomous",)}
                )
            }
        )


def _fixture(base: Path) -> tuple[Path, Path]:
    workspace = base / "fixture" / "workspace"
    outside = base / "fixture" / "outside"
    workspace.mkdir(parents=True)
    outside.mkdir(parents=True)
    for relative, content in FIXTURE_FILES.items():
        path = workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    (outside / "secret.txt").write_text("sentinel\n", encoding="utf-8")
    return workspace, outside


def _manifest(workspace: Path, outside: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for root in (workspace, outside):
        for path in sorted(root.rglob("*")):
            if path.is_file() and not path.is_symlink():
                relative = path.relative_to(root.parent).as_posix()
                result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _events(infra: Any) -> tuple[Event, ...]:
    return tuple(infra.event_store.read_all())


def _action_events(events: Sequence[Event]) -> list[dict[str, Any]]:
    safe_fields = {
        "action_id",
        "input_digest",
        "kind",
        "actor",
        "request_identity",
        "work_item_key",
        "workspace_root",
        "path",
        "command_id",
        "argv",
        "plan",
        "pipeline_session",
        "node",
        "policy_event",
        "approval_event",
        "decision",
        "reason",
        "status",
        "sha256",
        "artifact_id",
        "before_sha256",
        "after_sha256",
        "diff_ref",
        "output_ref",
        "exit_status",
    }
    selected = {
        "repository_action.requested",
        "repository_action.started",
        "repository_action.completed",
        "repository_action.denied",
        "repository_action.indeterminate",
        "repository_action.cancelled",
        "repository_action.artifact",
        "policy.evaluated",
        "approval.requested",
        "approval.pending",
        "approval.approved",
        "approval.denied",
        "planning.execution_plan_assembled",
        "interaction.request_submitted",
    }
    output = []
    for event in events:
        if event.type not in selected:
            continue
        payload = {key: value for key, value in event.payload.items() if key in safe_fields}
        outcome = event.payload.get("outcome")
        if isinstance(outcome, dict):
            payload["outcome"] = {
                key: outcome.get(key)
                for key in (
                    "action_id",
                    "kind",
                    "status",
                    "input_digest",
                    "actor",
                    "workspace_root",
                    "path",
                    "before_sha256",
                    "after_sha256",
                    "diff_ref",
                    "output_ref",
                    "command_id",
                    "argv",
                    "exit_status",
                    "event_refs",
                )
            }
            if "workspace_root" in payload["outcome"]:
                payload["outcome"]["workspace_root"] = "<workspace>"
            if payload["outcome"].get("argv"):
                payload["outcome"]["argv"] = ["<python>", *payload["outcome"]["argv"][1:]]
        if event.type == "repository_action.requested":
            raw_action = event.payload.get("action")
            if isinstance(raw_action, dict):
                payload["action"] = {
                    key: raw_action.get(key)
                    for key in (
                        "kind",
                        "workspace_root",
                        "path",
                        "command_id",
                        "resolved_argv",
                        "actor",
                    )
                }
                payload["action"]["workspace_root"] = "<workspace>"
                if payload["action"].get("resolved_argv"):
                    payload["action"]["resolved_argv"] = [
                        "<python>",
                        *payload["action"]["resolved_argv"][1:],
                    ]
        if "workspace_root" in payload:
            payload["workspace_root"] = "<workspace>"
        if event.type == "repository_action.artifact" and payload.get("path"):
            payload["path"] = f"<artifact>/{Path(str(payload['path'])).name}"
        output.append(
            {
                "id": event.identifier,
                "type": event.type,
                "producer": event.producer,
                "correlation": event.correlation_identifier,
                "payload": payload,
            }
        )
        if "argv" in payload and isinstance(payload["argv"], list) and payload["argv"]:
            payload["argv"] = [
                "<python>"
                if str(payload["argv"][0]).lower().endswith(("python.exe", "python"))
                else payload["argv"][0],
                *payload["argv"][1:],
            ]
    return output


def _request(identity: str, workspace: Path, action: RepositoryAction) -> OperatorRequest:
    return OperatorRequest(
        identity=identity,
        request_text=f"Perform the explicitly specified {action.kind} action on the fixture.",
        work_items=(),
        knowledge_subject="Phase 3 fixture action",
        scope="phase3-fixture",
        repository_root=str(workspace),
        repository_actions=(action,),
    )


def _make_action(identity: str, workspace: Path, kind: str, **kwargs: Any) -> RepositoryAction:
    common = {
        "workspace_root": str(workspace),
        "actor": "phase3-evaluator",
        "request_identity": identity,
        "correlation": f"cor-{identity}",
    }
    if kind == "write_file":
        return RepositoryAction.write(
            path=cast(str, kwargs["path"]), content=cast(str, kwargs["content"]), **common
        )
    if kind == "read_file":
        return RepositoryAction.read(path=cast(str, kwargs["path"]), **common)
    return RepositoryAction.run_test(
        command_id=cast(str, kwargs["command_id"]),
        resolved_argv=cast(tuple[str, ...], kwargs.get("argv", ())),
        **common,
    )


def _checks(
    case_id: str, case_name: str, observed: dict[str, Any], failures: list[str]
) -> dict[str, Any]:
    return {
        "id": case_id,
        "name": case_name,
        "passed": not failures,
        "failures": failures,
        "observed": observed,
    }


def _cli_run(
    db: Path,
    cwd: Path,
    *args: str,
    extra_env: dict[str, str] | None = None,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["NEXUS_LLM_PROVIDER"] = "stub"
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(ROOT), env.get("PYTHONPATH", ""))))
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "nexus_cli.py"), "--db", str(db), *args],
        cwd=cwd,
        env=env,
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )


def _case_action(
    case_id: str,
    name: str,
    workspace: Path,
    outside: Path,
) -> tuple[dict[str, Any], list[Event]]:
    failures: list[str] = []
    identity = f"phase3-{case_id.lower()}"
    before = _manifest(workspace, outside)
    target = workspace / "README.md"
    action = _make_action(
        identity,
        workspace,
        "write_file",
        path="README.md",
        content=f"{case_id} approved fixture update\n",
    )
    reasoner = _AutomaticReasoner() if case_id == "A1" else None
    context = build_human_interaction(
        build_infrastructure(), learning=False, engineering_reasoner=reasoner
    )
    if case_id == "A1":
        response = context.facade.submit(_request(identity, workspace, action))
        events = _events(context.infrastructure)
        plan = response.execution_plan
        pending = response.pending_approvals[0] if response.pending_approvals else None
        if not response.awaiting_approval or pending is None:
            failures.append("human approval gate not pending")
        if plan is None or plan.execution_strategy.approval_policy.value != "automatic":
            failures.append("automatic approval_hint seam not exercised")
        if target.read_bytes() != b"# Phase 3 fixture\n\nBefore text.\n":
            failures.append("bytes changed before approval")
        if any(event.type == "repository_action.started" for event in events):
            failures.append("action started before approval")
        if pending is not None:
            context.facade.approve(
                _request(identity, workspace, action), pending.node, decided_by="phase3-evaluator"
            )
        final_events = _events(context.infrastructure)
        after = _manifest(workspace, outside)
        if target.read_text(encoding="utf-8") != f"{case_id} approved fixture update\n":
            failures.append("approved target content mismatch")
        changed = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
        if changed != {"workspace/README.md"}:
            failures.append(f"unexpected changed paths: {sorted(changed)}")
        if not any(event.type == "approval.approved" for event in final_events):
            failures.append("approval event missing")
        events = final_events
    elif case_id == "A2":
        response = context.facade.submit(_request(identity, workspace, action))
        events = _events(context.infrastructure)
        pending = response.pending_approvals[0] if response.pending_approvals else None
        if pending is None:
            failures.append("human approval did not become pending")
        else:
            context.facade.deny(
                _request(identity, workspace, action),
                pending.node,
                decided_by="phase3-evaluator",
                reason="frozen A2 denial",
            )
        events = _events(context.infrastructure)
        if _manifest(workspace, outside) != before:
            failures.append("human-denied write changed fixture bytes")
        if any(event.type == "repository_action.started" for event in events):
            failures.append("human-denied write started")
        if not any(event.type == "approval.denied" for event in events):
            failures.append("human denial event missing")
    elif case_id == "A6":
        mismatched = RepositoryAction.write(
            workspace_root=str(outside),
            path="secret.txt",
            content="must not be written\n",
            actor="phase3-evaluator",
            request_identity=identity,
            correlation=f"cor-{identity}",
        )
        context.facade.submit(_request(identity, workspace, mismatched))
        events = _events(context.infrastructure)
        if (outside / "secret.txt").read_text(encoding="utf-8") != "sentinel\n" or _manifest(
            workspace, outside
        ) != before:
            failures.append("workspace mismatch changed fixture bytes")
        if any(event.type == "repository_action.started" for event in events):
            failures.append("mismatched workspace action started")
        if not any(event.type == "repository_action.denied" for event in events):
            failures.append("workspace mismatch denial fact missing")
    elif case_id == "A7":
        read_action = _make_action(identity, workspace, "read_file", path="README.md")
        context.facade.submit(_request(identity, workspace, read_action))
        events = _events(context.infrastructure)
        if _manifest(workspace, outside) != before:
            failures.append("read-only action changed fixture bytes")
        if not any(event.type == "repository_action.completed" for event in events):
            failures.append("read action has no completed result")
        if not any(event.type == "repository_action.artifact" for event in events):
            failures.append("read output has no artifact reference")
    elif case_id == "A8":
        control = ActuationControl()
        control.cancel()
        context.facade.submit(
            _request(identity, workspace, action),
            control=SpineControl(actuation=control),
        )
        context.facade.restart(_request(identity, workspace, action))
        events = _events(context.infrastructure)
        if _manifest(workspace, outside) != before:
            failures.append("cancelled action changed bytes")
        if any(event.type == "repository_action.started" for event in events):
            failures.append("cancelled action started")
        if not any(event.type == "repository_action.cancelled" for event in events):
            failures.append("durable cancellation fact missing")
    else:
        failures.append(f"unsupported operator case {case_id}")
    after = _manifest(workspace, outside)
    return (
        _checks(
            case_id,
            name,
            {"before_sha256": before, "after_sha256": after, "event_trace": _action_events(events)},
            failures,
        ),
        list(events),
    )


def _boundary_case(case_id: str, name: str, workspace: Path, outside: Path) -> dict[str, Any]:
    from tests.unit.nexus_execution.actions.helpers import authorized_fixture

    before = _manifest(workspace, outside)
    failures: list[str] = []
    path = (
        "../outside/secret.txt"
        if case_id == "A3"
        else "escape-link"
        if case_id == "A4"
        else "README.md"
    )
    command_id = "unlisted-fixture-command" if case_id == "A5" else "fixture-test"
    if case_id == "A4":
        link = workspace / "escape-link"
        target = os.path.relpath(outside / "secret.txt", workspace)
        link.symlink_to(target)
    fixture = authorized_fixture(
        str(workspace),
        kind="run_test" if case_id == "A5" else "write_file",
        path=path,
        command_id=command_id,
    )
    boundary = RepositoryActionBoundary(fixture.infra, command_allowlist=fixture.command_allowlist)
    denied_reason = ""
    try:
        boundary.execute(fixture.action, authorization=fixture.authorization)
    except ActionDeniedError as exc:
        denied_reason = str(exc)
    else:
        failures.append("unsafe input unexpectedly executed")
    events = _events(fixture.infra)
    after = _manifest(workspace, outside)
    if before != after:
        failures.append("denied boundary action changed fixture bytes")
    if any(event.type == "repository_action.started" for event in events):
        failures.append("denied boundary action emitted started")
    if not any(event.type == "repository_action.denied" for event in events):
        failures.append("denial event missing")
    if case_id == "A5" and "allow-listed" not in denied_reason:
        failures.append(f"expected allow-list denial, got {denied_reason!r}")
    if case_id == "A4" and (
        not (workspace / "escape-link").is_symlink()
        or (workspace / "escape-link").resolve() != (outside / "secret.txt").resolve()
    ):
        failures.append("real symlink escape was not exercised")
    observed = {
        "denial_reason": denied_reason,
        "before_sha256": before,
        "after_sha256": after,
        "event_trace": _action_events(events),
    }
    if case_id == "A4":
        observed["symlink"] = {
            "path": "workspace/escape-link",
            "target": os.path.relpath(outside / "secret.txt", workspace),
            "resolved_path": "<outside>/secret.txt",
        }
    return _checks(case_id, name, observed, failures)


def _operator_cli_cases(
    workspace: Path, outside: Path, evidence_dir: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    results: list[dict[str, Any]] = []
    cli_record: dict[str, Any] = {}
    command_file = workspace.parent.parent / "fixture_commands.json"
    command_file.write_text(
        json.dumps({"fixture-test": [sys.executable, "-m", "pytest", "tests/test_app.py", "-q"]}),
        encoding="utf-8",
    )
    for case_id in ("A12", "A13"):
        case_failures: list[str] = []
        with tempfile.TemporaryDirectory(prefix=f"nexus-phase3-{case_id.lower()}-") as temp:
            db_root = Path(temp)
            cwd = db_root / "workspace"
            cwd.mkdir()
            for relative in FIXTURE_FILES:
                source = workspace / relative
                dest = cwd / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(source.read_bytes())
            db = db_root / "events.sqlite"
            instrumentation = cwd / "instrumentation"
            instrumentation.mkdir()
            invocation_log = cwd / "process_invocations.jsonl"
            expected_argv = [sys.executable, "-m", "pytest", "tests/test_app.py", "-q"]
            normalized_argv = ["<python>", *expected_argv[1:]]
            (instrumentation / "sitecustomize.py").write_text(
                "import json, os, subprocess\n"
                "_real_run = subprocess.run\n"
                "def _recording_run(*args, **kwargs):\n"
                "    command = args[0] if args else kwargs.get('args')\n"
                "    argv = list(command) if isinstance(command, (list, tuple)) else [str(command)]\n"
                "    with open(os.environ['NEXUS_ACTION_INVOCATIONS_FILE'], 'a', encoding='utf-8') as f:\n"
                "        f.write(json.dumps({'argv': argv, 'shell': kwargs.get('shell', False), 'cwd': kwargs.get('cwd')}) + '\\n')\n"
                "    return _real_run(*args, **kwargs)\n"
                "subprocess.run = _recording_run\n",
                encoding="utf-8",
            )
            env = {
                "NEXUS_ACTION_COMMANDS_FILE": str(command_file),
                "NEXUS_ACTION_EXPECTED_ARGV": json.dumps(expected_argv),
                "NEXUS_ACTION_INVOCATIONS_FILE": str(invocation_log),
                "PYTHONPATH": os.pathsep.join((str(instrumentation), str(ROOT))),
            }
            plan = _cli_run(
                db,
                cwd,
                "--plan",
                "Run the named fixture test.",
                "--repository-root",
                str(cwd),
                "--action",
                "run_test",
                "--command-id",
                "fixture-test",
                extra_env=env,
            )
            session = re.search(r"session: (cli-[a-f0-9]+)", plan.stdout)
            first = build_durable_infrastructure(str(db))
            first.close()
            resumed = _cli_run(
                db, cwd, "--resume", session.group(1) if session else "missing", extra_env=env
            )
            reopened = build_durable_infrastructure(str(db))
            action_events = _action_events(_events(reopened))
            reopened.close()
            passed = plan.returncode == 0 and session is not None and resumed.returncode == 0
            if not passed:
                case_failures.append(
                    f"{case_id} CLI plan/resume failed: {plan.stderr} {resumed.stderr}"
                )
            if "arbitrary executable" in plan.stdout.lower():
                case_failures.append(f"{case_id} CLI exposed executable control")
            if not any(event["type"] == "repository_action.completed" for event in action_events):
                case_failures.append(f"{case_id} did not complete named allow-listed action")
            completed = next(
                (
                    event
                    for event in action_events
                    if event["type"] == "repository_action.completed"
                ),
                None,
            )
            outcome = completed["payload"].get("outcome", {}) if completed else {}
            process_invocations = (
                [
                    json.loads(line)
                    for line in invocation_log.read_text(encoding="utf-8").splitlines()
                ]
                if invocation_log.exists()
                else []
            )
            # The CLI's command allow-list is deployment configuration; no argument accepts argv.
            observed = {
                "plan_stdout": plan.stdout.replace(str(cwd), "<workspace>").replace(
                    str(db), "<db>"
                ),
                "resume_stdout": resumed.stdout.replace(str(cwd), "<workspace>").replace(
                    str(db), "<db>"
                ),
                "returncodes": [plan.returncode, resumed.returncode],
                "action_events": action_events,
                "configured_argv": normalized_argv,
                "shell": False,
                "process_invocation_trace": [
                    {
                        "argv": ["<python>", *record["argv"][1:]],
                        "shell": record["shell"],
                        "cwd": "<workspace>",
                    }
                    for record in process_invocations
                ],
                "fixture_manifest": _manifest(cwd, cwd / "outside")
                if (cwd / "outside").exists()
                else {},
                "exit_status": outcome.get("exit_status"),
            }
            if case_id == "A13" and outcome.get("argv") != normalized_argv:
                case_failures.append("A13 event argv differs from fixed allow-list")
            if outcome.get("exit_status") != 0:
                case_failures.append(f"{case_id} allow-listed pytest command failed")
            if len(process_invocations) != 1 or process_invocations[0].get("shell") is not False:
                case_failures.append(
                    f"{case_id} subprocess trace does not prove one shell-free invocation"
                )
            arbitrary = _cli_run(
                cwd / "invalid.sqlite",
                cwd,
                "--plan",
                "Run test",
                "--repository-root",
                str(cwd),
                "--action",
                "run_test",
                "--command-id",
                "fixture-test",
                "--executable",
                "malicious",
                extra_env=env,
            )
            observed["arbitrary_executable_attempt"] = {
                "returncode": arbitrary.returncode,
                "rejected": arbitrary.returncode != 0
                and "unrecognized arguments" in arbitrary.stderr,
            }
            if arbitrary.returncode == 0 or "unrecognized arguments" not in arbitrary.stderr:
                case_failures.append("CLI accepted caller-supplied executable input")
            result = _checks(
                case_id,
                "opaque-cli-boundary" if case_id == "A12" else "allow-listed-test-command-succeeds",
                observed,
                case_failures,
            )
            results.append(result)
            cli_record[case_id] = {
                "passed": result["passed"],
                "plan": observed["plan_stdout"],
                "resume": observed["resume_stdout"],
                "events": action_events,
            }
    return results, cli_record


def _case_a9(workspace: Path, outside: Path, evidence_dir: Path) -> dict[str, Any]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="nexus-phase3-A9-") as temp:
        db_root = Path(temp)
        cwd = db_root / "workspace"
        cwd.mkdir()
        for relative in FIXTURE_FILES:
            dest = cwd / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes((workspace / relative).read_bytes())
        target = cwd / "README.md"
        target_before = hashlib.sha256(target.read_bytes()).hexdigest()
        fixture_before = _manifest(cwd, outside)
        db = db_root / "actions.sqlite"
        plan = _cli_run(
            db,
            cwd,
            "--plan",
            "Write a single approved marker to README.",
            "--repository-root",
            str(cwd),
            "--action",
            "write_file",
            "--action-path",
            "README.md",
            "--action-content",
            "one execution only\n",
        )
        match = re.search(r"session: (cli-[a-f0-9]+)", plan.stdout)
        if plan.returncode != 0 or match is None:
            failures.append("A9 plan process failed to persist a session")
            return _checks(
                "A9",
                "completed-action-restart-no-repeat",
                {"plan_stdout": plan.stdout, "stderr": plan.stderr},
                failures,
            )
        session = match.group(1)
        pending = build_durable_infrastructure(str(db))
        pending_count = sum(event.type == "repository_action.started" for event in _events(pending))
        pending.close()
        if pending_count:
            failures.append("plan process dispatched before resume")
        resumed = _cli_run(db, cwd, "--resume", session, stdin="y\n")
        after_first = hashlib.sha256(target.read_bytes()).hexdigest()
        first_infra = build_durable_infrastructure(str(db))
        first_events = _events(first_infra)
        started_first = sum(event.type == "repository_action.started" for event in first_events)
        completed_first = sum(event.type == "repository_action.completed" for event in first_events)
        first_infra.close()
        replayed = _cli_run(db, cwd, "--resume", session)
        second_infra = build_durable_infrastructure(str(db))
        second_events = _events(second_infra)
        started_second = sum(event.type == "repository_action.started" for event in second_events)
        completed_second = sum(
            event.type == "repository_action.completed" for event in second_events
        )
        second_infra.close()
        after_second = hashlib.sha256(target.read_bytes()).hexdigest()
        fixture_after = _manifest(cwd, outside)
        if resumed.returncode != 0 or replayed.returncode != 0:
            failures.append("one of the fresh-process resumes failed")
        if (started_first, completed_first, started_second, completed_second) != (1, 1, 1, 1):
            failures.append("fresh-process replay changed action dispatch/completion count")
        if after_first != after_second or after_first == target_before:
            failures.append("write side effect hash did not remain stable across restart")
        changed = {
            key
            for key in fixture_before.keys() | fixture_after.keys()
            if fixture_before.get(key) != fixture_after.get(key)
        }
        if changed != {"workspace/README.md"}:
            failures.append(f"A9 changed unexpected fixture paths: {sorted(changed)}")
        observed = {
            "plan_process": plan.stdout.replace(str(cwd), "<workspace>").replace(str(db), "<db>"),
            "first_resume_process": resumed.stdout.replace(str(cwd), "<workspace>").replace(
                str(db), "<db>"
            ),
            "second_resume_process": replayed.stdout.replace(str(cwd), "<workspace>").replace(
                str(db), "<db>"
            ),
            "before_sha256": target_before,
            "after_sha256": after_first,
            "before_fixture_sha256": fixture_before,
            "after_fixture_sha256": fixture_after,
            "process_counts": {
                "started_after_first": started_first,
                "completed_after_first": completed_first,
                "started_after_replay": started_second,
                "completed_after_replay": completed_second,
            },
            "event_trace": _action_events(second_events),
        }
        result = _checks("A9", "completed-action-restart-no-repeat", observed, failures)
        (evidence_dir / "a9_process_trace.json").write_text(
            json.dumps(observed, indent=2) + "\n", encoding="utf-8"
        )
        return result


def _case_a14(workspace: Path, outside: Path) -> tuple[dict[str, Any], list[Event]]:
    failures: list[str] = []
    identity = "phase3-a14"
    before = _manifest(workspace, outside)
    action = _make_action(
        identity, workspace, "write_file", path="README.md", content="must remain unchanged\n"
    )
    context = build_human_interaction(build_infrastructure(), learning=False)
    request = _request(identity, workspace, action)
    pending = context.facade.submit(request)
    if not pending.awaiting_approval or not pending.pending_approvals:
        failures.append("write did not reach a pending human gate")
    deny_policy = Policy(
        identity="policy.phase3.a14.denied-action",
        version="1",
        purpose="Frozen A14 policy denial for this exact action input.",
        conditions={"attr": "action_id", "op": "eq", "value": action.identity},
        decision=PolicyDecision.DENY,
        priority=100,
        owner="phase3-evaluator",
        status=PolicyStatus.ENABLED,
        category=PolicyCategory.GOVERNANCE,
        governed_action_class="repository_action",
    )
    context.spine.coordinator._policy.registry.register(deny_policy)
    if pending.pending_approvals:
        context.facade.approve(
            request, pending.pending_approvals[0].node, decided_by="phase3-evaluator"
        )
    events = _events(context.infrastructure)
    after = _manifest(workspace, outside)
    if before != after:
        failures.append("Policy DENY changed fixture bytes")
    if any(event.type == "repository_action.started" for event in events):
        failures.append("Policy DENY did not prevent action start")
    requested = next(
        (event for event in events if event.type == "repository_action.requested"), None
    )
    plan_event = next(
        (event for event in events if event.type == "planning.execution_plan_assembled"), None
    )
    expected_node = ""
    expected_plan = ""
    if requested is None or plan_event is None:
        failures.append("durable action request or frozen plan missing")
    else:
        raw_plan = plan_event.payload.get("execution_plan", {})
        plan_obj = raw_plan.get("plan", {})
        expected_plan = str(plan_obj.get("identity", "")) if isinstance(plan_obj, dict) else ""
        packages = raw_plan.get("work_packages", ())
        nodes = raw_plan.get("execution_graph", {}).get("nodes", ())
        for graph_node in nodes:
            if not isinstance(graph_node, dict):
                continue
            package_id = graph_node.get("work_package_ref", {}).get("identifier")
            package = next(
                (
                    item
                    for item in packages
                    if isinstance(item, dict) and item.get("identifier") == package_id
                ),
                None,
            )
            if package and any(
                ref.get("target_type") == "action_request"
                and ref.get("identifier") == requested.payload.get("action_id")
                for ref in package.get("inputs", ())
            ):
                expected_node = str(graph_node.get("identifier", ""))
                break
    matching_approval = any(
        event.type == "approval.approved"
        and event.payload.get("session") == f"pipe-{identity}"
        and event.payload.get("node") == expected_node
        for event in events
    )
    if not matching_approval:
        failures.append("matching human approval event missing")
    denied = [
        event
        for event in events
        if event.type == "policy.evaluated"
        and event.payload.get("decision") == "deny"
        and event.payload.get("action_class") == "repository_action"
        and isinstance(event.payload.get("attributes"), dict)
        and all(
            event.payload["attributes"].get(key) == value
            for key, value in {
                "action_id": requested.payload.get("action_id") if requested else None,
                "input_digest": requested.payload.get("input_digest") if requested else None,
                "plan_identity": expected_plan,
                "pipeline_session": f"pipe-{identity}",
                "node": expected_node,
                "actor": "phase3-evaluator",
            }.items()
        )
    ]
    if not denied:
        failures.append("exact-action/plan/node Policy DENY evaluation missing")
    return _checks(
        "A14",
        "policy-deny-overrides-recorded-approval",
        {"before_sha256": before, "after_sha256": after, "event_trace": _action_events(events)},
        failures,
    ), list(events)


def _a11_lineage(events: Sequence[Event], identity: str) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    requested = next(
        (event for event in events if event.type == "repository_action.requested"), None
    )
    started = next((event for event in events if event.type == "repository_action.started"), None)
    completed = next(
        (event for event in events if event.type == "repository_action.completed"), None
    )
    approval = next((event for event in events if event.type == "approval.approved"), None)
    policy = next(
        (
            event
            for event in events
            if event.type == "policy.evaluated" and event.payload.get("decision") == "allow"
        ),
        None,
    )
    plan_event = next(
        (event for event in events if event.type == "planning.execution_plan_assembled"), None
    )
    if not all((requested, started, completed, approval, policy, plan_event)):
        return {}, ["one or more required lineage events are missing"]
    assert (
        requested is not None
        and started is not None
        and completed is not None
        and approval is not None
        and policy is not None
        and plan_event is not None
    )
    action_id = requested.payload.get("action_id")
    digest = requested.payload.get("input_digest")
    start_payload = started.payload
    approval_payload = approval.payload
    policy_attrs = policy.payload.get("attributes", {})
    plan = plan_event.payload.get("execution_plan", {})
    plan_obj = plan.get("plan", {}) if isinstance(plan, dict) else {}
    goal_ref = plan.get("goal_ref", {}) if isinstance(plan, dict) else {}
    node = start_payload.get("node")
    session = start_payload.get("pipeline_session")
    graph = plan.get("execution_graph", {}) if isinstance(plan, dict) else {}
    nodes = graph.get("nodes", ()) if isinstance(graph, dict) else ()
    work_package_ids = {
        item.get("work_package_ref", {}).get("identifier")
        for item in nodes
        if isinstance(item, dict) and item.get("identifier") == node
    }
    packages = plan.get("work_packages", ()) if isinstance(plan, dict) else ()
    bound = any(
        package.get("identifier") in work_package_ids
        and any(
            ref.get("target_type") == "action_request" and ref.get("identifier") == action_id
            for ref in package.get("inputs", ())
        )
        for package in packages
        if isinstance(package, dict)
    )
    conditions = {
        "same_action_id": start_payload.get("action_id") == action_id,
        "same_input_digest": start_payload.get("input_digest") == digest,
        "same_actor": start_payload.get("actor")
        == requested.payload.get("action", {}).get("actor"),
        "plan_bound_action_reference": bound,
        "same_plan": start_payload.get("plan") == plan_obj.get("identity"),
        "same_session_approval": approval_payload.get("session") == session,
        "same_node_approval": approval_payload.get("node") == node,
        "policy_action_binding": policy_attrs.get("action_id") == action_id
        and policy_attrs.get("input_digest") == digest,
        "completion_references_artifact": bool(
            completed.payload.get("outcome", {}).get("diff_ref")
        ),
        "goal_request_identity": requested.payload.get("action", {}).get("request_identity")
        == identity,
        "goal_belongs_to_request": isinstance(goal_ref, dict)
        and goal_ref.get("identifier") == f"goal-{identity}",
    }
    failures.extend(name for name, ok in conditions.items() if not ok)
    return {"lineage_checks": conditions, "event_trace": _action_events(events)}, failures


def main() -> int:
    PHASE3.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    cases = cast(dict[str, Any], json.loads((PHASE3 / "cases.json").read_text(encoding="utf-8")))
    results: list[dict[str, Any]] = []
    all_traces: dict[str, list[dict[str, Any]]] = {}
    a1_events: list[Event] = []
    with tempfile.TemporaryDirectory(prefix="nexus-phase3-eval-") as temp:
        base = Path(temp)
        inventory: dict[str, dict[str, str]] = {}
        # The real symlink is created inside A4; never silently skip it.
        for case_id, name in (
            ("A1", "approved-write"),
            ("A2", "denied-write-no-start-byte-identity"),
            ("A6", "workspace-mismatch-denied"),
            ("A7", "read-only-action"),
            ("A8", "cancellation"),
        ):
            case_workspace, case_outside = _fixture(base / case_id)
            inventory[case_id] = _manifest(case_workspace, case_outside)
            case_result, events = _case_action(case_id, name, case_workspace, case_outside)
            results.append(case_result)
            all_traces[case_id] = _action_events(events)
            if case_id == "A1":
                a1_events = events
                diff_event = next(
                    (
                        event
                        for event in events
                        if event.type == "repository_action.artifact"
                        and event.payload.get("kind") == "unified_diff"
                    ),
                    None,
                )
                if diff_event is not None:
                    diff_path = Path(str(diff_event.payload["path"]))
                    (EVIDENCE / "approved_write.diff").write_text(
                        diff_path.read_text(encoding="utf-8"), encoding="utf-8", newline=""
                    )
        for case_id, name in (
            ("A3", "path-traversal-denied"),
            ("A4", "symlink-component-escape-denied"),
            ("A5", "unlisted-test-command-denied"),
        ):
            case_workspace, case_outside = _fixture(base / case_id)
            inventory[case_id] = _manifest(case_workspace, case_outside)
            result = _boundary_case(case_id, name, case_workspace, case_outside)
            results.append(result)
            all_traces[case_id] = result["observed"]["event_trace"]
        cli_workspace, cli_outside = _fixture(base / "CLI")
        inventory["CLI"] = _manifest(cli_workspace, cli_outside)
        results.append(_case_a9(cli_workspace, cli_outside, EVIDENCE))
        worker_trace: dict[str, Any] = {}
        crash_exit: int | None = None
        try:
            with tempfile.TemporaryDirectory(prefix="nexus-phase3-A10-") as temp_a10:
                root = Path(temp_a10)
                worker_workspace = root / "workspace"
                worker_workspace.mkdir()
                marker = worker_workspace / "marker.txt"
                marker.write_text("before\n", encoding="utf-8")
                db = root / "events.sqlite"
                dispatch_log = root / "dispatches.log"
                identity = "phase3-a10-worker"
                crashed = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts" / "phase3_recovery_worker.py"),
                        "crash-after-write",
                        "--db",
                        str(db),
                        "--workspace",
                        str(worker_workspace),
                        "--identity",
                        identity,
                        "--dispatch-log",
                        str(dispatch_log),
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=60,
                )
                crash_exit = crashed.returncode
                resumed = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts" / "phase3_recovery_worker.py"),
                        "resume",
                        "--db",
                        str(db),
                        "--workspace",
                        str(worker_workspace),
                        "--identity",
                        identity,
                        "--dispatch-log",
                        str(dispatch_log),
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=60,
                )
                replayed = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts" / "phase3_recovery_worker.py"),
                        "resume",
                        "--db",
                        str(db),
                        "--workspace",
                        str(worker_workspace),
                        "--identity",
                        identity,
                        "--dispatch-log",
                        str(dispatch_log),
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=60,
                )
                first_trace = json.loads(resumed.stdout)
                second_trace = json.loads(replayed.stdout)

                def safe_worker(trace: dict[str, Any]) -> dict[str, Any]:
                    safe_events = []
                    for event in trace.get("action_events", []):
                        payload = dict(event.get("payload", {}))
                        action_input = payload.get("action")
                        if isinstance(action_input, dict):
                            payload["action"] = {
                                key: action_input.get(key)
                                for key in ("kind", "path", "actor", "request_identity")
                            }
                        payload.pop("content", None)
                        if "workspace_root" in payload:
                            payload["workspace_root"] = "<workspace>"
                        safe_events.append(
                            {"id": event.get("id"), "type": event.get("type"), "payload": payload}
                        )
                    fields = (
                        "status",
                        "succeeded",
                        "target_sha256",
                        "started_count",
                        "completed_count",
                        "indeterminate_count",
                    )
                    return {key: trace.get(key) for key in fields} | {"action_events": safe_events}

                worker_trace = {
                    "crash_exit": crash_exit,
                    "fault_marker": "FAULT_INJECTED_AFTER_SIDE_EFFECT" in crashed.stdout,
                    "resume": safe_worker(first_trace),
                    "repeat_resume": safe_worker(second_trace),
                    "side_effect_dispatch_count": len(
                        dispatch_log.read_text(encoding="utf-8").splitlines()
                    )
                    if dispatch_log.exists()
                    else 0,
                }
                failed: list[str] = []
                if crash_exit != 86:
                    failed.append(f"expected injected post-write exit 86, got {crash_exit}")
                if not worker_trace["fault_marker"]:
                    failed.append("crash marker does not confirm post-side-effect fault point")
                if worker_trace["side_effect_dispatch_count"] != 1:
                    failed.append("side-effect instrumentation observed a redispatch after restart")
                if resumed.returncode != 0 or replayed.returncode != 0:
                    failed.append("fresh-process restart failed")
                if first_trace["status"] != "paused" or first_trace["succeeded"]:
                    failed.append("restart did not halt paused for reconciliation")
                expected_written_hash = hashlib.sha256(b"approved marker\n").hexdigest()
                if first_trace["target_sha256"] != expected_written_hash:
                    failed.append("post-crash bytes do not prove the side effect happened")
                if (
                    first_trace["started_count"] != 1
                    or first_trace["completed_count"] != 0
                    or first_trace["indeterminate_count"] != 1
                ):
                    failed.append(
                        "restart did not halt with one started/no completed/one indeterminate"
                    )
                if (
                    first_trace["target_sha256"] != second_trace["target_sha256"]
                    or second_trace["started_count"] != 1
                ):
                    failed.append(
                        "repeated restart changed bytes or redispatched the indeterminate action"
                    )
                all_traces["A10"] = worker_trace["resume"]["action_events"]
                results.append(
                    _checks(
                        "A10",
                        "post-side-effect-pre-completion-crash-indeterminate",
                        worker_trace,
                        failed,
                    )
                )
        except Exception as exc:
            results.append(
                _checks(
                    "A10",
                    "post-side-effect-pre-completion-crash-indeterminate",
                    worker_trace,
                    [f"exception: {type(exc).__name__}: {exc}"],
                )
            )
        cli_results, cli_evidence = _operator_cli_cases(cli_workspace, cli_outside, EVIDENCE)
        results.extend(cli_results)
        all_traces.update({key: value.get("events", []) for key, value in cli_evidence.items()})
        lineage, lineage_failures = _a11_lineage(a1_events, "phase3-a1")
        results.append(_checks("A11", "durable-event-lineage", lineage, lineage_failures))
        a14_workspace, a14_outside = _fixture(base / "A14")
        inventory["A14"] = _manifest(a14_workspace, a14_outside)
        a14, a14_events = _case_a14(a14_workspace, a14_outside)
        results.append(a14)
        all_traces["A14"] = _action_events(a14_events)

        gate_cases = {case["id"]: case for case in cases["cases"]}
        for result in results:
            frozen = gate_cases.get(result["id"])
            if frozen is None or frozen["name"] != result["name"]:
                result["failures"].append("result does not map to frozen case")
                result["passed"] = False
        fails = [result for result in results if not result["passed"]]
        (EVIDENCE / "fixture_inventory.json").write_text(
            json.dumps(inventory, indent=2) + "\n", encoding="utf-8"
        )
        (EVIDENCE / "event_traces.json").write_text(
            json.dumps(all_traces, indent=2) + "\n", encoding="utf-8"
        )
        opaque_note = "This evidence covers only Nexus-owned actions dispatched through RepositoryActionBoundary. Provider-internal tool or CLI actions remain opaque and are not claimed as governed or inspected. The operator CLI accepts command_id only; executable argv comes from deployment configuration NEXUS_ACTION_COMMANDS_FILE."
        (EVIDENCE / "opaque_boundary.txt").write_text(opaque_note + "\n", encoding="utf-8")
        by_id = {result["id"]: result for result in results}

        def byte_identical(case_id: str) -> bool:
            observed = by_id[case_id]["observed"]
            return bool(observed.get("before_sha256") == observed.get("after_sha256"))

        def no_action_start(case_id: str) -> bool:
            return not any(
                event["type"] == "repository_action.started"
                for event in by_id[case_id]["observed"].get("event_trace", [])
            )

        a10_observed = by_id["A10"]["observed"]
        a9_observed = by_id["A9"]["observed"]
        measured = {
            "cases_passed": f"{sum(result['passed'] for result in results)}/{len(results)}",
            "denied_cases_no_action_start": {
                case_id: no_action_start(case_id)
                for case_id in ("A2", "A3", "A4", "A5", "A6", "A14")
            },
            "denied_cases_byte_changes": sum(
                not byte_identical(case_id) for case_id in ("A2", "A3", "A4", "A5", "A6", "A14")
            ),
            "A1_action_starts_before_human_approval": 0
            if "no action started before approval" not in by_id["A1"]["failures"]
            else 1,
            "A14_action_starts_with_policy_deny": 0 if no_action_start("A14") else 1,
            "read_only_byte_changes": 0 if byte_identical("A7") else 1,
            "completed_action_dispatches_after_restart": a9_observed["process_counts"][
                "started_after_replay"
            ]
            - a9_observed["process_counts"]["started_after_first"],
            "indeterminate_action_automatic_redispatches": a10_observed[
                "side_effect_dispatch_count"
            ]
            - 1,
            "approved_write_changes_outside_selected_target": max(
                0,
                len(
                    {
                        key
                        for key in by_id["A1"]["observed"]["before_sha256"].keys()
                        | by_id["A1"]["observed"]["after_sha256"].keys()
                        if by_id["A1"]["observed"]["before_sha256"].get(key)
                        != by_id["A1"]["observed"]["after_sha256"].get(key)
                    }
                    - {"workspace/README.md"}
                ),
            ),
            "allow_list_test_shell_invocations": sum(
                record["shell"] is not False
                for case_id in ("A12", "A13")
                for record in by_id[case_id]["observed"]["process_invocation_trace"]
            ),
            "policy_and_approval_input_digest_mismatch": sum(
                not all(by_id["A11"]["observed"].get("lineage_checks", {}).values()) for _ in (0,)
            ),
            "missing_required_lineage_links": sum(
                not value for value in by_id["A11"]["observed"].get("lineage_checks", {}).values()
            ),
            "skips": 0,
            "warnings": 0,
        }
        report = {
            "command": "python scripts/evaluate_phase3_gate.py",
            "python_version": platform.python_version(),
            "registered_case_count": len(results),
            "passed_count": sum(result["passed"] for result in results),
            "failed_count": len(fails),
            "thresholds": cases["thresholds"],
            "measured_thresholds": measured,
            "evaluation_warnings": [],
            "failures": [{"id": item["id"], "failures": item["failures"]} for item in fails],
            "cases": results,
        }
        (EVIDENCE / "evaluation_report.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "registered_case_count": len(results),
                "passed_count": sum(result["passed"] for result in results),
                "failed_count": sum(not result["passed"] for result in results),
                "failures": [
                    {"id": item["id"], "failures": item["failures"]}
                    for item in results
                    if not item["passed"]
                ],
            },
            indent=2,
        )
    )
    return 0 if len(results) == 14 and not any(not item["passed"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
