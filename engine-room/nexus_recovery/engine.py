"""The Recovery Engine — decides the governed continuation for a validated outcome.

Milestones 1-5. Given a :class:`~nexus_validation.report.ValidationReport`, the
:class:`~nexus_execution.results.ExecutionResult` it judged, a Recovery Policy, and the attempt
history, the engine:

1. emits ``recovery.started`` and **classifies** the failure (Milestone 1, doc 19);
2. evaluates each deterministic **rule** (Milestone 2), emitting ``recovery.rule_evaluated``;
3. **aggregates** one governed decision by fixed precedence and builds an immutable
   **Recovery Plan** (Milestone 3) that *references* the report/result/evidence/checkpoint,
   never duplicating them (INV-12);
4. emits ``recovery.decision_created`` then ``recovery.completed`` (a governed continuation was
   determined) or ``recovery.failed`` (Abort — no continuation exists) (Milestone 4) and
   **persists** the Plan (Milestone 5).

It **decides continuation** and nothing else (INV-21; doc 19 boundaries): it never executes,
retries, restores, fails over, plans, mutates the Validation Report, or invokes AI. It is
deterministic — an identical report against an identical policy yields a byte-identical plan
and event stream.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, Struct
from nexus_core.domain.event import Event
from nexus_core.events.interfaces import EventEmitter
from nexus_execution.results import ExecutionResult
from nexus_recovery import events as revents
from nexus_recovery import ids
from nexus_recovery.classification import FailureClassifier, FailureSignal
from nexus_recovery.evaluator import RecoveryDetermination, RecoveryEvaluator
from nexus_recovery.observability import RecoveryObservability
from nexus_recovery.persistence import RecoveryRepositories
from nexus_recovery.plan import RecoveryPlan, RecoveryRuleResult
from nexus_recovery.policy import DEFAULT_RECOVERY_POLICY, RecoveryPolicy
from nexus_recovery.rules import DEFAULT_RULES, RecoveryContext, RecoveryRule
from nexus_recovery.vocabulary import (
    EXECUTION_RESULT_TARGET_TYPE,
    RecoveryDecision,
    RecoveryStage,
)
from nexus_runtime.events import SystemTimestampSource, TimestampSource
from nexus_validation.report import ValidationReport

_STAGE_FOR_DECISION = {
    RecoveryDecision.COMPLETE: RecoveryStage.COMPLETE,
    RecoveryDecision.RETRY: RecoveryStage.RETRY,
    RecoveryDecision.RESUME: RecoveryStage.RESUME,
    RecoveryDecision.ESCALATE: RecoveryStage.ESCALATED,
    RecoveryDecision.AWAIT_APPROVAL: RecoveryStage.WAITING_APPROVAL,
    RecoveryDecision.ABORT: RecoveryStage.ABORTED,
}


class RecoveryEngine:
    """Produces an immutable, deterministic Recovery Plan from a Validation Report."""

    def __init__(
        self,
        emitter: EventEmitter,
        *,
        repositories: RecoveryRepositories | None = None,
        observability: RecoveryObservability | None = None,
        timestamps: TimestampSource | None = None,
        rules: tuple[RecoveryRule, ...] = DEFAULT_RULES,
    ) -> None:
        self._emitter = emitter
        self._repos = repositories
        self._obs = observability or RecoveryObservability()
        self._timestamps = timestamps or SystemTimestampSource()
        self._rules = rules
        self._classifier = FailureClassifier()
        self._evaluator = RecoveryEvaluator()

    def recover(
        self,
        report: ValidationReport,
        result: ExecutionResult,
        *,
        events: tuple[Event, ...] = (),
        policy: RecoveryPolicy | None = None,
        attempt: int = 1,
        checkpoint_ref: Reference | None = None,
    ) -> RecoveryPlan:
        """Decide the governed continuation for one validated outcome; emit, persist, return."""
        resolved_policy = policy or DEFAULT_RECOVERY_POLICY
        scope = report.session_ref.identifier
        correlation = self._correlation(report, events)
        seq = 0

        seq = self._emit(
            scope,
            revents.RECOVERY_STARTED,
            "started",
            seq,
            correlation,
            {"session": scope, "verdict": report.decision.value},
        )
        self._obs.started()

        failure = self._classifier.classify(report, result)
        context = RecoveryContext(
            report=report,
            failure=failure,
            policy=resolved_policy,
            attempt=attempt,
            checkpoint_ref=checkpoint_ref,
        )

        rule_results: list[RecoveryRuleResult] = []
        for rule in self._rules:
            rule_result = rule.evaluate(context)
            rule_results.append(rule_result)
            seq = self._emit(
                scope,
                revents.RECOVERY_RULE_EVALUATED,
                "rule",
                seq,
                correlation,
                {
                    "rule": rule_result.rule_id,
                    "outcome": rule_result.outcome.value,
                    "proposed": (
                        rule_result.proposed_decision.value
                        if rule_result.proposed_decision
                        else None
                    ),
                },
            )
            self._obs.rule_evaluated()

        determination = self._evaluator.evaluate(tuple(rule_results), context)
        plan = self._build_plan(
            scope, correlation, report, result, failure, context, tuple(rule_results), determination
        )

        seq = self._emit(
            scope,
            revents.RECOVERY_DECISION_CREATED,
            "decision",
            seq,
            correlation,
            {"decision": plan.decision.value, "deciding_rule": determination.deciding_rule},
        )
        self._obs.decision_created(plan.decision.value)

        if plan.decision is RecoveryDecision.ABORT:
            self._emit(
                scope, revents.RECOVERY_FAILED, "failed", seq, correlation, self._payload(plan)
            )
            self._obs.failed()
        else:
            self._emit(
                scope,
                revents.RECOVERY_COMPLETED,
                "completed",
                seq,
                correlation,
                self._payload(plan),
            )
            self._obs.completed()

        self._persist(plan)
        return plan

    # -- plan construction --------------------------------------------------- #

    def _build_plan(
        self,
        scope: str,
        correlation: str,
        report: ValidationReport,
        result: ExecutionResult,
        failure: FailureSignal,
        context: RecoveryContext,
        rule_results: tuple[RecoveryRuleResult, ...],
        determination: RecoveryDetermination,
    ) -> RecoveryPlan:
        decision = determination.decision
        return RecoveryPlan(
            identity=ids.plan_id(scope),
            decision=decision,
            stage=_STAGE_FOR_DECISION[decision],
            failure_category=failure.category,
            session_ref=report.session_ref,
            work_package_ref=report.work_package_ref,
            validation_report_ref=report.reference(),
            execution_result_ref=Reference(
                target_type=EXECUTION_RESULT_TARGET_TYPE, identifier=result.session_ref.identifier
            ),
            runtime_ref=result.runtime_ref,
            correlation_identifier=correlation,
            triggering_evidence_refs=report.evidence_refs,
            checkpoint_ref=context.checkpoint_ref if determination.resumable else None,
            escalation_target=self._escalation_target(decision, context),
            rule_results=rule_results,
            required_actions=determination.required_actions,
            recommendations=determination.recommendations,
            reasoning_trace=determination.reasoning_trace,
            retry_eligible=determination.retry_eligible,
            retry_policy=context.policy.retry.kind.value,
            attempts_used=context.attempt,
            attempts_remaining=context.attempts_remaining,
            resumable=determination.resumable,
            timestamp=self._timestamps.now(),
        )

    def _escalation_target(
        self, decision: RecoveryDecision, context: RecoveryContext
    ) -> str | None:
        if decision in (RecoveryDecision.ESCALATE, RecoveryDecision.AWAIT_APPROVAL):
            return context.policy.escalation_target
        return None

    def _payload(self, plan: RecoveryPlan) -> Struct:
        return {
            "decision": plan.decision.value,
            "failure_category": plan.failure_category.value,
            "retry_eligible": plan.retry_eligible,
            "resumable": plan.resumable,
            "attempts_remaining": plan.attempts_remaining,
        }

    # -- persistence + events ------------------------------------------------ #

    def _persist(self, plan: RecoveryPlan) -> None:
        if self._repos is None:
            return
        self._repos.plans.add(plan)

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
            revents.build_event(
                identifier, event_type, correlation, payload, self._timestamps.now()
            )
        )
        return seq + 1

    def _correlation(self, report: ValidationReport, events: tuple[Event, ...]) -> str:
        if report.correlation_identifier:
            return report.correlation_identifier
        prefix = f"evt-{report.session_ref.identifier}-"
        for event in events:
            if event.identifier.startswith(prefix):
                return event.correlation_identifier
        return report.session_ref.identifier
