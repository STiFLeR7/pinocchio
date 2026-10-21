"""Recovery Plan — the immutable, reference-only output of one recovery decision.

Milestone 3. A :class:`RecoveryPlan` is the Recovery Engine's output value object (the same
pattern as the Runtime Session / Execution Result / Validation Report: a layer output, not a
frozen core contract). It records the governed decision, the classified failure, the
deterministic rule results and reasoning trace (INV-31 explainability), the retry/resume
eligibility the decision rests on, and the escalation and checkpoint references.

It **references existing objects by id and never duplicates them** (INV-12, ADR-003): the
triggering Validation Report, the Execution Result, the Evidence, and any checkpoint are all
carried as :class:`~nexus_core.contracts.base.Reference` values, never embedded. Every field
is a deterministic function of ``(validation_report, execution_result, policy, attempt,
checkpoint)`` and the injected timestamp, so identical inputs produce a byte-identical plan.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, ValueObject
from nexus_recovery.vocabulary import (
    RECOVERY_PLAN_TARGET_TYPE,
    FailureCategory,
    RecoveryDecision,
    RecoveryRuleOutcome,
    RecoveryStage,
)


class RecoveryRuleResult(ValueObject):
    """The immutable outcome of one deterministic recovery rule, with its rationale."""

    rule_id: str
    outcome: RecoveryRuleOutcome
    proposed_decision: RecoveryDecision | None
    rationale: str


class RecoveryPlan(ValueObject):
    """The immutable, reference-only recovery decision for one execution attempt."""

    identity: str
    decision: RecoveryDecision
    stage: RecoveryStage
    failure_category: FailureCategory
    session_ref: Reference
    work_package_ref: Reference
    validation_report_ref: Reference
    execution_result_ref: Reference | None = None
    runtime_ref: Reference | None = None
    correlation_identifier: str = ""
    triggering_evidence_refs: tuple[Reference, ...] = ()
    checkpoint_ref: Reference | None = None
    escalation_target: str | None = None
    rule_results: tuple[RecoveryRuleResult, ...] = ()
    required_actions: tuple[str, ...] = ()
    recommendations: tuple[str, ...] = ()
    reasoning_trace: tuple[str, ...] = ()
    retry_eligible: bool = False
    retry_policy: str = ""
    attempts_used: int = 0
    attempts_remaining: int = 0
    resumable: bool = False
    planner: str = "nexus_recovery"
    timestamp: str = ""

    def reference(self) -> Reference:
        """A typed by-id pointer to this plan."""
        return Reference(target_type=RECOVERY_PLAN_TARGET_TYPE, identifier=self.identity)

    @property
    def recovered(self) -> bool:
        """Whether recovery reached a terminal, no-further-action outcome (Complete)."""
        return self.decision is RecoveryDecision.COMPLETE

    @property
    def aborted(self) -> bool:
        """Whether recovery concluded the work cannot continue (Abort)."""
        return self.decision is RecoveryDecision.ABORT
