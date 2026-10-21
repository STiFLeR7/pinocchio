"""Decision evaluation — aggregating rule results into a deterministic verdict.

Milestone 2 (aggregation). A pure function of the :class:`RuleResult` list — no AI, no
randomness. The precedence encodes the INV-20 policy ratified for this program: a runtime
self-report alone never passes; a clean run must be corroborated by an independent artifact,
and a clean run *without* corroboration (and without explicit criteria) is **Partial**, not
Passed.

Confidence is a deterministic "evidence-corroboration strength": the fraction of *applicable*
rules that were satisfied. It is explainable (every rule contributes) and reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_validation.report import RuleResult
from nexus_validation.vocabulary import RuleOutcome, ValidationDecision

_HARD_RULES = ("process_outcome", "exit_status", "error_absence")


@dataclass(frozen=True, slots=True)
class Decision:
    """The aggregated verdict plus its explainable derivation."""

    decision: ValidationDecision
    confidence: float
    satisfied_requirements: tuple[str, ...]
    failed_requirements: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    recommendations: tuple[str, ...]
    reasoning_trace: tuple[str, ...]


class DecisionEvaluator:
    """Aggregates rule results into a deterministic, explainable :class:`Decision`."""

    def evaluate(self, rule_results: tuple[RuleResult, ...]) -> Decision:
        by_id = {r.rule_id: r for r in rule_results}
        satisfied = tuple(r.rule_id for r in rule_results if r.outcome is RuleOutcome.SATISFIED)
        failed = tuple(
            r.rule_id
            for r in rule_results
            if r.outcome in {RuleOutcome.VIOLATED, RuleOutcome.PARTIAL}
        )
        missing = tuple(
            r.rationale for r in rule_results if r.outcome is RuleOutcome.INSUFFICIENT_EVIDENCE
        )
        decision = self._decide(by_id)
        confidence = self._confidence(rule_results)
        trace = tuple(f"{r.rule_id}: {r.outcome.value} — {r.rationale}" for r in rule_results)
        return Decision(
            decision=decision,
            confidence=confidence,
            satisfied_requirements=satisfied,
            failed_requirements=failed,
            missing_evidence=missing,
            recommendations=self._recommendations(decision, by_id),
            reasoning_trace=trace,
        )

    def _decide(self, by_id: dict[str, RuleResult]) -> ValidationDecision:
        if any(rid in by_id and by_id[rid].outcome is RuleOutcome.VIOLATED for rid in _HARD_RULES):
            return ValidationDecision.FAILED
        process = by_id.get("process_outcome")
        if process is not None and process.outcome is RuleOutcome.INSUFFICIENT_EVIDENCE:
            return ValidationDecision.REQUIRES_REVIEW
        outcome_conditions = by_id.get("outcome_conditions")
        if outcome_conditions is not None:
            if outcome_conditions.outcome is RuleOutcome.INSUFFICIENT_EVIDENCE:
                return ValidationDecision.REQUIRES_REVIEW
            if outcome_conditions.outcome is RuleOutcome.VIOLATED:
                return ValidationDecision.FAILED
            if outcome_conditions.outcome is RuleOutcome.PARTIAL:
                return ValidationDecision.PARTIAL
        criteria = by_id.get("completion_criteria")
        if criteria is not None and criteria.outcome is RuleOutcome.VIOLATED:
            return ValidationDecision.PARTIAL
        if criteria is not None and criteria.outcome is RuleOutcome.INSUFFICIENT_EVIDENCE:
            return ValidationDecision.REQUIRES_REVIEW
        corroboration = by_id.get("artifact_corroboration")
        if corroboration is not None and corroboration.outcome is RuleOutcome.INSUFFICIENT_EVIDENCE:
            return ValidationDecision.PARTIAL
        return ValidationDecision.PASSED

    def _confidence(self, rule_results: tuple[RuleResult, ...]) -> float:
        applicable = [r for r in rule_results if r.outcome is not RuleOutcome.NOT_APPLICABLE]
        if not applicable:
            return 0.0
        satisfied = sum(1 for r in applicable if r.outcome is RuleOutcome.SATISFIED)
        return round(satisfied / len(applicable), 4)

    def _recommendations(
        self, decision: ValidationDecision, by_id: dict[str, RuleResult]
    ) -> tuple[str, ...]:
        if decision is ValidationDecision.PASSED:
            return ()
        if decision is ValidationDecision.FAILED:
            reasons = [
                by_id[r].rationale
                for r in _HARD_RULES
                if r in by_id and by_id[r].outcome is RuleOutcome.VIOLATED
            ]
            outcome_conditions = by_id.get("outcome_conditions")
            if (
                outcome_conditions is not None
                and outcome_conditions.outcome is RuleOutcome.VIOLATED
            ):
                reasons.append(outcome_conditions.rationale)
            return tuple(f"resolve failure: {reason}" for reason in reasons)
        if decision is ValidationDecision.PARTIAL:
            return (
                "supply the missing corroborating evidence or complete the required deliverables",
            )
        return ("route to human review — evidence is insufficient for a deterministic verdict",)
