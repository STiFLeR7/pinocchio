"""Unit tests for the deterministic recovery rules (each applies or abstains)."""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_recovery import (
    AbortRule,
    ApprovalRule,
    CompletionRule,
    EscalationRule,
    FailureCategory,
    FailureSignal,
    RecoveryContext,
    RecoveryDecision,
    RecoveryPolicy,
    RecoveryRuleOutcome,
    ResumeRule,
    RetryPolicy,
    RetryRule,
)
from nexus_recovery.vocabulary import RetryPolicyKind
from nexus_validation.vocabulary import ValidationDecision
from tests.unit.nexus_recovery.helpers import checkpoint_ref, report


def _signal(category: FailureCategory) -> FailureSignal:
    if category is FailureCategory.NONE:
        return FailureSignal(FailureCategory.NONE, None, "no failure")
    return FailureSignal(category, "owner", "a failure")


def _context(  # type: ignore[no-untyped-def]
    *,
    decision: ValidationDecision,
    category: FailureCategory,
    policy: RecoveryPolicy | None = None,
    attempt: int = 1,
    checkpoint: Reference | None = None,
) -> RecoveryContext:
    return RecoveryContext(
        report=report(decision=decision),
        failure=_signal(category),
        policy=policy or RecoveryPolicy(),
        attempt=attempt,
        checkpoint_ref=checkpoint,
    )


# --- context helpers -------------------------------------------------------- #


def test_attempts_remaining_never_negative() -> None:
    ctx = _context(
        decision=ValidationDecision.FAILED,
        category=FailureCategory.RUNTIME,
        policy=RecoveryPolicy(retry=RetryPolicy(max_attempts=2)),
        attempt=5,
    )
    assert ctx.attempts_remaining == 0
    assert ctx.has_checkpoint is False


# --- completion ------------------------------------------------------------- #


def test_completion_rule_applies_on_passed() -> None:
    result = CompletionRule().evaluate(
        _context(decision=ValidationDecision.PASSED, category=FailureCategory.NONE)
    )
    assert result.outcome is RecoveryRuleOutcome.APPLICABLE
    assert result.proposed_decision is RecoveryDecision.COMPLETE


def test_completion_rule_skips_when_not_passed() -> None:
    result = CompletionRule().evaluate(
        _context(decision=ValidationDecision.FAILED, category=FailureCategory.RUNTIME)
    )
    assert result.outcome is RecoveryRuleOutcome.NOT_APPLICABLE
    assert result.proposed_decision is None


# --- approval --------------------------------------------------------------- #


def test_approval_rule_applies_on_requires_review() -> None:
    result = ApprovalRule().evaluate(
        _context(decision=ValidationDecision.REQUIRES_REVIEW, category=FailureCategory.VALIDATION)
    )
    assert result.proposed_decision is RecoveryDecision.AWAIT_APPROVAL


def test_approval_rule_applies_on_governance_failure() -> None:
    result = ApprovalRule().evaluate(
        _context(decision=ValidationDecision.FAILED, category=FailureCategory.GOVERNANCE)
    )
    assert result.proposed_decision is RecoveryDecision.AWAIT_APPROVAL


def test_approval_rule_skips_otherwise() -> None:
    result = ApprovalRule().evaluate(
        _context(decision=ValidationDecision.FAILED, category=FailureCategory.RUNTIME)
    )
    assert result.outcome is RecoveryRuleOutcome.NOT_APPLICABLE


# --- abort ------------------------------------------------------------------ #


def test_abort_rule_applies_when_policy_marks_category_fatal() -> None:
    policy = RecoveryPolicy(abort_on=(FailureCategory.DEPENDENCY,))
    result = AbortRule().evaluate(
        _context(
            decision=ValidationDecision.FAILED, category=FailureCategory.DEPENDENCY, policy=policy
        )
    )
    assert result.proposed_decision is RecoveryDecision.ABORT


def test_abort_rule_skips_when_recoverable() -> None:
    result = AbortRule().evaluate(
        _context(decision=ValidationDecision.FAILED, category=FailureCategory.RUNTIME)
    )
    assert result.outcome is RecoveryRuleOutcome.NOT_APPLICABLE


# --- resume ----------------------------------------------------------------- #


def test_resume_rule_applies_on_partial_with_checkpoint() -> None:
    result = ResumeRule().evaluate(
        _context(
            decision=ValidationDecision.PARTIAL,
            category=FailureCategory.VALIDATION,
            checkpoint=checkpoint_ref(),
        )
    )
    assert result.proposed_decision is RecoveryDecision.RESUME


def test_resume_rule_skips_without_checkpoint() -> None:
    result = ResumeRule().evaluate(
        _context(decision=ValidationDecision.PARTIAL, category=FailureCategory.VALIDATION)
    )
    assert result.outcome is RecoveryRuleOutcome.NOT_APPLICABLE


def test_resume_rule_skips_when_resume_disallowed() -> None:
    result = ResumeRule().evaluate(
        _context(
            decision=ValidationDecision.PARTIAL,
            category=FailureCategory.VALIDATION,
            policy=RecoveryPolicy(allow_resume=False),
            checkpoint=checkpoint_ref(),
        )
    )
    assert result.outcome is RecoveryRuleOutcome.NOT_APPLICABLE


# --- retry ------------------------------------------------------------------ #


def test_retry_rule_applies_on_retryable_with_budget() -> None:
    result = RetryRule().evaluate(
        _context(decision=ValidationDecision.FAILED, category=FailureCategory.RUNTIME, attempt=1)
    )
    assert result.proposed_decision is RecoveryDecision.RETRY


def test_retry_rule_skips_when_budget_exhausted() -> None:
    result = RetryRule().evaluate(
        _context(
            decision=ValidationDecision.FAILED,
            category=FailureCategory.RUNTIME,
            policy=RecoveryPolicy(retry=RetryPolicy(max_attempts=2)),
            attempt=2,
        )
    )
    assert result.outcome is RecoveryRuleOutcome.NOT_APPLICABLE


def test_retry_rule_skips_when_retries_disabled() -> None:
    result = RetryRule().evaluate(
        _context(
            decision=ValidationDecision.FAILED,
            category=FailureCategory.RUNTIME,
            policy=RecoveryPolicy(retry=RetryPolicy(kind=RetryPolicyKind.NEVER)),
        )
    )
    assert result.outcome is RecoveryRuleOutcome.NOT_APPLICABLE


def test_retry_rule_skips_for_non_retryable_category() -> None:
    result = RetryRule().evaluate(
        _context(decision=ValidationDecision.FAILED, category=FailureCategory.CONTEXT)
    )
    assert result.outcome is RecoveryRuleOutcome.NOT_APPLICABLE


# --- escalation ------------------------------------------------------------- #


def test_escalation_rule_applies_on_any_failure() -> None:
    result = EscalationRule().evaluate(
        _context(decision=ValidationDecision.FAILED, category=FailureCategory.DEPENDENCY)
    )
    assert result.proposed_decision is RecoveryDecision.ESCALATE


def test_escalation_rule_skips_when_no_failure() -> None:
    result = EscalationRule().evaluate(
        _context(decision=ValidationDecision.PASSED, category=FailureCategory.NONE)
    )
    assert result.outcome is RecoveryRuleOutcome.NOT_APPLICABLE
