"""Recovery rules — deterministic, policy-driven, explainable (no AI, no heuristics).

Milestone 2. Each rule is a pure function of the :class:`RecoveryContext` (the Validation
Report, the classified failure, the policy, the attempt count, and any checkpoint). A rule
either *applies* and proposes exactly one :class:`~nexus_recovery.vocabulary.RecoveryDecision`
with a rationale and required actions, or reports ``NOT_APPLICABLE``. Rules never execute,
retry, restore, plan, or invoke an LLM — they read facts and explain a proposed decision. The
:class:`~nexus_recovery.evaluator.RecoveryEvaluator` applies a fixed precedence over the rule
outputs to select the final decision.

The rule set covers the program's decision scope (Complete / Retry / Resume / Escalate /
Await Approval / Abort). Doc-19's richer strategies (Rollback / Switch Runtime / Request
Context) and Replan are reserved for a later program and are intentionally not proposed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from nexus_core.contracts.base import Reference
from nexus_recovery.classification import FailureSignal
from nexus_recovery.plan import RecoveryRuleResult
from nexus_recovery.policy import RecoveryPolicy
from nexus_recovery.vocabulary import RecoveryDecision, RecoveryRuleOutcome
from nexus_validation.report import ValidationReport
from nexus_validation.vocabulary import ValidationDecision


@dataclass(frozen=True, slots=True)
class RecoveryContext:
    """Everything a recovery rule may read — the verdict, the failure, policy, and history."""

    report: ValidationReport
    failure: FailureSignal
    policy: RecoveryPolicy
    attempt: int = 1
    checkpoint_ref: Reference | None = None

    @property
    def attempts_remaining(self) -> int:
        """Retry budget left under the policy (never negative)."""
        return max(0, self.policy.retry.max_attempts - self.attempt)

    @property
    def has_checkpoint(self) -> bool:
        """Whether a valid checkpoint is available to resume from."""
        return self.checkpoint_ref is not None


def _applies(rule_id: str, decision: RecoveryDecision, rationale: str) -> RecoveryRuleResult:
    """An applicable rule proposing a decision (keyword-forwarding for the frozen VO)."""
    return RecoveryRuleResult(
        rule_id=rule_id,
        outcome=RecoveryRuleOutcome.APPLICABLE,
        proposed_decision=decision,
        rationale=rationale,
    )


def _skip(rule_id: str, rationale: str) -> RecoveryRuleResult:
    """A non-applicable rule (proposes nothing)."""
    return RecoveryRuleResult(
        rule_id=rule_id,
        outcome=RecoveryRuleOutcome.NOT_APPLICABLE,
        proposed_decision=None,
        rationale=rationale,
    )


@runtime_checkable
class RecoveryRule(Protocol):
    """A deterministic rule that proposes a governed recovery decision, or abstains."""

    rule_id: str

    def evaluate(self, context: RecoveryContext) -> RecoveryRuleResult:
        """Return the immutable outcome + proposed decision for this rule."""
        ...


class CompletionRule:
    """A Passed validation needs no recovery — the work is complete (INV-21/INV-22)."""

    rule_id = "recovery_completion"

    def evaluate(self, context: RecoveryContext) -> RecoveryRuleResult:
        if context.report.decision is ValidationDecision.PASSED:
            return _applies(
                self.rule_id, RecoveryDecision.COMPLETE, "validation passed — work complete"
            )
        return _skip(self.rule_id, "validation did not pass")


class ApprovalRule:
    """Inconclusive verdicts and governance failures pause for human approval (INV-22)."""

    rule_id = "recovery_approval"

    def evaluate(self, context: RecoveryContext) -> RecoveryRuleResult:
        if context.report.decision is ValidationDecision.REQUIRES_REVIEW:
            return _applies(
                self.rule_id,
                RecoveryDecision.AWAIT_APPROVAL,
                "validation inconclusive — human review required",
            )
        if context.policy.requires_approval(context.failure.category):
            return _applies(
                self.rule_id,
                RecoveryDecision.AWAIT_APPROVAL,
                f"{context.failure.category.value} failure requires approval — governance is never bypassed",
            )
        return _skip(self.rule_id, "no approval gate applies")


class AbortRule:
    """A failure the policy marks fatal for its category cannot be recovered."""

    rule_id = "recovery_abort"

    def evaluate(self, context: RecoveryContext) -> RecoveryRuleResult:
        category = context.failure.category
        if context.failure.is_failure and context.policy.aborts_on(category):
            return _applies(
                self.rule_id,
                RecoveryDecision.ABORT,
                f"policy marks {category.value} failure non-recoverable",
            )
        return _skip(self.rule_id, "failure is recoverable under policy")


class ResumeRule:
    """Partial progress with a valid checkpoint resumes rather than repeats work (doc 19)."""

    rule_id = "recovery_resume"

    def evaluate(self, context: RecoveryContext) -> RecoveryRuleResult:
        if (
            context.report.decision is ValidationDecision.PARTIAL
            and context.policy.allow_resume
            and context.has_checkpoint
        ):
            return _applies(
                self.rule_id,
                RecoveryDecision.RESUME,
                "partial progress preserved — resume from the latest valid checkpoint",
            )
        return _skip(self.rule_id, "no resumable partial progress with a checkpoint")


class RetryRule:
    """A retryable failure with budget remaining retries under the policy (bounded)."""

    rule_id = "recovery_retry"

    def evaluate(self, context: RecoveryContext) -> RecoveryRuleResult:
        category = context.failure.category
        if (
            context.failure.is_failure
            and context.policy.is_retryable(category)
            and context.attempts_remaining > 0
        ):
            return _applies(
                self.rule_id,
                RecoveryDecision.RETRY,
                f"{category.value} failure is retryable — {context.attempts_remaining} attempt(s) remaining",
            )
        return _skip(self.rule_id, "failure is not retryable or retry budget is exhausted")


class EscalationRule:
    """The floor: any unresolved failure escalates to a human — never silently dropped."""

    rule_id = "recovery_escalation"

    def evaluate(self, context: RecoveryContext) -> RecoveryRuleResult:
        if context.failure.is_failure:
            return _applies(
                self.rule_id,
                RecoveryDecision.ESCALATE,
                f"escalate {context.failure.category.value} failure to {context.policy.escalation_target}",
            )
        return _skip(self.rule_id, "no failure to escalate")


DEFAULT_RULES: tuple[RecoveryRule, ...] = (
    CompletionRule(),
    ApprovalRule(),
    AbortRule(),
    ResumeRule(),
    RetryRule(),
    EscalationRule(),
)

# Fixed precedence over proposed decisions (highest wins). Progress preservation (Resume)
# outranks a full Retry (doc 19 *Progress Preservation*); governance (Approval) is never
# bypassed; a Passed run Completes outright; Escalate is the safe floor.
DECISION_PRECEDENCE: tuple[RecoveryDecision, ...] = (
    RecoveryDecision.COMPLETE,
    RecoveryDecision.AWAIT_APPROVAL,
    RecoveryDecision.ABORT,
    RecoveryDecision.RESUME,
    RecoveryDecision.RETRY,
    RecoveryDecision.ESCALATE,
)
