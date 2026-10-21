"""Unit tests for the DecisionEvaluator — the deterministic verdict aggregation."""

from __future__ import annotations

from nexus_validation import DecisionEvaluator, RuleResult
from nexus_validation.vocabulary import RuleOutcome, ValidationDecision


def _r(rule_id: str, outcome: RuleOutcome) -> RuleResult:
    return RuleResult(rule_id=rule_id, outcome=outcome, rationale=f"{rule_id}:{outcome.value}")


_CLEAN = (
    _r("process_outcome", RuleOutcome.SATISFIED),
    _r("exit_status", RuleOutcome.SATISFIED),
    _r("error_absence", RuleOutcome.SATISFIED),
    _r("completion_criteria", RuleOutcome.NOT_APPLICABLE),
    _r("artifact_corroboration", RuleOutcome.SATISFIED),
)


def test_all_satisfied_is_passed() -> None:
    d = DecisionEvaluator().evaluate(_CLEAN)
    assert d.decision is ValidationDecision.PASSED
    assert d.confidence == 1.0
    assert d.recommendations == ()


def test_hard_violation_is_failed() -> None:
    results = (_r("process_outcome", RuleOutcome.VIOLATED), *_CLEAN[1:])
    d = DecisionEvaluator().evaluate(results)
    assert d.decision is ValidationDecision.FAILED
    assert "process_outcome" in d.failed_requirements
    assert d.recommendations  # non-empty


def test_exit_status_violation_is_failed() -> None:
    results = (_CLEAN[0], _r("exit_status", RuleOutcome.VIOLATED), *_CLEAN[2:])
    assert DecisionEvaluator().evaluate(results).decision is ValidationDecision.FAILED


def test_cancelled_process_is_requires_review() -> None:
    results = (_r("process_outcome", RuleOutcome.INSUFFICIENT_EVIDENCE), *_CLEAN[1:])
    d = DecisionEvaluator().evaluate(results)
    assert d.decision is ValidationDecision.REQUIRES_REVIEW
    assert d.missing_evidence


def test_criteria_violation_is_partial() -> None:
    results = (
        *_CLEAN[:3],
        _r("completion_criteria", RuleOutcome.VIOLATED),
        _CLEAN[4],
    )
    assert DecisionEvaluator().evaluate(results).decision is ValidationDecision.PARTIAL


def test_criteria_insufficient_is_requires_review() -> None:
    results = (
        *_CLEAN[:3],
        _r("completion_criteria", RuleOutcome.INSUFFICIENT_EVIDENCE),
        _CLEAN[4],
    )
    assert DecisionEvaluator().evaluate(results).decision is ValidationDecision.REQUIRES_REVIEW


def test_missing_corroboration_is_partial() -> None:
    # Clean process but no independent artifact → Partial (INV-20 policy).
    results = (*_CLEAN[:4], _r("artifact_corroboration", RuleOutcome.INSUFFICIENT_EVIDENCE))
    assert DecisionEvaluator().evaluate(results).decision is ValidationDecision.PARTIAL


def test_confidence_is_fraction_of_applicable_satisfied() -> None:
    results = (
        _r("process_outcome", RuleOutcome.SATISFIED),
        _r("exit_status", RuleOutcome.VIOLATED),
        _r("completion_criteria", RuleOutcome.NOT_APPLICABLE),
    )
    # 1 of 2 applicable satisfied → 0.5
    assert DecisionEvaluator().evaluate(results).confidence == 0.5


def test_confidence_zero_when_no_applicable_rules() -> None:
    results = (_r("completion_criteria", RuleOutcome.NOT_APPLICABLE),)
    assert DecisionEvaluator().evaluate(results).confidence == 0.0


def test_reasoning_trace_covers_every_rule() -> None:
    d = DecisionEvaluator().evaluate(_CLEAN)
    assert len(d.reasoning_trace) == len(_CLEAN)


def test_partial_and_review_recommendations_present() -> None:
    partial = DecisionEvaluator().evaluate(
        (*_CLEAN[:4], _r("artifact_corroboration", RuleOutcome.INSUFFICIENT_EVIDENCE))
    )
    review = DecisionEvaluator().evaluate(
        (_r("process_outcome", RuleOutcome.INSUFFICIENT_EVIDENCE), *_CLEAN[1:])
    )
    assert partial.recommendations
    assert review.recommendations
