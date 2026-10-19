"""Recovery policy — the declarative bundle a recovery decision runs under (doc 19).

Recovery is **strategy driven** (doc 19): it never invents recovery behavior; it applies the
Recovery Policy the Execution Strategy would define. For this program the policy is expressed
as a small, immutable, deterministic bundle — a retry budget, the categories that are fatal
or that require human approval, whether checkpoint resume is permitted, and the escalation
target. The engine reads this bundle; it never mutates it and never derives behavior from
anywhere else.

Retries are **never indefinite** (doc 19): ``RetryPolicy`` carries an explicit
``max_attempts`` bound and a :class:`~nexus_recovery.vocabulary.RetryPolicyKind`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nexus_recovery.vocabulary import FailureCategory, RetryPolicyKind

# Categories a plain retry can plausibly clear (transient / re-runnable). Others need a
# different governed path (context request, approval, upstream recovery) — deferred here to
# Escalate, never a silent re-run.
RETRYABLE_CATEGORIES: tuple[FailureCategory, ...] = (
    FailureCategory.RUNTIME,
    FailureCategory.RESOURCE,
    FailureCategory.VALIDATION,
)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """How retries are governed — bounded, never indefinite (doc 19 *Retry Policy*)."""

    kind: RetryPolicyKind = RetryPolicyKind.FIXED
    max_attempts: int = 3

    @property
    def retries_enabled(self) -> bool:
        """Whether this policy permits any automated retry at all."""
        return self.kind is not RetryPolicyKind.NEVER and self.max_attempts > 1


@dataclass(frozen=True, slots=True)
class RecoveryPolicy:
    """The declarative policy a single recovery decision is evaluated under."""

    retry: RetryPolicy = field(default_factory=RetryPolicy)
    allow_resume: bool = True
    abort_on: tuple[FailureCategory, ...] = ()
    require_approval_on: tuple[FailureCategory, ...] = (FailureCategory.GOVERNANCE,)
    escalation_target: str = "operator"

    def is_retryable(self, category: FailureCategory) -> bool:
        """Whether a failure of this category may be retried under this policy."""
        return self.retry.retries_enabled and category in RETRYABLE_CATEGORIES

    def requires_approval(self, category: FailureCategory) -> bool:
        """Whether a failure of this category must pause for human approval."""
        return category in self.require_approval_on

    def aborts_on(self, category: FailureCategory) -> bool:
        """Whether a failure of this category is fatal under this policy."""
        return category in self.abort_on


DEFAULT_RECOVERY_POLICY = RecoveryPolicy()
