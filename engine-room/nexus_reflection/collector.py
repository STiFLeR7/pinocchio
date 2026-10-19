"""Reflection collection — correlating completed operational history (read-only).

Milestone 1. The :class:`ReflectionCollector` joins the three per-execution outputs into
:class:`~nexus_reflection.episode.OperationalEpisode` records keyed by session, and bundles
them with the raw runtime events and operational metrics into an immutable
:class:`OperationalHistory`. It **never modifies the collected data** (doc 26 *Evidence
First*): it reads the Execution Results, Validation Reports, and Recovery Plans and produces a
read-only projection that references them by id (INV-12).

Correlation is by execution **session** (``ExecutionResult.session_ref`` /
``ValidationReport.session_ref`` / ``RecoveryPlan.session_ref`` share the identity). Sessions
are ordered by first appearance across the inputs, so the history — and therefore every
downstream analysis — is deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nexus_core.contracts.base import Reference, Struct
from nexus_core.domain.event import Event
from nexus_execution.results import ExecutionResult
from nexus_recovery.plan import RecoveryPlan
from nexus_reflection.episode import OperationalEpisode
from nexus_reflection.vocabulary import EXECUTION_RESULT_TARGET_TYPE
from nexus_validation.report import ValidationReport
from nexus_validation.vocabulary import ValidationDecision


@dataclass(frozen=True, slots=True)
class OperationalHistory:
    """The immutable, correlated window of completed operations Reflection analyses."""

    scope: str
    correlation_identifier: str
    episodes: tuple[OperationalEpisode, ...]
    events: tuple[Event, ...] = ()
    metrics: Struct = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """Whether there is any completed operation to reflect on."""
        return not self.episodes


class ReflectionCollector:
    """Correlates execution/validation/recovery outputs into an immutable history."""

    def collect(
        self,
        scope: str,
        *,
        execution_results: tuple[ExecutionResult, ...] = (),
        validation_reports: tuple[ValidationReport, ...] = (),
        recovery_plans: tuple[RecoveryPlan, ...] = (),
        events: tuple[Event, ...] = (),
        metrics: Struct | None = None,
    ) -> OperationalHistory:
        """Join the per-execution outputs into a deterministic, read-only history."""
        results = {r.session_ref.identifier: r for r in execution_results}
        reports = {r.session_ref.identifier: r for r in validation_reports}
        plans = {p.session_ref.identifier: p for p in recovery_plans}

        ordered: list[str] = []
        for source in (execution_results, validation_reports, recovery_plans):
            for item in source:
                session = item.session_ref.identifier
                if session not in ordered:
                    ordered.append(session)

        episodes = tuple(
            self._episode(session, results.get(session), reports.get(session), plans.get(session))
            for session in ordered
        )
        correlation = self._correlation(episodes)
        return OperationalHistory(
            scope=scope,
            correlation_identifier=correlation,
            episodes=episodes,
            events=events,
            metrics=dict(metrics) if metrics else {},
        )

    def _episode(
        self,
        session: str,
        result: ExecutionResult | None,
        report: ValidationReport | None,
        plan: RecoveryPlan | None,
    ) -> OperationalEpisode:
        return OperationalEpisode(
            session=session,
            correlation_identifier=self._episode_correlation(report, plan, result),
            runtime=self._runtime(result, report, plan),
            validation_decision=report.decision if report else None,
            recovery_decision=plan.decision if plan else None,
            failure_category=plan.failure_category if plan else None,
            succeeded=bool(report and report.decision is ValidationDecision.PASSED),
            retry_eligible=bool(plan and plan.retry_eligible),
            attempts_used=plan.attempts_used if plan else 0,
            exit_status=result.exit_status if result else None,
            error_class=result.error_class if result else None,
            metrics=dict(result.metrics) if result else {},
            execution_result_ref=(
                Reference(target_type=EXECUTION_RESULT_TARGET_TYPE, identifier=session)
                if result
                else None
            ),
            validation_report_ref=report.reference() if report else None,
            recovery_plan_ref=plan.reference() if plan else None,
            evidence_refs=report.evidence_refs if report else (),
        )

    def _runtime(
        self,
        result: ExecutionResult | None,
        report: ValidationReport | None,
        plan: RecoveryPlan | None,
    ) -> str | None:
        for ref in (
            result.runtime_ref if result else None,
            report.runtime_ref if report else None,
            plan.runtime_ref if plan else None,
        ):
            if ref is not None:
                return ref.identifier
        return None

    def _episode_correlation(
        self,
        report: ValidationReport | None,
        plan: RecoveryPlan | None,
        result: ExecutionResult | None,
    ) -> str:
        for candidate in (
            report.correlation_identifier if report else "",
            plan.correlation_identifier if plan else "",
        ):
            if candidate:
                return candidate
        return result.session_ref.identifier if result else ""

    def _correlation(self, episodes: tuple[OperationalEpisode, ...]) -> str:
        for episode in episodes:
            if episode.correlation_identifier:
                return episode.correlation_identifier
        return ""
