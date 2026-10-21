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
from typing import Any, NoReturn, cast

from nexus_core.domain.event import Event
from nexus_human_interaction import build_human_interaction
from nexus_human_interaction.model import OperatorRequest
from nexus_infra import build_durable_infrastructure
from nexus_intent.model import IntentAnalysis
from nexus_planning.grounded.model import ExecutionPlan
from nexus_workflows.spine import SpineControl, SpineStage
from nexus_workflows.spine.coordinator import _RunCtx
from nexus_workflows.spine.model import SpineRequest

ROOT = Path(__file__).resolve().parents[1]
PHASE2 = ROOT / "docs" / "phase2"
EVIDENCE = PHASE2 / "evidence"
FIXTURE = EVIDENCE / "fixture_repository"

_FIXTURE_FILES = {
    "pyproject.toml": "[project]\nname = 'fixture-cli'\nversion = '1.2.3'\nrequires-python = '>=3.11'\n\n[tool.pytest.ini_options]\ntestpaths = ['tests']\n\n[tool.ruff]\nline-length = 88\n",
    "README.md": "# Fixture CLI\n\nEntry point: `src/fixture_cli/main.py`. Commands: `run`, `status`. Tests: `python -m pytest`.\n",
    "src/fixture_cli/main.py": "import argparse\n\ndef main(argv=None):\n    parser = argparse.ArgumentParser()\n    sub = parser.add_subparsers(dest='command')\n    sub.add_parser('run')\n    sub.add_parser('status')\n    return parser.parse_args(argv)\n",
    "src/fixture_cli/config.py": "def load_config(path):\n    with open(path, encoding='utf-8') as handle:\n        return dict(line.split('=', 1) for line in handle if '=' in line)\n",
    "src/fixture_cli/export.py": "import json\n\ndef export_json(data, path):\n    with open(path, 'w', encoding='utf-8') as handle:\n        json.dump(data, handle)\n",
    "tests/test_main.py": "from fixture_cli.main import main\n\ndef test_run_command():\n    assert main(['run']).command == 'run'\n\ndef test_status_command():\n    assert main(['status']).command == 'status'\n",
    "tests/test_config.py": "from fixture_cli.config import load_config\n\ndef test_load_config(tmp_path):\n    path = tmp_path / 'config.ini'\n    path.write_text('mode=fast', encoding='utf-8')\n    assert load_config(path) == {'mode': 'fast'}\n",
    "tests/test_export.py": "import json\nfrom fixture_cli.export import export_json\n\ndef test_export_json(tmp_path):\n    path = tmp_path / 'data.json'\n    export_json({'ok': True}, path)\n    assert json.loads(path.read_text(encoding='utf-8')) == {'ok': True}\n",
}


def _fixture() -> None:
    for relative, content in _FIXTURE_FILES.items():
        path = FIXTURE / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


def _cases() -> list[dict[str, Any]]:
    cases = json.loads((PHASE2 / "cases.json").read_text(encoding="utf-8-sig"))["cases"]
    return cast(list[dict[str, Any]], cases)


def _find(events: Sequence[Event], event_type: str) -> Event | None:
    return next((event for event in events if event.type == event_type), None)


def _check(failures: list[str], name: str, condition: bool) -> None:
    if not condition:
        failures.append(name)


def _replay_check(db: Path, request: OperatorRequest) -> dict[str, Any]:
    infra = build_durable_infrastructure(str(db))
    events = tuple(infra.event_store.read_all())
    ctx = build_human_interaction(infra, learning=False)
    coordinator = ctx.spine.coordinator

    def forbidden(*_args: Any, **_kwargs: Any) -> NoReturn:
        raise AssertionError("replay crossed the interpretation or repository scan seam")

    coordinator._intent.engine._interpreter = type(
        "ReplaySpy", (), {"version": "spy", "interpret": forbidden}
    )()
    repository_engine: Any = coordinator._repository.engine
    repository_engine.profile = forbidden
    operator = request
    spine_request = SpineRequest(
        identity=operator.identity,
        request_text=operator.request_text,
        work_items=operator.work_items,
        knowledge_subject=operator.knowledge_subject,
        scope=operator.scope,
        knowledge_kind=operator.knowledge_kind,
        context_fragments=operator.context_fragments,
        capabilities=operator.capabilities,
        fail=operator.fail,
        correlation_identifier=operator.correlation_identifier,
        repository_root=operator.repository_root,
    )
    replay_ctx = _RunCtx()
    resume_stage = coordinator._seed(events, replay_ctx, spine_request)
    intent_event = _find(events, "intent.resolved")
    plan_event = _find(events, "planning.execution_plan_assembled")
    profile_event = _find(events, "repository.profiled")
    assert intent_event is not None and plan_event is not None
    analysis = IntentAnalysis.model_validate(intent_event.payload["analysis"])
    plan = ExecutionPlan.model_validate(plan_event.payload["execution_plan"])
    assert replay_ctx.intent_analysis == analysis
    assert replay_ctx.plan == plan
    assert resume_stage is SpineStage.ACTUATION
    assert replay_ctx.repository_profile is not None
    assert profile_event is not None
    trace = {
        "intent_identity": analysis.identity,
        "plan_identity": plan.identity,
        "repository_profile_identity": replay_ctx.repository_profile.identity,
        "resume_stage": resume_stage.value,
        "interpreter_calls": 0,
        "repository_rescans": 0,
    }
    infra.close()
    return trace


