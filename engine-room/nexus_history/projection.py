"""Projection — reconstruct one immutable ExecutionHistoryProfile from the authoritative log.

This is the deterministic heart of Execution History: given the whole event log and a scoping
:class:`HistoryQuery`, it selects the in-scope operational events (:mod:`retrieval`) and folds them —
in the log's own global order — into the facts-only facets of an
:class:`~nexus_history.model.ExecutionHistoryProfile`. It **retrieves and counts only**: no
reasoning, no AI, no scoring, no recommendation (the Grounding rule). Identical events → identical
facets → identical identity, which is what makes replay and restart reconstruct an identical view.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from nexus_core.domain.event import Event
from nexus_history.lineage import build_lineage
from nexus_history.model import (
    ArtifactHistory,
    EventFrequency,
    EvidenceHistory,
    ExecutionEpisode,
    ExecutionHistoryProfile,
    GoalHistory,
    HistoryQuery,
    OperatorHistory,
    RecoveryHistory,
    ReflectionHistory,
    RepositoryExecutionHistory,
    RuntimeHistory,
    ValidationHistory,
    WorkPackageHistory,
)
from nexus_history.retrieval import filter_events, first
from nexus_history.timeline import build_timeline


class _Episode:
    """Mutable per-correlation accumulator (collapsed to a frozen ExecutionEpisode at the end)."""

    __slots__ = ("completions", "failures", "recovered", "reflected", "starts", "validated")

    def __init__(self) -> None:
        self.starts = self.completions = self.failures = 0
        self.validated = self.recovered = self.reflected = False


def project(
    events: Iterable[Event], query: HistoryQuery, projector_version: str
) -> ExecutionHistoryProfile:
    """Fold the in-scope operational log into one facts-only profile draft (identity filled later)."""
    scoped = filter_events(events, query)

    by_type: Counter[str] = Counter()
    by_producer: Counter[str] = Counter()
    episodes: dict[str, _Episode] = {}

    registered = selections = starts = completions = failures = timeouts = cancellations = 0
    runtimes: set[str] = set()
    v_started = v_completed = 0
    verdicts: list[tuple[str, str]] = []
    r_started = r_decisions = 0
    r_outcomes: list[tuple[str, str]] = []
    rf_started = rf_reports = 0
    rf_correlations: list[str] = []
    artifact_refs: list[tuple[str, str]] = []
    evidence_refs: list[tuple[str, str]] = []
    work_packages: list[str] = []
    operators: Counter[str] = Counter()
    repositories: Counter[str] = Counter()
    goal_refs: set[str] = set()

    def episode(correlation: str) -> _Episode:
        return episodes.setdefault(correlation, _Episode())

    for e in scoped:
        payload = e.payload or {}
        by_type[e.type] += 1
        by_producer[e.producer] += 1
        cor = e.correlation_identifier
        suffix = e.type.split(".", 1)[1] if "." in e.type else e.type

        if e.type.startswith("runtime."):
            runtime_ref = first(payload, "runtime", "runtime_ref", "chosen", "provider")
            if runtime_ref is not None:
                runtimes.add(str(runtime_ref))
            if suffix == "registered":
                registered += 1
            elif suffix == "started":
                starts += 1
                episode(cor).starts += 1
            elif suffix == "completed":
                completions += 1
                episode(cor).completions += 1
            elif suffix == "failed":
                failures += 1
                episode(cor).failures += 1
            elif suffix == "timed_out":
                timeouts += 1
            elif suffix == "cancelled":
                cancellations += 1
            elif suffix in ("allocated", "candidates_resolved"):
                selections += 1
            elif suffix == "artifact_emitted":
                ref = first(payload, "artifact", "runtime_ref", "allocation_ref") or e.identifier
                artifact_refs.append((cor, str(ref)))

        elif e.type == "orchestration.runtime_request_created":
            selections += 1

        elif e.type.startswith("validation."):
            if suffix == "started":
                v_started += 1
            elif suffix == "completed":
                v_completed += 1
                episode(cor).validated = True
                verdict = first(payload, "outcome", "decision", "verdict", "final_state")
                verdicts.append((cor, str(verdict) if verdict is not None else "unknown"))
            elif suffix == "evidence_collected":
                ref = first(payload, "artifact", "sources", "count") or e.identifier
                evidence_refs.append((cor, str(ref)))

        elif e.type.startswith("recovery."):
            if suffix == "started":
                r_started += 1
            elif suffix == "decision_created":
                r_decisions += 1
                episode(cor).recovered = True
                outcome = first(payload, "decision", "outcome", "proposed")
                r_outcomes.append((cor, str(outcome) if outcome is not None else "unknown"))

        elif e.type.startswith("reflection."):
            if suffix == "started":
                rf_started += 1
            elif suffix == "report_created":
                rf_reports += 1
                episode(cor).reflected = True
                rf_correlations.append(cor)

        if e.type in (
            "work_package.created",
            "orchestration.work_package_ready",
            "harness.execution_package_created",
        ):
            wp = first(payload, "work_package", "package") or e.identifier
            work_packages.append(str(wp))

        if "artifact" in payload and not e.type.startswith("runtime."):
            artifact_refs.append((cor, str(payload["artifact"])))

        operator = first(payload, "operator", "user")
        if operator is not None:
            operators[str(operator)] += 1

        repo = first(payload, "root", "repository_root")
        if repo is not None:
            repositories[str(repo)] += 1

        goal = first(payload, "goal", "goal_identifier", "subject", "subject_identifier")
        if goal is not None:
            goal_refs.add(str(goal))

    timeline, truncated = build_timeline(scoped)
    ordered_episodes = tuple(
        ExecutionEpisode(
            correlation_identifier=cor,
            runtime_starts=acc.starts,
            runtime_completions=acc.completions,
            runtime_failures=acc.failures,
            validated=acc.validated,
            recovered=acc.recovered,
            reflected=acc.reflected,
        )
        for cor, acc in sorted(episodes.items())
    )
    goals = tuple(sorted(goal_refs)) or tuple(ep.correlation_identifier for ep in ordered_episodes)

    return ExecutionHistoryProfile(
        identity="",
        projector_version=projector_version,
        scope=query.scope(),
        available=bool(scoped),
        event_count=len(scoped),
        execution_count=len(ordered_episodes),
        timeline_truncated=truncated,
        frequency=EventFrequency(
            total=len(scoped),
            by_type=tuple(sorted(by_type.items())),
            by_producer=tuple(sorted(by_producer.items())),
        ),
        timeline=timeline,
        executions=ordered_episodes,
        runtime=RuntimeHistory(
            registered=registered,
            selections=selections,
            starts=starts,
            completions=completions,
            failures=failures,
            timeouts=timeouts,
            cancellations=cancellations,
            runtimes=tuple(sorted(runtimes)),
        ),
        validation=ValidationHistory(
            started=v_started, completed=v_completed, verdicts=tuple(verdicts)
        ),
        recovery=RecoveryHistory(
            started=r_started, decisions=r_decisions, outcomes=tuple(r_outcomes)
        ),
        reflection=ReflectionHistory(
            started=rf_started, reports=rf_reports, correlations=tuple(rf_correlations)
        ),
        knowledge_lineage=build_lineage(scoped),
        artifacts=ArtifactHistory(count=len(artifact_refs), references=tuple(artifact_refs)),
        evidence=EvidenceHistory(count=len(evidence_refs), references=tuple(evidence_refs)),
        work_packages=WorkPackageHistory(
            created=len(work_packages), identifiers=tuple(work_packages)
        ),
        goals=GoalHistory(goals=goals, count=len(goals)),
        operators=OperatorHistory(by_operator=tuple(sorted(operators.items()))),
        repositories=RepositoryExecutionHistory(
            by_repository=tuple(sorted(repositories.items())),
            scoped_root=query.repository_root,
        ),
    )
