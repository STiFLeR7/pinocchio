"""Execute the frozen Phase 4 outcome cases and write a sanitized evidence bundle."""

from __future__ import annotations

import gc
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from nexus_infra import content_hash
from tests.integration.test_phase4_outcome_evidence import (
    FAILING_XML,
    PASSING_XML,
    _submit,
)

ROOT = Path(__file__).resolve().parents[1]
PHASE4 = ROOT / "docs" / "phase4"
EVIDENCE = PHASE4 / "evidence"
EXPECTED = {
    "E1": (True, ("reports/junit.xml",), (PASSING_XML,)),
    "E2": (False, ("reports/junit.xml",), (FAILING_XML,)),
    "E3": (False, ("reports/missing.xml",), (PASSING_XML,)),
    "E4": (True, ("reports/junit.xml",), (FAILING_XML,)),
    "E5": (False, ("reports/one.xml", "reports/two.xml"), (PASSING_XML, FAILING_XML)),
}


def _json(path: Path, value: object) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _summarize_events(events: tuple[Any, ...], workspace: Path) -> list[dict[str, Any]]:
    selected = {
        "planning.execution_plan_assembled",
        "repository_action.requested",
        "repository_action.started",
        "repository_action.completed",
        "repository_action.artifact",
        "validation.evidence_collected",
        "validation.rule_evaluated",
        "validation.completed",
        "validation.failed",
    }
    safe_keys = {
        "action_id",
        "input_digest",
        "kind",
        "command_id",
        "exit_status",
        "plan",
        "node",
        "pipeline_session",
        "sha256",
        "artifact_id",
        "decision",
        "confidence",
        "rule",
        "count",
        "sources",
        "evidence",
        "report",
        "execution_result_ref",
        "identity",
        "condition_id",
        "condition_digest",
        "path",
        "expected_sha256",
        "testcases",
        "failures",
        "errors",
        "skipped",
        "passed",
        "artifact_ref",
        "evidence_refs",
        "satisfied",
        "failed",
        "missing_evidence",
    }
    output: list[dict[str, Any]] = []
    for event in events:
        if event.type not in selected:
            continue
        payload = {key: value for key, value in event.payload.items() if key in safe_keys}
        if event.type == "repository_action.requested":
            payload = {
                "action_id": event.payload.get("action_id"),
                "input_digest": event.payload.get("input_digest"),
                "action_kind": event.payload.get("action", {}).get("kind"),
                "command_id": event.payload.get("action", {}).get("command_id"),
            }
        if event.type == "repository_action.artifact":
            payload["path"] = f"<artifact>/{Path(str(event.payload.get('path', ''))).name}"
        outcome = event.payload.get("outcome")
        if isinstance(outcome, dict):
            payload["action_outcome"] = {
                key: outcome.get(key)
                for key in (
                    "action_id",
                    "input_digest",
                    "kind",
                    "command_id",
                    "exit_status",
                    "output_ref",
                )
            }
        if isinstance(payload.get("evidence"), list):
            payload["evidence"] = [
                _safe_evidence(item) for item in payload["evidence"] if isinstance(item, dict)
            ]
        if isinstance(payload.get("report"), dict):
            report = payload["report"]
            payload["report"] = {
                "identity": report.get("identity"),
                "decision": report.get("decision"),
                "evidence_refs": report.get("evidence_refs", []),
                "reasoning_trace": report.get("reasoning_trace", []),
            }
        output.append(
            {
                "id": event.identifier,
                "type": event.type,
                "producer": event.producer,
                "correlation": event.correlation_identifier,
                "payload": payload,
            }
        )
    return output


