"""Failure classification — deterministically naming *what failed* (doc 19).

Recovery's first responsibility is **failure classification** (doc 19 *Responsibilities*).
The classifier is a pure function of the Validation Report and the Execution Result: it maps
the typed execution error (doc-11 ``error_class`` / ``owner``) and the validation verdict onto
one of doc-19's :class:`~nexus_recovery.vocabulary.FailureCategory` values. It reads facts and
explains a category — it never executes, retries, or reasons with an LLM.

A ``PASSED`` verdict classifies as ``NONE`` (no failure to recover). Otherwise the *execution
error* is authoritative when present (a real runtime/resource/governance fault); a verdict
that is not Passed with *no* execution error is a ``VALIDATION`` failure (tests failed, review
rejected, artifact invalid, or evidence inconclusive).
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_execution.results import ExecutionResult
from nexus_recovery.vocabulary import FailureCategory
from nexus_validation.report import ValidationReport
from nexus_validation.vocabulary import ValidationDecision

# doc-11 error owners/classes → doc-19 failure categories (deterministic, total map).
_OWNER_CATEGORY = {
    "transport": FailureCategory.RESOURCE,
    "infrastructure": FailureCategory.RESOURCE,
    "provider": FailureCategory.RUNTIME,
    "runtime": FailureCategory.RUNTIME,
    "user": FailureCategory.GOVERNANCE,
}
_CLASS_CATEGORY = {
    "transport-failure": FailureCategory.RESOURCE,
    "infrastructure-failure": FailureCategory.RESOURCE,
    "timeout": FailureCategory.RUNTIME,
    "provider-failure": FailureCategory.RUNTIME,
    "execution-startup-failure": FailureCategory.RUNTIME,
    "teardown-failure": FailureCategory.RUNTIME,
    "user-cancellation": FailureCategory.GOVERNANCE,
}


@dataclass(frozen=True, slots=True)
class FailureSignal:
    """The classified failure — its category plus the traceable owner/detail (doc 19)."""

    category: FailureCategory
    owner: str | None
    detail: str

    @property
    def is_failure(self) -> bool:
        """Whether an actual failure was classified (``NONE`` means nothing to recover)."""
        return self.category is not FailureCategory.NONE


class FailureClassifier:
    """Deterministically classifies a validated outcome into a doc-19 failure category."""

    def classify(self, report: ValidationReport, result: ExecutionResult) -> FailureSignal:
        """Name what failed from the verdict + execution error (pure, explainable)."""
        if report.decision is ValidationDecision.PASSED:
            return FailureSignal(FailureCategory.NONE, None, "validation passed — no failure")

        if result.error_class is not None:
            category = _CLASS_CATEGORY.get(result.error_class) or _OWNER_CATEGORY.get(
                result.error_owner or "", FailureCategory.RUNTIME
            )
            detail = result.error_detail or result.error_class
            return FailureSignal(category, result.error_owner, f"execution error: {detail}")

        # Not Passed, no typed execution error ⇒ the *validation* judged it short.
        return FailureSignal(
            FailureCategory.VALIDATION,
            "validation",
            f"validation returned {report.decision.value}",
        )
