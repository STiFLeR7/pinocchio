"""Validation Report — the immutable, evidence-referencing verdict of one validation.

Milestone 3. A :class:`ValidationReport` is the Validation Engine's output value object
(the same pattern as the Runtime Session / Execution Result: a layer output, not a frozen
core contract). It records the doc-14 report contents — decision, confidence, satisfied and
failed requirements, recommendations, timestamp, validator — plus a reasoning trace and the
evaluated rule results, and it **references Evidence by id, never duplicating artifacts**
(INV-12, ADR-003). Every field is a deterministic function of the evidence and the rules, so
identical evidence produces a byte-identical report (doc 14 *Deterministic*, INV-31
explainability).
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, Struct, ValueObject
from nexus_validation.vocabulary import (
    VALIDATION_REPORT_TARGET_TYPE,
    RuleOutcome,
    ValidationDecision,
    ValidationStage,
)


class RuleResult(ValueObject):
    """The immutable outcome of one deterministic rule, with its rationale and evidence."""

    rule_id: str
    outcome: RuleOutcome
    rationale: str
    evidence_refs: tuple[Reference, ...] = ()


class ValidationReport(ValueObject):
    """The immutable, evidence-referencing verdict for one execution attempt."""

    identity: str
    decision: ValidationDecision
    stage: ValidationStage
    confidence: float
    session_ref: Reference
    work_package_ref: Reference
    execution_result_ref: Reference
    runtime_ref: Reference | None = None
    correlation_identifier: str = ""
    evidence_refs: tuple[Reference, ...] = ()
    rule_results: tuple[RuleResult, ...] = ()
    satisfied_requirements: tuple[str, ...] = ()
    failed_requirements: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    recommendations: tuple[str, ...] = ()
    reasoning_trace: tuple[str, ...] = ()
    observations: tuple[Struct, ...] = ()
    validator: str = "nexus_validation"
    timestamp: str = ""

    def reference(self) -> Reference:
        """A typed by-id pointer to this report."""
        return Reference(target_type=VALIDATION_REPORT_TARGET_TYPE, identifier=self.identity)

    @property
    def passed(self) -> bool:
        """Whether the verdict is Passed (a *validated* outcome, INV-20 — not a self-report)."""
        return self.decision is ValidationDecision.PASSED