def _safe_evidence(item: dict[str, Any]) -> dict[str, Any]:
    observed = item.get("observed", {})
    safe_observed = {
        key: value
        for key, value in observed.items()
        if key
        in {
            "condition_id",
            "condition_digest",
            "path",
            "sha256",
            "expected_sha256",
            "passed",
            "failures",
            "errors",
            "skipped",
            "testcases",
            "action_id",
            "action_digest",
            "plan",
            "node",
            "pipeline_session",
            "artifact_ref",
            "kind",
            "artifact",
            "exit_status",
            "outcome",
        }
    }
    return {
        "identity": item.get("identity"),
        "source": item.get("source"),
        "kind": item.get("kind"),
        "observed": safe_observed,
        "derived_from": item.get("derived_from", []),
    }


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    cases = json.loads((PHASE4 / "cases.json").read_text(encoding="utf-8"))["cases"]
    expected_by_id = {item["id"]: item["expected_verdict"] for item in cases}
    results: list[dict[str, Any]] = []
    traces: dict[str, list[dict[str, Any]]] = {}
    inventories: dict[str, dict[str, str]] = {}
    failures: list[str] = []

    with tempfile.TemporaryDirectory(prefix="nexus-phase4-gate-") as root_text:
        root = Path(root_text)
        for case_id, (file_condition, reports, contents) in EXPECTED.items():
            case_root = root / case_id
            case_root.mkdir()
            workspace = case_root / "workspace"
            context, response, terminal, _request = _submit(
                case_root,
                case_id,
                file_condition=file_condition,
                reports=reports,
                contents=contents,
                db_path=case_root / "events.sqlite",
            )
            actual = str(terminal.payload["decision"])
            expected = expected_by_id[case_id]
            if actual != expected:
                failures.append(f"{case_id}: expected {expected}, got {actual}")
            report = terminal.payload["report"]
            evidence_event = next(
                event
                for event in context.infrastructure.event_store.read_all()
                if event.type == "validation.evidence_collected"
                and event.identifier.startswith(
                    f"evt-{report['session_ref']['identifier']}-val-evidence-"
                )
            )
            evidence_items = evidence_event.payload.get("evidence", [])
            file_hashes: dict[str, str] = {}
            for path in (workspace / "README.md", *(workspace / relative for relative in reports)):
                if path.is_file():
                    file_hashes[path.relative_to(workspace).as_posix()] = hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
            action = next(
                event
                for event in context.infrastructure.event_store.read_all()
                if event.type == "repository_action.requested"
            )
            frozen_plan = response.execution_plan
            assert frozen_plan is not None
            work_package = frozen_plan.work_packages[0]
            conditions = work_package.completion_criteria.get("outcome_conditions")
            condition_digest = content_hash(
                json.dumps(conditions, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            )
            observed_digests = {
                item.get("observed", {}).get("condition_digest")
                for item in evidence_items
                if item.get("observed", {}).get("condition_digest")
            }
            if observed_digests and observed_digests != {condition_digest}:
                failures.append(f"{case_id}: condition evidence digest differs from frozen plan")
            metadata: dict[str, Any] = next(
                (
                    item.get("observed", {})
                    for item in evidence_items
                    if item.get("source") == "runtime_metadata"
                ),
                {},
            )
            action_completed = next(
                event
                for event in context.infrastructure.event_store.read_all()
                if event.type == "repository_action.completed"
            )
            action_exit_status = action_completed.payload.get("outcome", {}).get("exit_status")
            action_output = next(
                (
                    event
                    for event in context.infrastructure.event_store.read_all()
                    if event.type == "repository_action.artifact"
                    and event.payload.get("action_id") == action.payload.get("action_id")
                    and event.payload.get("kind") == "action_output"
                ),
                None,
            )
            runtime_terminal = next(
                (
                    event
                    for event in context.infrastructure.event_store.read_all()
                    if event.type == "runtime.completed"
                    and event.identifier.startswith(f"evt-{report['session_ref']['identifier']}-")
                ),
                None,
            )
            runtime_exit_status = metadata.get("exit_status")
            if case_id in {"E2", "E4"} and (
                action_exit_status != 0
                or runtime_exit_status != 0
                or runtime_terminal is None
                or runtime_terminal.payload.get("exit_status") != 0
            ):
                failures.append(f"{case_id}: action or runtime exit was not zero")
            if action_exit_status != 0:
                failures.append(f"{case_id}: action terminal exit was not zero")
            results.append(
                {
                    "id": case_id,
                    "expected": expected,
                    "actual": actual,
                    "runtime_exit_status": metadata.get("exit_status"),
                    "action_exit_status": action_exit_status,
                    "runtime_terminal_exit_status": runtime_terminal.payload.get("exit_status")
                    if runtime_terminal is not None
                    else None,
                    "runtime_completed": response.runtime_completed,
                    "outcome_accepted": response.outcome_accepted,
                    "conditions": conditions,
                    "condition_digest": condition_digest,
                    "evidence_refs": [item.get("identity") for item in evidence_items],
                    "source_hashes": file_hashes,
                    "action_id": action.payload.get("action_id"),
                    "action_digest": action.payload.get("input_digest"),
                    "action_output_artifact_ref": action_output.identifier
                    if action_output is not None
                    else None,
                    "action_output_sha256": action_output.payload.get("sha256")
                    if action_output is not None
                    else None,
                    "declared_report_inventory": {
                        relative: (workspace / relative).is_file() for relative in reports
                    },
                }
            )
            traces[case_id] = _summarize_events(
                tuple(context.infrastructure.event_store.read_all()), workspace
            )
            inventories[case_id] = file_hashes
            expected_report_path = case_root / "expected-report.json"
            _json(expected_report_path, report)
            session = str(report["session_ref"]["identifier"])
            del context
            gc.collect()
            replay = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.phase4_replay_worker",
                    "--db",
                    str(case_root / "events.sqlite"),
                    "--expected",
                    str(expected_report_path),
                    "--session",
                    session,
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            replay_data = json.loads(replay.stdout)
            if (
                not replay_data["same_report"]
                or replay_data["operator_restart_decision"] != expected
                or not replay_data["operator_restart_runtime_completed"]
                or replay_data["validation_terminals_before"]
                != replay_data["validation_terminals_after"]
                or replay_data["action_starts_before"] != replay_data["action_starts_after"]
                or not replay_data["operator_restart_pipeline_entered"]
                or replay_data["same_store_restart_decision"] != expected
                or replay_data["same_store_restart_validation_terminals_before"]
                != replay_data["same_store_restart_validation_terminals_after"]
                or replay_data["same_store_restart_action_starts_before"]
                != replay_data["same_store_restart_action_starts_after"]
                or replay_data["same_store_restart_responses_before"]
                != replay_data["same_store_restart_responses_after"]
                or replay_data["operator_restart_validation_terminals_before"]
                != replay_data["operator_restart_validation_terminals_after"]
                or replay_data["operator_restart_action_starts_before"]
                != replay_data["operator_restart_action_starts_after"]
                or replay_data["operator_restart_responses_after"] != 1
            ):
                failures.append(
                    f"{case_id}: fresh-process engine/operator replay differed or caused side effects"
                )
            results[-1]["replay"] = replay_data

    expected_digest = hashlib.sha256((PHASE4 / "cases.json").read_bytes()).hexdigest()
    report = {
        "gate": "phase4-independent-outcome-evidence-v1",
        "registered_cases_sha256": expected_digest,
        "case_count": len(results),
        "passed_cases": sum(result["actual"] == result["expected"] for result in results),
        "false_passes": sum(
            result["actual"] == "passed" and result["expected"] != "passed" for result in results
        ),
        "failures": failures,
        "results": results,
        "thresholds": {
            "expected_verdicts": "5/5",
            "false_passes": 0,
            "replay_external_evidence_reads": 0,
            "replay_runtime_dispatches": 0,
            "replay_duplicate_validation_decisions": 0,
            "operator_restart_pipeline_entry": "5/5",
            "same_store_operator_restart_verdict_matches": "5/5",
            "same_store_restart_duplicate_side_effects": 0,
            "operator_restart_duplicate_verdict_events": 0,
            "operator_restart_duplicate_action_starts": 0,
            "operator_restart_verdict_matches": "5/5",
            "action_exit_status_zero": "5/5",
            "runtime_exit_status_zero_on_failed_assertion_cases": "2/2",
        },
    }
    _json(EVIDENCE / "evaluation_report.json", report)
    _json(EVIDENCE / "event_traces.json", traces)
    _json(EVIDENCE / "source_hash_manifest.json", inventories)
    _json(
        EVIDENCE / "limitations.json",
        {
            "file_sha256": "Verifies exact bytes at a workspace-relative path; it does not establish semantic correctness.",
            "junit_xml": "Counts testcase failure/error nodes from a named allow-listed action report; it does not establish test-suite completeness or test quality.",
            "runtime": "Exit status and process completion are recorded separately and cannot override JUnit evidence.",
        },
    )
    return 1 if failures or len(results) != 5 else 0


if __name__ == "__main__":
    raise SystemExit(main())
