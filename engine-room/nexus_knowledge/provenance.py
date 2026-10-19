"""Resolve Phase 5 source claims against the shared durable event log."""

from __future__ import annotations

from collections.abc import Iterable

from nexus_core.domain.event import Event
from nexus_knowledge.candidate import KnowledgeCandidate


def verify_candidate_sources(candidate: KnowledgeCandidate, events: Iterable[Event]) -> bool:
    """Verify every candidate report, run, goal, and evidence reference against durable facts."""
    if (
        candidate.source_goal_ref is None
        or candidate.source_goal_ref.target_type != "goal"
        or not candidate.source_run_refs
        or not candidate.validation_report_refs
        or not candidate.evidence_refs
    ):
        return False
    event_list = tuple(events)
    reports: dict[str, tuple[str, str, dict[str, object]]] = {}
    for event in event_list:
        if event.type in {"validation.completed", "validation.failed"}:
            report_value = event.payload.get("report")
            if isinstance(report_value, dict):
                report_identity = report_value.get("identity")
                if isinstance(report_identity, str):
                    reports[report_identity] = (event.type, event.producer, report_value)
    plans: list[dict[str, object]] = []
    completed_plans = {
        (event.payload.get("plan"), event.correlation_identifier)
        for event in event_list
        if event.type == "planning.completed" and event.producer == "planning"
    }
    for event in event_list:
        if event.type == "planning.execution_plan_assembled":
            value = event.payload.get("execution_plan")
            if isinstance(value, dict):
                plans.append(value)
        elif (
            event.type == "plan.created"
            and event.producer == "planning"
            and (event.payload.get("plan"), event.correlation_identifier) in completed_plans
        ):
            goal_id = event.payload.get("goal")
            packages = event.payload.get("work_packages")
            if isinstance(goal_id, str) and isinstance(packages, list):
                plans.append(
                    {
                        "goal_ref": {"target_type": "goal", "identifier": goal_id},
                        "work_packages": [
                            {"identifier": package_id}
                            for package_id in packages
                            if isinstance(package_id, str)
                        ],
                    }
                )

    report_refs = {ref.identifier for ref in candidate.validation_report_refs}
    if (
        len(report_refs) != len(candidate.validation_report_refs)
        or any(ref.target_type != "validation_report" for ref in candidate.validation_report_refs)
        or any(ref.target_type != "runtime_session" for ref in candidate.source_run_refs)
        or any(ref.target_type != "evidence" for ref in candidate.evidence_refs)
    ):
        return False
    run_ids: set[str] = set()
    used_evidence: set[str] = set()
    for identity in report_refs:
        terminal = reports.get(identity)
        if terminal is None:
            return False
        terminal_type, producer, report = terminal
        if terminal_type != "validation.completed" or producer != "validation":
            return False
        if report.get("decision") != "passed":
            return False
        session = report.get("session_ref")
        package = report.get("work_package_ref")
        report_evidence = report.get("evidence_refs")
        if not isinstance(session, dict) or not isinstance(package, dict):
            return False
        if (
            session.get("target_type") != "runtime_session"
            or package.get("target_type") != "work_package"
        ):
            return False
        run_id = session.get("identifier")
        package_id = package.get("identifier")
        if not isinstance(run_id, str) or not isinstance(package_id, str):
            return False
        run_ids.add(run_id)
        collected_ids: set[str] = set()
        for event in event_list:
            if (
                event.type == "validation.evidence_collected"
                and event.producer == "validation"
                and event.correlation_identifier == report.get("correlation_identifier")
                and event.identifier.startswith(f"evt-{run_id}-val-evidence-")
            ):
                evidence = event.payload.get("evidence")
                if isinstance(evidence, list):
                    collected_ids.update(
                        value["identity"]
                        for value in evidence
                        if isinstance(value, dict) and isinstance(value.get("identity"), str)
                    )
        if not collected_ids:
            return False
        if not isinstance(report_evidence, list):
            return False
        for ref in report_evidence:
            if (
                not isinstance(ref, dict)
                or ref.get("target_type") != "evidence"
                or not isinstance(ref.get("identifier"), str)
            ):
                return False
            evidence_id = ref["identifier"]
            if evidence_id not in collected_ids:
                return False
            used_evidence.add(evidence_id)
        if not any(_plan_contains_package(plan, candidate, package_id) for plan in plans):
            return False
    if run_ids != {ref.identifier for ref in candidate.source_run_refs}:
        return False
    declared_evidence = {ref.identifier for ref in candidate.evidence_refs}
    return bool(used_evidence) and used_evidence == declared_evidence


def _plan_contains_package(
    plan: dict[str, object], candidate: KnowledgeCandidate, package_id: str
) -> bool:
    packages = plan.get("work_packages")
    goal_ref = candidate.source_goal_ref
    if not isinstance(packages, list) or goal_ref is None:
        return False
    return plan.get("goal_ref") == goal_ref.model_dump(mode="json") and any(
        isinstance(work_package, dict) and work_package.get("identifier") == package_id
        for work_package in packages
    )
