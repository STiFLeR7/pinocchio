"""The Validation Engine — judges an execution outcome from deterministic evidence.

Milestones 2-5. Given an :class:`~nexus_execution.results.ExecutionResult`, the Work Package
it was meant to satisfy, and the runtime event log, the engine:

1. collects immutable **Evidence** (Milestone 1) and emits ``validation.evidence_collected``;
2. evaluates each deterministic **rule** (Milestone 2), emitting ``validation.rule_evaluated``;
3. **aggregates** a verdict + confidence (INV-20 policy) and builds an immutable
   **Validation Report** (Milestone 3) that *references* Evidence, never duplicating it;
4. emits ``validation.completed`` (non-failed verdict) or ``validation.failed`` (Failed
   verdict) (Milestone 4) and **persists** the Report + Evidence (Milestone 5).

It **judges** outcomes and nothing else (doc 14 boundaries): it never executes, retries,
recovers, plans, mutates artifacts, or invokes AI. It is deterministic — identical evidence
against identical rules yields a byte-identical report and event stream.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, Struct
from nexus_core.domain.event import Event
from nexus_core.domain.work_package import WorkPackage
from nexus_core.events.interfaces import EventEmitter
from nexus_execution.results import ExecutionResult
from nexus_runtime.events import SystemTimestampSource, TimestampSource
from nexus_validation import events as vevents
from nexus_validation import ids
from nexus_validation.collector import EvidenceCollector
from nexus_validation.evaluator import Decision, DecisionEvaluator
from nexus_validation.evidence import Evidence
from nexus_validation.observability import ValidationObservability
from nexus_validation.outcome_evidence import OutcomeConditionEvaluator
from nexus_validation.persistence import ValidationRepositories
from nexus_validation.report import RuleResult, ValidationReport
from nexus_validation.rules import DEFAULT_RULES, RuleContext, ValidationPolicy, ValidationRule
from nexus_validation.vocabulary import (
    EXECUTION_RESULT_TARGET_TYPE,
    ValidationDecision,
    ValidationStage,
)

_STAGE_FOR_DECISION = {
    ValidationDecision.PASSED: ValidationStage.PASSED,
    ValidationDecision.FAILED: ValidationStage.FAILED,
    ValidationDecision.PARTIAL: ValidationStage.PARTIAL,
    ValidationDecision.REQUIRES_REVIEW: ValidationStage.REQUIRES_REVIEW,
}


class ValidationEngine:
    """Produces an immutable, deterministic Validation Report from an Execution Result."""

    def __init__(
        self,
        emitter: EventEmitter,
        *,
        repositories: ValidationRepositories | None = None,
        observability: ValidationObservability | None = None,
        timestamps: TimestampSource | None = None,
        rules: tuple[ValidationRule, ...] = DEFAULT_RULES,
    ) -> None:
        self._emitter = emitter
        self._repos = repositories
        self._obs = observability or ValidationObservability()
        self._timestamps = timestamps or SystemTimestampSource()
        self._rules = rules
        self._collector = EvidenceCollector()
        self._evaluator = DecisionEvaluator()
        self._condition_evaluator = OutcomeConditionEvaluator()

    def validate(
        self,
        result: ExecutionResult,
        work_package: WorkPackage,
        *,
        events: tuple[Event, ...] = (),
        policy: ValidationPolicy | None = None,
    ) -> ValidationReport:
        """Judge one execution outcome; emit events, persist, and return the Report."""
        event_log = events
        scope = result.session_ref.identifier
        correlation = self._correlation(result, event_log)
        emitted: list[str] = []
        seq = 0

        seq = self._emit(
            emitted,
            scope,
            vevents.VALIDATION_STARTED,
            "started",
            seq,
            correlation,
            {"session": scope, "work_package": work_package.identifier},
        )
        self._obs.started()

        evidence = self._collector.collect(result, event_log)
        base_context = RuleContext(
            result=result,
            work_package=work_package,
            evidence=evidence,
            policy=policy or ValidationPolicy(),
            events=event_log,
        )
        condition_result, condition_evidence = self._condition_evaluator.evaluate(base_context)
        evidence = (*evidence, *condition_evidence)
        seq = self._emit(
            emitted,
            scope,
            vevents.VALIDATION_EVIDENCE_COLLECTED,
            "evidence",
            seq,
            correlation,
            {
                "count": len(evidence),
                "sources": sorted({e.source.value for e in evidence}),
                "evidence": [item.model_dump(mode="json") for item in evidence],
            },
        )
        self._obs.evidence_collected(len(evidence))

        context = RuleContext(
            result=result,
            work_package=work_package,
            evidence=evidence,
            policy=policy or ValidationPolicy(),
            events=event_log,
            precomputed_outcome_condition=condition_result,
        )
        rule_results: list[RuleResult] = []
        for rule in self._rules:
            rule_result = rule.evaluate(context)
            rule_results.append(rule_result)
            seq = self._emit(
                emitted,
                scope,
                vevents.VALIDATION_RULE_EVALUATED,
                "rule",
                seq,
                correlation,
                {"rule": rule_result.rule_id, "outcome": rule_result.outcome.value},
            )
            self._obs.rule_evaluated()

        decision = self._evaluator.evaluate(tuple(rule_results))
        report = self._build_report(
            scope, correlation, result, work_package, evidence, tuple(rule_results), decision
        )

        if report.decision is ValidationDecision.FAILED:
            self._emit(
                emitted,
                scope,
                vevents.VALIDATION_FAILED,
                "failed",
                seq,
                correlation,
                self._terminal_payload(report),
            )
            self._obs.failed()
        else:
            self._emit(
                emitted,
                scope,
                vevents.VALIDATION_COMPLETED,
                "completed",
                seq,
                correlation,
                self._terminal_payload(report),
            )
            self._obs.completed()

        self._persist(report, evidence)
        return report

    # -- report construction ------------------------------------------------- #

    def _build_report(
        self,
        scope: str,
        correlation: str,
        result: ExecutionResult,
        work_package: WorkPackage,
        evidence: tuple[Evidence, ...],
        rule_results: tuple[RuleResult, ...],
        decision: Decision,
    ) -> ValidationReport:
        sources = sorted({e.source.value for e in evidence})
        observations: tuple[Struct, ...] = (
            {
                "evidence_by_source": {
                    s: sum(1 for e in evidence if e.source.value == s) for s in sources
                }
            },
        )
        return ValidationReport(
            identity=ids.report_id(scope),
            decision=decision.decision,
            stage=_STAGE_FOR_DECISION[decision.decision],
            confidence=decision.confidence,
            session_ref=result.session_ref,
            work_package_ref=result.work_package_ref,
            execution_result_ref=Reference(
                target_type=EXECUTION_RESULT_TARGET_TYPE, identifier=scope
            ),
            runtime_ref=result.runtime_ref,
            correlation_identifier=correlation,
            evidence_refs=tuple(e.reference() for e in evidence),
            rule_results=rule_results,
            satisfied_requirements=decision.satisfied_requirements,
            failed_requirements=decision.failed_requirements,
            missing_evidence=decision.missing_evidence,
            recommendations=decision.recommendations,
            reasoning_trace=decision.reasoning_trace,
            observations=observations,
            timestamp=self._timestamps.now(),
        )

    def _terminal_payload(self, report: ValidationReport) -> Struct:
        return {
            "decision": report.decision.value,
            "confidence": report.confidence,
            "satisfied": list(report.satisfied_requirements),
            "failed": list(report.failed_requirements),
            "report": report.model_dump(mode="json"),
        }

    def replay(
        self,
        events: tuple[Event, ...],
        result: ExecutionResult,
        work_package: WorkPackage | None = None,
    ) -> ValidationReport | None:
        """Rebuild an existing report from durable validation facts without collecting evidence."""
        result_id = result.session_ref.identifier
        terminal = next(
            (
                event
                for event in reversed(events)
                if event.type in {vevents.VALIDATION_COMPLETED, vevents.VALIDATION_FAILED}
                and isinstance(event.payload.get("report"), dict)
                and event.payload["report"].get("execution_result_ref", {}).get("identifier")
                == result_id
            ),
            None,
        )
        if terminal is None:
            return None
        report = ValidationReport.model_validate(terminal.payload["report"])
        if (
            work_package is not None
            and report.work_package_ref.identifier != work_package.identifier
        ):
            return None
        return report

    # -- persistence + events ------------------------------------------------ #

    def _persist(self, report: ValidationReport, evidence: tuple[Evidence, ...]) -> None:
        if self._repos is None:
            return
        self._repos.reports.add(report)
        for item in evidence:
            self._repos.evidence.add(item)

    def _emit(
        self,
        emitted: list[str],
        scope: str,
        event_type: str,
        kind: str,
        seq: int,
        correlation: str,
        payload: Struct,
    ) -> int:
        identifier = ids.event_id(scope, kind, seq)
        self._emitter.emit(
            vevents.build_event(
                identifier, event_type, correlation, payload, self._timestamps.now()
            )
        )
        emitted.append(identifier)
        return seq + 1

    def _correlation(self, result: ExecutionResult, event_log: tuple[Event, ...]) -> str:
        prefix = f"evt-{result.session_ref.identifier}-"
        for event in event_log:
            if event.identifier.startswith(prefix):
                return event.correlation_identifier
        return result.session_ref.identifier
