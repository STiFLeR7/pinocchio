"""Evaluate the frozen Phase 5 cross-run Knowledge retrieval gate."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import (
    ConfidenceLadder,
    PolicyCategory,
    PolicyDecision,
)
from nexus_core.contracts.status import PolicyStatus
from nexus_core.domain.policy import Policy
from nexus_infra import build_durable_infrastructure, content_hash
from nexus_knowledge.policy import DEFAULT_PERSISTENCE_POLICY, PersistencePolicy
from nexus_policy import KNOWLEDGE_GROUNDING_ACTION_CLASS
from nexus_workflows.spine import (
    SpineControl,
    SpineStage,
    build_constitutional_pipeline,
    spine_reference_request,
)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "phase5" / "evidence"
GATE = ROOT / "docs" / "phase5" / "cases.json"
WORKER = ROOT / "tests" / "e2e" / "phase5_replay_worker.py"
SUBJECT = "architecture summary generation"


def _request(
    run: str, *, subject: str = SUBJECT, fail: bool = False, supersedes: str | None = None
) -> Any:
    return replace(
        spine_reference_request(run=run, fail=fail),
        knowledge_subject=subject,
        knowledge_supersedes_subject=supersedes,
    )


def _pipeline(
    database: Path,
    policy: PersistencePolicy = DEFAULT_PERSISTENCE_POLICY,
    *,
    learning: bool = True,
) -> tuple[Any, Any]:
    infrastructure = build_durable_infrastructure(str(database))
    context = build_constitutional_pipeline(
        infrastructure,
        knowledge_policy=policy,
        learning=learning,
    )
    return infrastructure, context


def _plan_fingerprint(events: tuple[Any, ...], correlation: str) -> tuple[str, tuple[str, ...]]:
    event = next(
        event
        for event in events
        if event.type == "planning.execution_plan_assembled"
        and event.correlation_identifier == correlation
    )
    plan = event.payload["execution_plan"]
    return content_hash(plan), tuple(
        package["identifier"] for package in plan.get("work_packages", [])
    )


def _strategy_influences(events: tuple[Any, ...], correlation: str) -> list[dict[str, Any]]:
    result = []
    for event in events:
        if event.type != "engineering.strategized" or event.correlation_identifier != correlation:
            continue
        strategy = event.payload.get("strategy", {})
        result.append(
            {
                "knowledge_refs": strategy.get("knowledge_refs", []),
                "recommendation_knowledge_influences": [
                    influence
                    for facet in strategy.get("facets", [])
                    for influence in facet.get("knowledge_influences", [])
                ],
            }
        )
    return result


def _context_influences(events: tuple[Any, ...], correlation: str) -> list[str]:
    refs: list[str] = []
    for event in events:
        if (
            event.type != "context.grounding.selected"
            or event.correlation_identifier != correlation
        ):
            continue
        refs.extend(
            row["identifier"]
            for row in event.payload.get("selected", [])
            if row.get("artifact_type") == "knowledge" and row.get("selected")
        )
    return sorted(set(refs))


def _validation_facts(events: tuple[Any, ...], correlation: str) -> list[dict[str, Any]]:
    return [
        {
            "report_ref": event.payload.get("report", {}).get("identity"),
            "decision": event.payload.get("report", {}).get("decision"),
            "evidence_refs": [
                ref.get("identifier")
                for ref in event.payload.get("report", {}).get("evidence_refs", [])
            ],
        }
        for event in events
        if event.type in {"validation.completed", "validation.failed"}
        and event.correlation_identifier == correlation
    ]


def _event_summary(events: tuple[Any, ...], *, correlations: set[str]) -> list[dict[str, Any]]:
    retained_types = {
        "pipeline.knowledge_grounded",
        "engineering.strategized",
        "context.grounding.selected",
        "plan.created",
        "planning.completed",
        "planning.execution_plan_assembled",
        "validation.evidence_collected",
        "validation.completed",
        "validation.failed",
        "knowledge.candidate_received",
        "knowledge.candidate_accepted",
        "knowledge.candidate_rejected",
        "knowledge.item_created",
        "knowledge.item_evolved",
        "knowledge.item_superseded",
        "knowledge.item_expired",
        "knowledge.item_deprecated",
        "knowledge.feedback_recorded",
        "policy.registered",
    }
    safe_fields = (
        "candidate",
        "candidate_id",
        "subject_key",
        "decision",
        "outcome",
        "failed_requirement",
        "version",
        "superseded",
        "state",
        "feedback_id",
        "effect",
        "actor",
    )
    result = []
    for event in events:
        if event.correlation_identifier not in correlations or event.type not in retained_types:
            continue
        payload = {key: event.payload[key] for key in safe_fields if key in event.payload}
        result.append(
            {
                "identifier": event.identifier,
                "type": event.type,
                "producer": event.producer,
                "correlation": event.correlation_identifier,
                "facts": payload,
            }
        )
    return result


def _source_item(
    context: Any,
    run: str,
    subject: str = SUBJECT,
    *,
    fail: bool = False,
    supersedes: str | None = None,
) -> dict[str, Any]:
    request = _request(run, subject=subject, fail=fail, supersedes=supersedes)
    result = context.coordinator.run(request)
    return {
        "request": request,
        "run": result,
        "selected": list(result.knowledge_item_ids),
        "correlation": request.correlation,
    }


def _deny_grounding(policy_context: Any) -> None:
    policy_context.registry.register(
        Policy(
            identity="policy.phase5.deny-grounding",
            version="1",
            purpose="Fixture denial for Phase 5 exclusion coverage.",
            conditions={
                "attr": "action_class",
                "op": "eq",
                "value": KNOWLEDGE_GROUNDING_ACTION_CLASS,
            },
            decision=PolicyDecision.DENY,
            priority=100,
            owner="phase5-gate-fixture",
            status=PolicyStatus.ENABLED,
            category=PolicyCategory.GOVERNANCE,
            governed_action_class=KNOWLEDGE_GROUNDING_ACTION_CLASS,
        )
    )


def _build_relevant(
    case_id: str, database: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]], Any]:
    policy = DEFAULT_PERSISTENCE_POLICY
    if case_id == "R6":
        policy = PersistencePolicy(serving_confidence_floor=ConfidenceLadder.OBSERVED)
    infrastructure, context = _pipeline(database, policy)
    coordinator = context.coordinator
    provenance_runs: list[dict[str, Any]] = []

    if case_id == "R4":
        old_subject = "phase5 previous subject"
        replacement_subject = "phase5 replacement subject"
        old = _source_item(context, "R4-old", subject=old_subject)
        replacement = _source_item(
            context,
            "R4-replacement",
            subject=replacement_subject,
            supersedes=old_subject,
        )
        provenance_runs.extend([old, replacement])
        expected_label = "replacement"
        second_subject = replacement_subject
        expected_identity = replacement["selected"][0]
    else:
        first = _source_item(context, f"{case_id}-source")
        provenance_runs.append(first)
        if case_id == "R3":
            provenance_runs.append(_source_item(context, "R3-source2"))
        if case_id == "R5":
            item_id = first["selected"][0]
            item = next(
                item for item in coordinator.inspect_knowledge() if item.identity == item_id
            )
            run_ref = Reference.model_validate(item.metadata["source_run_refs"][0])
            feedback_ref = coordinator.record_knowledge_feedback(
                item_id,
                actor="phase5-fixture-operator",
                source_run_ref=run_ref,
                effect="support",
                feedback_id="phase5-R5-positive-feedback",
            )
        else:
            feedback_ref = None
        expected_label = "latest_relevant" if case_id == "R3" else "relevant"
        second_subject = SUBJECT
        expected_identity = first["selected"][0]

    second_request = _request(f"{case_id}-second", subject=second_subject)
    baseline_infra, baseline_context = _pipeline(
        database.with_name(f"{database.stem}-baseline.db"), learning=False
    )
    baseline = baseline_context.coordinator.run(second_request)
    baseline_events = tuple(baseline_infra.event_store.read_all())

    seeded = coordinator.run(second_request)
    seeded_events = tuple(infrastructure.event_store.read_all())
    if case_id == "R3":
        evolved_item = next(
            item for item in coordinator.inspect_knowledge() if item.identity == expected_identity
        )
        metadata = evolved_item.metadata or {}
        report_refs = metadata.get("validation_report_refs", [])
        assert len({ref["identifier"] for ref in report_refs}) >= 2, (
            "R3: latest evolved item must retain two distinct passed reports"
        )
        assert len({ref.identifier for ref in evolved_item.evidence_refs}) >= 2, (
            "R3: latest evolved item must retain evidence from both reports"
        )
        assert any(
            event.type == "knowledge.item_evolved"
            and event.payload.get("subject_key") == expected_identity
            for event in seeded_events
        ), "R3: no evolved version event recorded"
    if case_id == "R4":
        supersession = next(
            (
                event
                for event in seeded_events
                if event.type == "knowledge.item_superseded"
                and event.payload.get("superseded") == old["selected"][0]
            ),
            None,
        )
        assert supersession is not None
        assert supersession.payload.get("subject_key") == expected_identity
    plan_fingerprint, work_items = _plan_fingerprint(seeded_events, second_request.correlation)
    baseline_fingerprint, baseline_work_items = _plan_fingerprint(
        baseline_events, second_request.correlation
    )
    selected = list(seeded.knowledge_grounding.selected_ids) if seeded.knowledge_grounding else []
    selected_label = expected_label if expected_identity in selected else None
    expected_verdicts = list(seeded.validation_decisions)
    baseline_verdicts = list(baseline.validation_decisions)
    comparison = {
        "case_id": case_id,
        "baseline": {
            "selected_ids": [],
            "engineering_influences": _strategy_influences(
                baseline_events, second_request.correlation
            ),
            "context_influences": _context_influences(baseline_events, second_request.correlation),
            "plan_fingerprint": baseline_fingerprint,
            "work_item_ids": list(baseline_work_items),
            "validation_verdicts": baseline_verdicts,
            "evidence_refs": _validation_facts(baseline_events, second_request.correlation),
        },
        "seeded": {
            "selected_ids": selected,
            "engineering_influences": _strategy_influences(
                seeded_events, second_request.correlation
            ),
            "context_influences": _context_influences(seeded_events, second_request.correlation),
            "plan_fingerprint": plan_fingerprint,
            "work_item_ids": list(work_items),
            "validation_verdicts": expected_verdicts,
            "evidence_refs": _validation_facts(seeded_events, second_request.correlation),
        },
        "observed_comparison": (
            "same"
            if baseline_fingerprint == plan_fingerprint and baseline_verdicts == expected_verdicts
            else "unknown"
        ),
        "causal_claim": False,
    }

    assert selected_label == expected_label, f"{case_id}: expected {expected_label} in selection"
    assert expected_verdicts and all(value == "passed" for value in expected_verdicts)

    before = tuple(infrastructure.event_store.read_all())
    infrastructure.close()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    worker = subprocess.run(
        [sys.executable, str(WORKER), str(database), f"{case_id}-second", second_subject],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    replay = json.loads(worker.stdout)
    replay_mismatches = []
    if replay["selection"] != selected:
        replay_mismatches.append("selected_ids")
    if replay["knowledge_candidates_after"] != replay["knowledge_candidates_before"]:
        replay_mismatches.append("knowledge_acceptance_event_count")
    if replay["runtime_after"] != replay["runtime_before"]:
        replay_mismatches.append("runtime_dispatch_count")
    if any(event_type != "pipeline.resumed" for event_type in replay["added_event_types"]):
        replay_mismatches.append("durable_event_set_changed")
    if replay["after_types"].count("pipeline.knowledge_grounded") != sum(
        event.type == "pipeline.knowledge_grounded" for event in before
    ):
        replay_mismatches.append("knowledge_grounding_event_count")
    if not any(expected_identity in refs for refs in replay["context_refs"]):
        replay_mismatches.append("context_refs")

    source_correlations = {entry["correlation"] for entry in provenance_runs}
    provenance = []
    for entry in provenance_runs:
        run_events = tuple(
            event for event in seeded_events if event.correlation_identifier == entry["correlation"]
        )
        provenance.append(
            {
                "request_id": entry["request"].identity,
                "goal_ref": f"goal-{entry['request'].identity}",
                "runtime_verdicts": list(entry["run"].validation_decisions),
                "knowledge_item_ids": entry["selected"],
                "knowledge_chain": _event_summary(run_events, correlations=source_correlations),
                "accepted_versions": [
                    event.payload["version_data"]
                    for event in run_events
                    if event.producer == "knowledge"
                    and isinstance(event.payload.get("version_data"), dict)
                ],
                "passed_report_ids": [
                    event.payload.get("report", {}).get("identity")
                    for event in run_events
                    if event.type == "validation.completed"
                    and event.producer == "validation"
                    and event.payload.get("report", {}).get("decision") == "passed"
                ],
            }
        )
    if case_id == "R5":
        provenance[-1]["feedback_ref"] = feedback_ref.identifier
        feedback_event = next(
            event for event in seeded_events if event.identifier == feedback_ref.identifier
        )
        provenance[-1]["feedback_event"] = {
            "identifier": feedback_event.identifier,
            "actor": feedback_event.payload["actor"],
            "effect": feedback_event.payload["effect"],
            "source_run_ref": feedback_event.payload["source_run_ref"],
        }

    report = {
        "case_id": case_id,
        "expected_label": expected_label,
        "expected_identity": expected_identity,
        "selected_ids": selected,
        "selected_label": selected_label,
        "all_source_reports_passed": all(
            all(value == "passed" for value in entry["run"].validation_decisions)
            for entry in provenance_runs
        ),
        "source_runs": len(provenance_runs),
        "plan_fingerprint": plan_fingerprint,
        "validation_verdicts": expected_verdicts,
        "replay_mismatches": replay_mismatches,
        "accepted_versions": [
            event.payload["version_data"]
            for event in seeded_events
            if event.producer == "knowledge" and isinstance(event.payload.get("version_data"), dict)
        ],
    }
    trace_events = tuple(
        event
        for event in seeded_events
        if event.correlation_identifier in {*source_correlations, second_request.correlation}
    )
    trace = _event_summary(
        trace_events, correlations={*source_correlations, second_request.correlation}
    )
    if baseline_infra:
        baseline_infra.close()
    return report, comparison, {"cases": provenance}, trace, replay


def _build_excluded(
    case_id: str, database: Path
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    policy = DEFAULT_PERSISTENCE_POLICY
    if case_id == "X2":
        policy = PersistencePolicy(freshness_ttl_seconds=1)
    infrastructure, context = _pipeline(database, policy)
    coordinator = context.coordinator
    subject = SUBJECT
    setup: list[dict[str, Any]] = []

    if case_id == "X1":
        source = _source_item(context, "X1-failed", fail=True)
        setup.append(source)
    elif case_id == "X5":
        unrelated_subject = "unrelated database migration runbook"
        setup.append(_source_item(context, "X5-unrelated", subject=unrelated_subject))
    else:
        if case_id == "X4":
            old = "phase5 retired subject"
            new = "phase5 active replacement"
            setup.append(_source_item(context, "X4-old", subject=old))
            setup.append(_source_item(context, "X4-new", subject=new, supersedes=old))
            subject = old
        else:
            setup.append(_source_item(context, f"{case_id}-source"))
        if case_id == "X2":
            expired = coordinator._knowledge.engine.maintain("1970-01-01T00:00:03+00:00")
            assert expired
        elif case_id == "X3":
            item_id = setup[0]["selected"][0]
            item = next(
                item for item in coordinator.inspect_knowledge() if item.identity == item_id
            )
            run_ref = Reference.model_validate(item.metadata["source_run_refs"][0])
            coordinator.record_knowledge_feedback(
                item_id,
                actor="phase5-fixture-operator",
                source_run_ref=run_ref,
                effect="contradict",
                feedback_id="phase5-X3-contradiction",
            )
        elif case_id == "X6":
            _deny_grounding(context.policy)

    second_request = _request(f"{case_id}-query", subject=SUBJECT if case_id == "X5" else subject)
    second = coordinator.run(
        second_request,
        control=SpineControl(stop_after_stage=SpineStage.PLANNING),
    )
    selected = list(second.knowledge_grounding.selected_ids) if second.knowledge_grounding else []
    assert not selected, f"{case_id}: excluded item surfaced: {selected}"

    events = tuple(infrastructure.event_store.read_all())
    chain: list[dict[str, Any]] = []
    for setup_run in setup:
        selected_corr = setup_run["correlation"]
        chain.extend(
            _event_summary(
                tuple(event for event in events if event.correlation_identifier == selected_corr),
                correlations={selected_corr},
            )
        )
    source_correlations = {entry["correlation"] for entry in setup}
    source_events = tuple(
        event for event in events if event.correlation_identifier in source_correlations
    )
    report = {
        "case_id": case_id,
        "expected_selected": [],
        "selected_ids": selected,
        "source_runs": len(setup),
        "candidate_rejections": sum(
            event.type == "knowledge.candidate_rejected" for event in events
        ),
        "policy_decision": (
            second.knowledge_grounding.decision if second.knowledge_grounding else "missing"
        ),
        "lifecycle_facts": [
            event.type
            for event in events
            if event.type
            in {
                "knowledge.item_expired",
                "knowledge.item_deprecated",
                "knowledge.item_superseded",
            }
        ],
        "accepted_versions": [
            event.payload["version_data"]
            for event in events
            if event.producer == "knowledge" and isinstance(event.payload.get("version_data"), dict)
        ],
    }
    trace = _event_summary(events, correlations={event.correlation_identifier for event in events})
    infrastructure.close()
    return (
        report,
        {
            "case_id": case_id,
            "knowledge_chain": chain,
            "accepted_versions": [
                event.payload["version_data"]
                for event in source_events
                if event.producer == "knowledge"
                and isinstance(event.payload.get("version_data"), dict)
            ],
            "passed_report_ids": [
                event.payload.get("report", {}).get("identity")
                for event in source_events
                if event.type == "validation.completed"
                and event.producer == "validation"
                and event.payload.get("report", {}).get("decision") == "passed"
            ],
        },
        trace,
    )


def main() -> int:
    frozen = json.loads(GATE.read_text(encoding="utf-8"))
    case_reports: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    provenance_bundle: dict[str, Any] = {"source_runs": []}
    traces: dict[str, Any] = {}
    replay_traces: list[dict[str, Any]] = []
    id_map: dict[str, dict[str, str]] = {}
    failures: list[str] = []

    with tempfile.TemporaryDirectory(prefix="nexus-phase5-") as temporary:
        work = Path(temporary)
        for case in frozen["cases"]:
            case_id = case["id"]
            try:
                if case["relevant"]:
                    report, comparison, provenance, trace, replay = _build_relevant(
                        case_id, work / f"{case_id}.db"
                    )
                    case_reports.append(report)
                    comparisons.append(comparison)
                    provenance_bundle["source_runs"].extend(provenance["cases"])
                    traces[case_id] = trace
                    replay_traces.append(
                        {
                            "case_id": case_id,
                            "selection": replay["selection"],
                            "context_refs": replay["context_refs"],
                            "runtime_count_before_after": [
                                replay["runtime_before"],
                                replay["runtime_after"],
                            ],
                            "acceptance_count_before_after": [
                                replay["knowledge_candidates_before"],
                                replay["knowledge_candidates_after"],
                            ],
                            "before_ids": replay["before_ids"],
                            "after_ids": replay["after_ids"],
                            "added_event_types": replay["added_event_types"],
                            "mismatches": report["replay_mismatches"],
                        }
                    )
                    id_map[case_id] = {report["expected_label"]: report["expected_identity"]}
                else:
                    report, provenance, trace = _build_excluded(case_id, work / f"{case_id}.db")
                    case_reports.append(report)
                    provenance_bundle["source_runs"].append(provenance)
                    traces[case_id] = trace
            except Exception as error:  # keep all frozen case failures visible in one report
                failures.append(f"{case_id}: {type(error).__name__}: {error}")
                case_reports.append(
                    {
                        "case_id": case_id,
                        "selected_ids": [],
                        "error": f"{type(error).__name__}: {error}",
                    }
                )

    relevant = [report for report in case_reports if report["case_id"].startswith("R")]
    excluded = [report for report in case_reports if report["case_id"].startswith("X")]
    relevant_surfaced = sum(bool(report.get("selected_label")) for report in relevant)
    excluded_surfaced = sum(bool(report.get("selected_ids")) for report in excluded)
    comparisons_complete = len(comparisons) == 6
    replay_mismatches = sum(len(item["mismatches"]) for item in replay_traces)
    bad_promotions = 0
    missing_source_refs = 0
    missing_feedback_attribution = 0
    valid_reports = {
        report_id
        for run in provenance_bundle["source_runs"]
        if isinstance(run, dict)
        for report_id in run.get("passed_report_ids", [])
        if isinstance(report_id, str)
    }
    for run in provenance_bundle["source_runs"]:
        if isinstance(run, dict) and "runtime_verdicts" in run:
            for version in run.get("accepted_versions", []):
                if version.get("confidence") == "proven":
                    report_refs = {
                        ref.get("identifier")
                        for ref in version.get("validation_report_refs", [])
                        if isinstance(ref, dict)
                    }
                    if not report_refs or not report_refs.issubset(valid_reports):
                        bad_promotions += 1
                    if not all(
                        version.get(key)
                        for key in (
                            "source_goal_ref",
                            "source_run_refs",
                            "validation_report_refs",
                            "evidence_refs",
                        )
                    ):
                        missing_source_refs += 1
    r5_feedback = next(
        (
            run
            for run in provenance_bundle["source_runs"]
            if isinstance(run, dict) and run.get("feedback_event")
        ),
        None,
    )
    if not r5_feedback or not all(
        r5_feedback["feedback_event"].get(field)
        for field in ("identifier", "actor", "effect", "source_run_ref")
    ):
        missing_feedback_attribution = 1

    thresholds = {
        "relevant_surfaced": f"{relevant_surfaced}/6",
        "relevant_surfaced_minimum_met": relevant_surfaced >= 5,
        "excluded_surfaced": excluded_surfaced,
        "excluded_surfaced_maximum_met": excluded_surfaced == 0,
        "failed_unknown_partial_or_unresolved_promoted_proven": bad_promotions,
        "accepted_items_missing_source_goal_run_report_or_evidence_refs": missing_source_refs,
        "feedback_decisions_missing_actor_event_or_source_run": missing_feedback_attribution,
        "relevant_cases_with_comparison": f"{len(comparisons)}/6",
        "relevant_comparisons_complete": comparisons_complete,
        "fresh_process_replay_mismatches": replay_mismatches,
        "replay_no_new_runtime_or_acceptance": all(
            row["runtime_count_before_after"][0] == row["runtime_count_before_after"][1]
            and row["acceptance_count_before_after"][0] == row["acceptance_count_before_after"][1]
            and row["added_event_types"] == ["pipeline.resumed"]
            for row in replay_traces
        ),
        "failures": failures,
    }
    for label, condition in (
        ("relevant threshold", thresholds["relevant_surfaced_minimum_met"]),
        ("excluded threshold", thresholds["excluded_surfaced_maximum_met"]),
        ("no invalid proven promotion", bad_promotions == 0),
        ("accepted provenance complete", missing_source_refs == 0),
        ("feedback attribution", missing_feedback_attribution == 0),
        ("second run comparison", comparisons_complete),
        ("fresh process replay", replay_mismatches == 0),
        ("no replay side effects", thresholds["replay_no_new_runtime_or_acceptance"]),
        ("no case exceptions", not failures),
    ):
        if not condition:
            failures.append(f"threshold failed: {label}")

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    report = {
        "gate": frozen["gate"],
        "status": "passed" if not failures else "failed",
        "thresholds": thresholds,
        "cases": case_reports,
        "failure_list": failures,
        "evidence_limitations": [
            "The fixture uses deterministic local Claude stubs; it does not claim production model causality.",
            "Plan and validation differences are observed comparisons only, not causal attribution.",
        ],
    }
    (EVIDENCE / "evaluation_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (EVIDENCE / "actual_id_map.json").write_text(
        json.dumps(id_map, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (EVIDENCE / "provenance_bundle.json").write_text(
        json.dumps(provenance_bundle, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (EVIDENCE / "second_run_comparison.json").write_text(
        json.dumps(comparisons, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (EVIDENCE / "replay_trace.json").write_text(
        json.dumps(replay_traces, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (EVIDENCE / "event_traces.json").write_text(
        json.dumps(traces, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"status": report["status"], "thresholds": thresholds}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
