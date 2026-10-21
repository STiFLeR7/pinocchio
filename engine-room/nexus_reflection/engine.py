"""The Reflection Engine — deterministically explains completed operational history.

Milestones 1-5. Given a window of completed operations — Execution Results, Validation Reports,
Recovery Plans, runtime events, and operational metrics — the engine:

1. **collects** them into an immutable, correlated :class:`OperationalHistory` (Milestone 1),
   emitting ``reflection.started``;
2. runs deterministic **analyzers** (Milestone 2) and emits ``reflection.analysis_completed``;
3. **synthesises** summaries, confidence, confirmed observations, and Knowledge *Candidates*
   and builds an immutable **Reflection Report** (Milestone 3) that *references* the reflected
   operations, never duplicating them (INV-12), emitting ``reflection.report_created``;
4. emits ``reflection.completed`` (history reflected) or ``reflection.failed`` (no operational
   history) (Milestone 4) and **persists** the Report + Patterns (Milestone 5).

It **explains** behaviour and nothing else (doc 26 boundaries): it never executes, retries,
plans, mutates policy, updates Knowledge (it produces *Candidates* only — INV-25), or invokes
AI. It is deterministic — identical history yields a byte-identical report and event stream.
"""

from __future__ import annotations

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event
from nexus_core.events.interfaces import EventEmitter
from nexus_execution.results import ExecutionResult
from nexus_recovery.plan import RecoveryPlan
from nexus_reflection import events as refevents
from nexus_reflection import ids
from nexus_reflection.analyzers import DEFAULT_ANALYZERS, AnalysisContext, OperationalAnalyzer
from nexus_reflection.collector import OperationalHistory, ReflectionCollector
from nexus_reflection.observability import ReflectionObservability
from nexus_reflection.patterns import OperationalPattern
from nexus_reflection.persistence import ReflectionRepositories
from nexus_reflection.report import ReflectionReport
from nexus_reflection.synthesis import ReflectionInsight, ReflectionSynthesizer
from nexus_reflection.vocabulary import ReflectionStage
from nexus_runtime.events import SystemTimestampSource, TimestampSource
from nexus_validation.report import ValidationReport


class ReflectionEngine:
    """Produces an immutable, deterministic Reflection Report from operational history."""

    def __init__(
        self,
        emitter: EventEmitter,
        *,
        repositories: ReflectionRepositories | None = None,
        observability: ReflectionObservability | None = None,
        timestamps: TimestampSource | None = None,
        analyzers: tuple[OperationalAnalyzer, ...] = DEFAULT_ANALYZERS,
    ) -> None:
        self._emitter = emitter
        self._repos = repositories
        self._obs = observability or ReflectionObservability()
        self._timestamps = timestamps or SystemTimestampSource()
        self._analyzers = analyzers
        self._collector = ReflectionCollector()
        self._synthesizer = ReflectionSynthesizer()

    def reflect(
        self,
        scope: str,
        *,
        execution_results: tuple[ExecutionResult, ...] = (),
        validation_reports: tuple[ValidationReport, ...] = (),
        recovery_plans: tuple[RecoveryPlan, ...] = (),
        events: tuple[Event, ...] = (),
        metrics: Struct | None = None,
    ) -> ReflectionReport:
        """Analyse one operational window; emit events, persist, and return the Report."""
        history = self._collector.collect(
            scope,
            execution_results=execution_results,
            validation_reports=validation_reports,
            recovery_plans=recovery_plans,
            events=events,
            metrics=metrics,
        )
        correlation = history.correlation_identifier or scope
        seq = 0

        seq = self._emit(
            scope,
            refevents.REFLECTION_STARTED,
            "started",
            seq,
            correlation,
            {"scope": scope, "episodes": len(history.episodes)},
        )
        self._obs.started()

        patterns = self._analyze(history)
        seq = self._emit(
            scope,
            refevents.REFLECTION_ANALYSIS_COMPLETED,
            "analysis",
            seq,
            correlation,
            {"patterns": len(patterns), "analyzers": len(self._analyzers)},
        )
        self._obs.analysis_completed(len(patterns))

        insight = self._synthesizer.synthesize(history, patterns)
        report = self._build_report(history, patterns, insight, correlation)
        seq = self._emit(
            scope,
            refevents.REFLECTION_REPORT_CREATED,
            "report",
            seq,
            correlation,
            {"report": report.identity, "candidates": len(report.knowledge_candidates)},
        )
        self._obs.report_created()

        if history.is_empty:
            self._emit(
                scope,
                refevents.REFLECTION_FAILED,
                "failed",
                seq,
                correlation,
                self._payload(report),
            )
            self._obs.failed()
        else:
            self._emit(
                scope,
                refevents.REFLECTION_COMPLETED,
                "completed",
                seq,
                correlation,
                self._payload(report),
            )
            self._obs.completed()

        self._persist(report, patterns)
        return report

    # -- analysis + report --------------------------------------------------- #

    def _analyze(self, history: OperationalHistory) -> tuple[OperationalPattern, ...]:
        context = AnalysisContext(history=history)
        collected: list[OperationalPattern] = []
        for analyzer in self._analyzers:
            collected.extend(analyzer.analyze(context))
        return tuple(collected)

    def _build_report(
        self,
        history: OperationalHistory,
        patterns: tuple[OperationalPattern, ...],
        insight: ReflectionInsight,
        correlation: str,
    ) -> ReflectionReport:
        stage = ReflectionStage.FAILED if history.is_empty else ReflectionStage.COMPLETED
        return ReflectionReport(
            identity=ids.report_id(history.scope),
            scope=history.scope,
            stage=stage,
            confidence=insight.confidence,
            correlation_identifier=correlation,
            episode_count=len(history.episodes),
            execution_summary=insight.execution_summary,
            validation_summary=insight.validation_summary,
            recovery_summary=insight.recovery_summary,
            patterns=patterns,
            confirmed_observations=insight.confirmed_observations,
            knowledge_candidates=insight.knowledge_candidates,
            recommendations=insight.recommendations,
            evidence_refs=insight.evidence_refs,
            reasoning_trace=insight.reasoning_trace,
            timestamp=self._timestamps.now(),
        )

    def _payload(self, report: ReflectionReport) -> Struct:
        return {
            "scope": report.scope,
            "episodes": report.episode_count,
            "patterns": len(report.patterns),
            "confidence": report.confidence.value,
            "candidates": len(report.knowledge_candidates),
        }

    # -- persistence + events ------------------------------------------------ #

    def _persist(self, report: ReflectionReport, patterns: tuple[OperationalPattern, ...]) -> None:
        if self._repos is None:
            return
        self._repos.reports.add(report)
        for pattern in patterns:
            self._repos.patterns.add(pattern)

    def _emit(
        self,
        scope: str,
        event_type: str,
        kind: str,
        seq: int,
        correlation: str,
        payload: Struct,
    ) -> int:
        identifier = ids.event_id(scope, kind, seq)
        self._emitter.emit(
            refevents.build_event(
                identifier, event_type, correlation, payload, self._timestamps.now()
            )
        )
        return seq + 1