def _evaluate_cli_path() -> dict[str, Any]:
    """Run plan, resume, and replay in fresh CLI processes; write only sanitized evidence."""
    evidence: dict[str, Any] = {
        "test": "scripts/nexus_cli.py --plan / --resume",
        "passed": False,
    }

    def run_cli(db: Path, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["NEXUS_LLM_PROVIDER"] = "stub"
        env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(ROOT), env.get("PYTHONPATH", ""))))
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "nexus_cli.py"), "--db", str(db), *args],
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )

    def counts(db: Path) -> dict[str, int]:
        infra = build_durable_infrastructure(str(db))
        try:
            events = tuple(infra.event_store.read_all())
        finally:
            infra.close()
        return {
            kind: sum(event.type == kind for event in events)
            for kind in ("runtime.started", "runtime.artifact_emitted")
        }

    try:
        with tempfile.TemporaryDirectory(prefix="nexus-phase2-cli-") as directory:
            cwd = Path(directory)
            db = cwd / "operator.sqlite"
            planned = run_cli(
                db,
                cwd,
                "--plan",
                "Update the CLI: first implement a --version option, then add a focused test for it.",
                "--repository-root",
                str(FIXTURE),
            )
            if planned.returncode != 0:
                raise RuntimeError(f"plan process failed: {planned.stderr.strip()}")
            session = re.search(r"session: (cli-[a-f0-9]+)", planned.stdout)
            if session is None:
                raise RuntimeError("plan process did not print a resumable session")
            initial = counts(db)
            items = [line.strip() for line in planned.stdout.splitlines() if "  work item " in line]
            dependencies = [
                line.strip() for line in planned.stdout.splitlines() if "  dependency:" in line
            ]
            if (
                "plan paused before actuation" not in planned.stdout
                or len(items) != 2
                or len(dependencies) != 1
                or initial["runtime.started"] != 0
                or initial["runtime.artifact_emitted"] != 0
            ):
                raise RuntimeError(
                    "plan process did not meet the pre-actuation inspection threshold"
                )

            resumed = run_cli(db, cwd, "--resume", session.group(1))
            if resumed.returncode != 0 or "status: completed" not in resumed.stdout:
                raise RuntimeError(f"resume process failed: {resumed.stderr.strip()}")
            completed = counts(db)
            if completed["runtime.started"] != 2:
                raise RuntimeError("resume did not dispatch both declared work items")

            replayed = run_cli(db, cwd, "--resume", session.group(1))
            if replayed.returncode != 0 or "status: completed" not in replayed.stdout:
                raise RuntimeError(f"replay process failed: {replayed.stderr.strip()}")
            final = counts(db)
            if final != completed:
                raise RuntimeError("replay changed runtime dispatch/artifact counts")
            evidence.update(
                {
                    "passed": True,
                    "plan_process": {
                        "status": "stopped after planning",
                        "runtime_counts": initial,
                        "work_items": items,
                        "dependencies": dependencies,
                        "source_refs_present": "source refs:" in planned.stdout,
                        "assumptions_present": "assumptions:" in planned.stdout,
                    },
                    "resume_process": {"status": "completed", "runtime_counts": completed},
                    "replay_process": {
                        "status": "completed",
                        "runtime_counts_unchanged": final == completed,
                    },
                }
            )
    except Exception as exc:
        evidence["failure"] = f"{type(exc).__name__}: {exc}"
    (EVIDENCE / "operator_path_cli.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )
    return evidence


def main() -> int:
    _fixture()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    cli_evidence = _evaluate_cli_path()
    inventory = set(_FIXTURE_FILES)
    provenance: list[dict[str, Any]] = []
    transcripts: list[dict[str, Any]] = []
    replay: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    for case in _cases():
        result: dict[str, Any] = {"id": case["id"], "kind": case["kind"], "passed": False}
        case_failures: list[str] = []
        try:
            with tempfile.TemporaryDirectory(prefix=f"nexus-phase2-{case['id']}-") as temp:
                db = Path(temp) / "events.sqlite"
                infra = build_durable_infrastructure(str(db))
                interaction = build_human_interaction(infra, learning=False)
                request = OperatorRequest(
                    identity=f"phase2-{case['id']}",
                    request_text=case["request"],
                    work_items=(),
                    knowledge_subject="fixture CLI",
                    scope="fixture repository",
                    repository_root=str(FIXTURE),
                )
                response = interaction.facade.submit(
                    request, control=SpineControl(stop_after_stage=SpineStage.PLANNING)
                )
                events = tuple(infra.event_store.read_all())
                intent_event = _find(events, "intent.resolved")
                assert intent_event is not None
                analysis = IntentAnalysis.model_validate(intent_event.payload["analysis"])
                context_event = _find(events, "context.grounding.assembled")
                profile_event = _find(events, "repository.profiled")
                profile = profile_event.payload["profile"] if profile_event is not None else None
                selection = response.grounding_selection
                execution_plan = response.execution_plan
                citations = [
                    ref.identifier
                    for ref in (execution_plan.context_references if execution_plan else ())
                    if ref.target_type == "file"
                ]
                if case["kind"] == "clarify":
                    _check(
                        case_failures,
                        "clarification_required",
                        not analysis.resolved and analysis.goal is None,
                    )
                    _check(
                        case_failures,
                        "clarification_prompt_present",
                        bool(response.clarification_requests),
                    )
                    _check(
                        case_failures,
                        "downstream_artifacts_absent",
                        execution_plan is None and context_event is None and profile_event is None,
                    )
                    transcripts.append(
                        {
                            "case_id": case["id"],
                            "request": case["request"],
                            "clarifications": [
                                item.model_dump(mode="json")
                                for item in response.clarification_requests
                            ],
                            "goal": None,
                            "context_package": None,
                            "plan": None,
                        }
                    )
                    infra.close()
                else:
                    _check(
                        case_failures,
                        "resolved_plan_present",
                        analysis.resolved and execution_plan is not None,
                    )
                    _check(
                        case_failures,
                        "stopped_after_planning",
                        bool(response.executed_stages)
                        and response.executed_stages[-1] == SpineStage.PLANNING.value,
                    )
                    _check(
                        case_failures,
                        "actuation_not_started",
                        SpineStage.ACTUATION.value not in response.executed_stages,
                    )
                    _check(
                        case_failures,
                        "grounding_and_profile_present",
                        selection is not None
                        and context_event is not None
                        and profile_event is not None,
                    )
                    work_count = len(execution_plan.work_packages) if execution_plan else 0
                    edges = (
                        [
                            [source.removeprefix("node-"), target.removeprefix("node-")]
                            for source, target in execution_plan.coordination.dependency_edges
                        ]
                        if execution_plan
                        else []
                    )
                    if case["kind"] == "atomic":
                        _check(case_failures, "atomic_shape", work_count == 1 and not edges)
                    else:
                        _check(
                            case_failures, "multi_step_count", work_count == case["expected_steps"]
                        )
                        _check(
                            case_failures,
                            "dependency_edges",
                            sorted(edges) == sorted(case["expected_edges"]),
                        )
                    objectives = (
                        [
                            next(
                                package.objective
                                for package in execution_plan.work_packages
                                if package.identifier == node.work_package_ref.identifier
                            ).lower()
                            for node in execution_plan.execution_graph.nodes
                        ]
                        if execution_plan
                        else []
                    )
                    expected_objectives = case.get("expected_objectives", [])
                    _check(
                        case_failures,
                        "requested_objective_coverage",
                        len(objectives) == len(expected_objectives)
                        and all(
                            all(term.lower() in objective for term in terms)
                            for objective, terms in zip(
                                objectives, expected_objectives, strict=True
                            )
                        ),
                    )
                    _check(case_failures, "citations_exist_in_fixture", set(citations) <= inventory)
                    _check(
                        case_failures,
                        "citations_within_registered_allowlist",
                        set(citations) <= set(case["references"]),
                    )
                    _check(
                        case_failures,
                        "required_implementation_citations",
                        set(case.get("required_citations", ())) <= set(citations),
                    )
                    plan_assumptions = execution_plan.plan.assumptions if execution_plan else ()
                    _check(
                        case_failures,
                        "assumptions_or_declared_steps_visible",
                        bool(
                            plan_assumptions
                            or analysis.declared_steps
                            or analysis.intent.assumptions
                        ),
                    )
                    infra.close()
                    replay.append({"case_id": case["id"], **_replay_check(db, request)})

                records: list[dict[str, Any]] = []
                if selection is not None:
                    records.extend(cast(list[dict[str, Any]], selection.get("selected", [])))
                    records.extend(cast(list[dict[str, Any]], selection.get("omitted", [])))
                context_identity = (
                    next(
                        (
                            ref.identifier
                            for ref in execution_plan.context_references
                            if ref.target_type == "context_package"
                        ),
                        None,
                    )
                    if execution_plan
                    else None
                )
                bundle = {
                    "case_id": case["id"],
                    "raw_request": case["request"],
                    "repository_root": str(FIXTURE),
                    "repository_profile": {
                        "identity": profile.get("identity") if profile else None,
                        "scanner_version": profile.get("scanner_version") if profile else None,
                        "files": profile.get("files", []) if profile else [],
                        "evidence": profile.get("evidence", []) if profile else [],
                        "facts": {
                            key: profile.get(key)
                            for key in ("repository_type", "technology", "build", "test")
                        }
                        if profile
                        else None,
                    },
                    "intent": {
                        "identity": analysis.identity,
                        "version": analysis.interpreter_version,
                        "resolved": analysis.resolved,
                        "domain": analysis.intent.detected_domain.value
                        if analysis.intent.detected_domain
                        else None,
                        "operator_claim": analysis.intent.raw_request,
                        "ambiguity": list(analysis.intent.ambiguity),
                        "missing_information": list(analysis.intent.missing_information),
                        "assumptions": list(analysis.intent.assumptions),
                    },
                    "grounding_records": records,
                    "goal_identity": analysis.goal.identity if analysis.goal else None,
                    "context_package_identity": context_identity,
                    "plan_identity": execution_plan.identity if execution_plan else None,
                    "work_items": [
                        {
                            "key": node.identifier.removeprefix("node-"),
                            "objective": next(
                                package.objective
                                for package in execution_plan.work_packages
                                if package.identifier == node.work_package_ref.identifier
                            ),
                            "identity": node.work_package_ref.identifier,
                        }
                        for node in execution_plan.execution_graph.nodes
                    ]
                    if execution_plan
                    else [],
                    "dependency_edges": edges if execution_plan else [],
                    "assumptions": list(execution_plan.plan.assumptions) if execution_plan else [],
                    "uncertainty": {
                        "confidence": analysis.confidence.model_dump(mode="json"),
                        "ambiguity": list(analysis.intent.ambiguity),
                        "missing_information": list(analysis.intent.missing_information),
                    },
                    "citations": citations,
                    "citation_content_sha256": {
                        path: hashlib.sha256((FIXTURE / path).read_bytes()).hexdigest()
                        for path in citations
                    },
                    "absent_artifacts": []
                    if execution_plan
                    else ["goal", "context_package", "plan", "grounding_selection"],
                }
                provenance.append(bundle)
                result.update(
                    {"passed": not case_failures, "failures": case_failures, "observed": bundle}
                )
        except Exception as exc:
            result["passed"] = False
            result["failures"] = [f"exception: {type(exc).__name__}: {exc}"]
        results.append(result)

    (EVIDENCE / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    (EVIDENCE / "clarification_transcripts.json").write_text(
        json.dumps(transcripts, indent=2) + "\n", encoding="utf-8"
    )
    (EVIDENCE / "replay_trace.json").write_text(
        json.dumps(replay, indent=2) + "\n", encoding="utf-8"
    )
    counts = {
        kind: sum(1 for item in results if item["kind"] == kind and item["passed"])
        for kind in ("clarify", "atomic", "multi_step")
    }
    failures = [item for item in results if not item["passed"]]
    operator_path_failure = (
        None
        if cli_evidence is not None and cli_evidence.get("passed") is True
        else "missing or failed fresh-process CLI plan/resume/replay evidence"
    )
    report = {
        "command": "python scripts/evaluate_phase2_gate.py",
        "python_version": platform.python_version(),
        "registered_case_count": len(results),
        "passed_count": len(results) - len(failures) - (1 if operator_path_failure else 0),
        "failed_count": len(failures) + (1 if operator_path_failure else 0),
        "category_passes": counts,
        "thresholds": {
            "all_cases": "12/12",
            "clarify": "4/4; no Goal/ContextPackage/Plan/profile scan",
            "atomic": "4/4; one work item and zero dependency edges",
            "multi_step": "4/4; exact declared dependencies",
            "fabricated_or_disallowed_file_references": 0,
            "replay_interpreter_calls": 0,
            "replay_repository_rescans": 0,
            "actuation_before_operator_action": 0,
            "operator_path_cli": "fresh-process plan -> inspect -> resume -> replay; no pre-resume dispatch",
        },
        "failures": failures
        + ([{"operator_path_cli": operator_path_failure}] if operator_path_failure else []),
        "operator_path_cli_evidence": cli_evidence,
        "cases": results,
    }
    (EVIDENCE / "evaluation_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "registered_case_count": report["registered_case_count"],
                "passed_count": report["passed_count"],
                "failed_count": report["failed_count"],
                "category_passes": report["category_passes"],
                "failed_cases": [
                    {
                        "id": item["id"],
                        "failure": item.get("failure", "acceptance assertion failed"),
                    }
                    for item in failures
                ],
            },
            indent=2,
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
