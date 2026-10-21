"""The Estimation Engine — the single constitutional owner of quantitative execution assessment.

Given immutable :class:`~nexus_estimation.model.EstimationInputs` it produces a deterministic,
explainable :class:`~nexus_estimation.model.EstimationReport` bundling the five estimates
(complexity, duration, cost, confidence, resource). It is a **pure function of (signals, model
version)** — no randomness, no clock in the scoring, no reasoning, no LLM, no runtime/skill/
intent decision. It **estimates only**; Engineering Intelligence (later) *consumes* these
estimates and owns the engineering decision (INV-02).

Each estimation records one durable ``estimation.estimated`` fact (the report embedded in the
payload) and persists the report through the reused P1 repository, so replay reconstructs every
estimate identically after restart (ADR-001/ADR-007/INV-17).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from nexus_core.domain.event import Event
from nexus_core.domain.work_package import WorkPackage
from nexus_core.events.interfaces import EventEmitter
from nexus_estimation import ids
from nexus_estimation.baseline import DEFAULT_MODEL, EstimationModel
from nexus_estimation.confidence import score_confidence
from nexus_estimation.events import ESTIMATION_ESTIMATED, build_event, system_now
from nexus_estimation.model import (
    ComplexityEstimate,
    ConfidenceEstimate,
    CostEstimate,
    DurationEstimate,
    EstimationInputs,
    EstimationReport,
    ResourceEstimate,
)
from nexus_estimation.observability import EstimationObservability
from nexus_estimation.persistence import EstimationRepositories
from nexus_estimation.rules import (
    estimate_cost,
    estimate_duration,
    estimate_resource,
    score_complexity,
)
from nexus_estimation.signals import merge_signals, signals_from_work_package
from nexus_estimation.vocabulary import ComplexityBand, ConfidenceBand, EstimateKind


class EstimationEngine:
    """Deterministic, explainable, replayable estimation over immutable facts."""

    def __init__(
        self,
        model: EstimationModel = DEFAULT_MODEL,
        *,
        emitter: EventEmitter | None = None,
        repositories: EstimationRepositories | None = None,
        observability: EstimationObservability | None = None,
        now: Callable[[], str] | None = None,
    ) -> None:
        self._model = model
        self._emitter = emitter
        self._repos = repositories
        self._obs = observability or EstimationObservability()
        self._now = now or system_now

    @property
    def model_version(self) -> str:
        """The version of the estimation model this engine uses (a versioned input)."""
        return self._model.version

    def estimate(self, inputs: EstimationInputs, *, persist: bool = True) -> EstimationReport:
        """Produce the immutable estimation report for ``inputs`` (pure; identical in → identical out)."""
        signals = dict(inputs.signals)
        model, subject = self._model, inputs.subject_identifier

        confidence_value, confidence_band, c_factors, c_trace = score_confidence(signals, model)
        complexity_score, complexity_band, x_factors, x_trace = score_complexity(signals, model)
        duration_seconds, d_factors, d_trace = estimate_duration(complexity_score, model)
        cost_amount, currency, k_factors, k_trace = estimate_cost(duration_seconds, signals, model)
        resource_class, profile, r_factors, r_trace = estimate_resource(
            complexity_score, complexity_band, signals, model
        )

        def _est_id(kind: EstimateKind) -> str:
            return ids.estimate_id(subject, kind, model.version, signals)

        complexity = ComplexityEstimate(
            identity=_est_id(ComplexityEstimate.KIND),
            subject_identifier=subject,
            confidence=confidence_value,
            factors=x_factors,
            reasoning_trace=x_trace,
            model_version=model.version,
            score=complexity_score,
            band=complexity_band,
        )
        duration = DurationEstimate(
            identity=_est_id(DurationEstimate.KIND),
            subject_identifier=subject,
            confidence=confidence_value,
            factors=d_factors,
            reasoning_trace=d_trace,
            model_version=model.version,
            seconds=duration_seconds,
        )
        cost = CostEstimate(
            identity=_est_id(CostEstimate.KIND),
            subject_identifier=subject,
            confidence=confidence_value,
            factors=k_factors,
            reasoning_trace=k_trace,
            model_version=model.version,
            amount=cost_amount,
            currency=currency,
        )
        confidence = ConfidenceEstimate(
            identity=_est_id(ConfidenceEstimate.KIND),
            subject_identifier=subject,
            confidence=confidence_value,
            factors=c_factors,
            reasoning_trace=c_trace,
            model_version=model.version,
            value=confidence_value,
            band=confidence_band,
        )
        resource = ResourceEstimate(
            identity=_est_id(ResourceEstimate.KIND),
            subject_identifier=subject,
            confidence=confidence_value,
            factors=r_factors,
            reasoning_trace=r_trace,
            model_version=model.version,
            resource_class=resource_class,
            profile=profile,
        )

        report = EstimationReport(
            identity=ids.report_id(subject, model.version, signals),
            subject_identifier=subject,
            correlation_identifier=inputs.correlation_identifier,
            model_version=model.version,
            complexity=complexity,
            duration=duration,
            cost=cost,
            confidence=confidence,
            resource=resource,
            timestamp=self._now(),
        )

        if persist:
            self._record(report, complexity_band, confidence_band)
        return report

    def estimate_work_package(
        self,
        work_package: WorkPackage,
        correlation_identifier: str,
        *,
        extra_signals: Mapping[str, float] | None = None,
        persist: bool = True,
    ) -> EstimationReport:
        """Estimate directly from an immutable Work Package (+ optional extra factual signals)."""
        signals = merge_signals(signals_from_work_package(work_package), extra_signals or {})
        inputs = EstimationInputs(work_package.identifier, correlation_identifier, signals)
        return self.estimate(inputs, persist=persist)

    # -- persistence + events ----------------------------------------------- #

    def _record(
        self,
        report: EstimationReport,
        complexity_band: ComplexityBand,
        confidence_band: ConfidenceBand,
    ) -> None:
        self._obs.estimated(complexity_band, confidence_band)
        if self._repos is not None:
            self._repos.reports.add(report)
        if self._emitter is not None:
            self._emitter.emit(self._estimated_event(report))

    def _estimated_event(self, report: EstimationReport) -> Event:
        payload = {
            "subject": report.subject_identifier,
            "model_version": report.model_version,
            "report": report.model_dump(mode="json"),
        }
        return build_event(
            ids.estimated_event_id(report.correlation_identifier, payload),
            ESTIMATION_ESTIMATED,
            report.correlation_identifier,
            payload,
            self._now(),
        )
