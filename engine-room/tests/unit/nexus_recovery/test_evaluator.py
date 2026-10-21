"""Unit tests for recovery decision aggregation (fixed precedence, explainable)."""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_recovery import (
    FailureCategory,
    FailureSignal,
    RecoveryContext,
    RecoveryDecision,
    RecoveryEvaluator,
    RecoveryPolicy,
    RetryPolicy,
)
from nexus_recovery.rules import DEFAULT_RULES
from nexus_validation.vocabulary import ValidationDecision
from tests.unit.nexus_recovery.helpers import checkpoint_ref, report


def _signal(category: FailureCategory) -> FailureSignal:
    if category is FailureCategory.NONE:
        return FailureSignal(FailureCategory.NONE, None, "no failure")
    return FailureSignal(category, "owner", "a failure")


def _determine(  # type: ignore[no-untyped-def]
    *,
    decision: ValidationDecision,
    category: FailureCategory,
    policy: RecoveryPolicy | None = None,
    attempt: int = 1,
    checkpoint: Reference | None = None,
):
    context = RecoveryContext(
        report=report(decision=decision),
        failure=_signal(category),
        policy=policy or RecoveryPolicy(),
        attempt=attempt,
        checkpoint_ref=checkpoint,
    )
    results = tuple(rule.evaluate(context) for rule in DEFAULT_RULES)
    return RecoveryEvaluator().evaluate(results, context)


def test_passed_completes_with_no_recommendations() -> None:
    d = _determine(decision=ValidationDecision.PASSED, category=FailureCategory.NONE)
    assert d.decision is RecoveryDecision.COMPLETE
    assert d.deciding_rule == "recovery_completion"
    assert d.recommendations == ()


def test_requires_review_awaits_approval() -> None:
    d = _determine(decision=ValidationDecision.REQUIRES_REVIEW, category=FailureCategory.VALIDATION)
    assert d.decision is RecoveryDecision.AWAIT_APPROVAL
    assert any("governance" in r for r in d.recommendations)


def test_policy_fatal_category_aborts() -> None:
    d = _determine(
        decision=ValidationDecision.FAILED,
        category=FailureCategory.DEPENDENCY,
        policy=RecoveryPolicy(abort_on=(FailureCategory.DEPENDENCY,)),
    )
    assert d.decision is RecoveryDecision.ABORT
    assert any("evidence is preserved" in r for r in d.recommendations)


def test_resume_outranks_retry() -> None:
    d = _determine(
        decision=ValidationDecision.PARTIAL,
        category=FailureCategory.VALIDATION,
        checkpoint=checkpoint_ref(),
    )
    assert d.decision is RecoveryDecision.RESUME
    assert d.resumable is True
    assert d.retry_eligible is True  # retry was also applicable, but resume has precedence
    assert any("do not repeat" in r for r in d.recommendations)


def test_retryable_failure_retries() -> None:
    d = _determine(decision=ValidationDecision.FAILED, category=FailureCategory.RUNTIME)
    assert d.decision is RecoveryDecision.RETRY
    assert d.retry_eligible is True
    assert any("retry under" in r for r in d.recommendations)


def test_exhausted_non_resumable_failure_escalates() -> None:
    d = _determine(
        decision=ValidationDecision.FAILED,
        category=FailureCategory.RUNTIME,
        policy=RecoveryPolicy(retry=RetryPolicy(max_attempts=2)),
        attempt=2,
    )
    assert d.decision is RecoveryDecision.ESCALATE
    assert d.retry_eligible is False
    assert any("escalate to operator" in r for r in d.recommendations)


def test_reasoning_trace_covers_every_rule() -> None:
    d = _determine(decision=ValidationDecision.FAILED, category=FailureCategory.RUNTIME)
    assert len(d.reasoning_trace) == len(DEFAULT_RULES)
    # applicable rules record their proposal; abstaining rules do not.
    assert any("-> retry" in line for line in d.reasoning_trace)
    assert any("not_applicable" in line for line in d.reasoning_trace)
