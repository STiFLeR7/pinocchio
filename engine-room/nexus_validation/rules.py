"""Validation rules — deterministic, evidence-driven, explainable (no AI, no heuristics).

Milestone 2. Each rule is a pure function of the collected Evidence and the Work Package's
completion criteria; it returns a :class:`RuleResult` with a canonical
:class:`~nexus_validation.vocabulary.RuleOutcome` and a human-readable rationale (INV-31).
No rule trusts the runtime's self-report alone (INV-20): the ``ArtifactCorroborationRule``
exists precisely to demand an *independent* artifact before a clean process outcome can pass.

Rules never execute, retry, or reason with an LLM. They read facts and explain a verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from nexus_core.contracts.base import Reference
from nexus_core.domain.event import Event
from nexus_core.domain.work_package import WorkPackage
from nexus_execution.results import ExecutionResult
from nexus_execution.signals import TerminalOutcome
from nexus_validation.evidence import Evidence
from nexus_validation.report import RuleResult
from nexus_validation.vocabulary import EvidenceSource, RuleOutcome


def _result(
    rule_id: str,
    outcome: RuleOutcome,
    rationale: str,
    evidence_refs: tuple[Reference, ...] = (),
) -> RuleResult:
    """Keyword-forwarding constructor for the frozen :class:`RuleResult` value object."""
    return RuleResult(
        rule_id=rule_id, outcome=outcome, rationale=rationale, evidence_refs=evidence_refs
    )


@dataclass(frozen=True, slots=True)
class ValidationPolicy:
    """The declarative policy a validation runs under (doc 14 *Policy Aware*)."""

    require_artifact_corroboration: bool = True
    required_evidence_sources: tuple[EvidenceSource, ...] = ()
    require_explicit_conditions: bool = False
    action_artifact_directory: str | None = None


@dataclass(frozen=True, slots=True)
class RuleContext:
    """Everything a rule may read — evidence + execution facts + the objective + policy."""

    result: ExecutionResult
    work_package: WorkPackage
    evidence: tuple[Evidence, ...]
    policy: ValidationPolicy = field(default_factory=ValidationPolicy)
    events: tuple[Event, ...] = ()
    precomputed_outcome_condition: RuleResult | None = None

    def of_source(self, source: EvidenceSource) -> tuple[Evidence, ...]:
        """Evidence collected from a given source (deterministic order)."""
        return tuple(e for e in self.evidence if e.source is source)


@runtime_checkable
class ValidationRule(Protocol):
    """A deterministic rule that judges the Evidence and explains its verdict."""

    rule_id: str

    def evaluate(self, context: RuleContext) -> RuleResult:
        """Return the immutable outcome + rationale for this rule."""
        ...


class ProcessOutcomeRule:
    """The runtime process must have ended normally (necessary, never sufficient — INV-20)."""

    rule_id = "process_outcome"

    def evaluate(self, context: RuleContext) -> RuleResult:
        metadata = context.of_source(EvidenceSource.RUNTIME_METADATA)
        refs = tuple(e.reference() for e in metadata)
        outcome = context.result.outcome
        if outcome is TerminalOutcome.COMPLETED:
            return _result(self.rule_id, RuleOutcome.SATISFIED, "process ended normally", refs)
        if outcome is TerminalOutcome.FAILED:
            return _result(self.rule_id, RuleOutcome.VIOLATED, "process ended in failure", refs)
        return _result(
            self.rule_id,
            RuleOutcome.INSUFFICIENT_EVIDENCE,
            "process was cancelled — completion is undetermined",
            refs,
        )


class ExitStatusRule:
    """A non-zero exit status is a violation; ``0`` or absent is satisfied."""

    rule_id = "exit_status"

    def evaluate(self, context: RuleContext) -> RuleResult:
        refs = tuple(e.reference() for e in context.of_source(EvidenceSource.RUNTIME_METADATA))
        exit_status = context.result.exit_status
        if exit_status in (0, None):
            return _result(self.rule_id, RuleOutcome.SATISFIED, f"exit status {exit_status}", refs)
        return _result(
            self.rule_id, RuleOutcome.VIOLATED, f"non-zero exit status {exit_status}", refs
        )


class ErrorAbsenceRule:
    """A typed execution error is a violation; its absence is satisfied."""

    rule_id = "error_absence"

    def evaluate(self, context: RuleContext) -> RuleResult:
        refs = tuple(e.reference() for e in context.of_source(EvidenceSource.RUNTIME_METADATA))
        error_class = context.result.error_class
        if error_class is None:
            return _result(self.rule_id, RuleOutcome.SATISFIED, "no execution error", refs)
        return _result(self.rule_id, RuleOutcome.VIOLATED, f"execution error: {error_class}", refs)


class ArtifactCorroborationRule:
    """At least one independent artifact must corroborate a clean run (the INV-20 rule)."""

    rule_id = "artifact_corroboration"

    def evaluate(self, context: RuleContext) -> RuleResult:
        artifacts = context.of_source(EvidenceSource.ARTIFACT)
        refs = tuple(e.reference() for e in artifacts)
        if not context.policy.require_artifact_corroboration:
            return _result(
                self.rule_id,
                RuleOutcome.NOT_APPLICABLE,
                "artifact corroboration not required",
                refs,
            )
        if artifacts:
            return _result(
                self.rule_id,
                RuleOutcome.SATISFIED,
                f"{len(artifacts)} independent artifact(s) corroborate the outcome",
                refs,
            )
        return _result(
            self.rule_id,
            RuleOutcome.INSUFFICIENT_EVIDENCE,
            "no independent artifact corroborates the runtime's self-report (INV-20)",
            refs,
        )


class CompletionCriteriaRule:
    """Evaluate the Work Package's explicit completion criteria, when present."""

    rule_id = "completion_criteria"

    def evaluate(self, context: RuleContext) -> RuleResult:
        criteria = context.work_package.completion_criteria
        if "outcome_conditions" in criteria:
            return _result(
                self.rule_id,
                RuleOutcome.NOT_APPLICABLE,
                "finite outcome conditions are evaluated independently",
            )
        if not criteria:
            return _result(
                self.rule_id, RuleOutcome.NOT_APPLICABLE, "no explicit completion criteria", ()
            )
        artifacts = context.of_source(EvidenceSource.ARTIFACT)
        artifact_ids = {str(e.observed.get("artifact", "")) for e in artifacts}
        refs = tuple(e.reference() for e in artifacts)

        required = criteria.get("required_artifacts")
        min_artifacts = criteria.get("min_artifacts")

        if isinstance(required, (list, tuple)):
            missing = [name for name in required if not any(name in aid for aid in artifact_ids)]
            if missing:
                return _result(
                    self.rule_id,
                    RuleOutcome.VIOLATED,
                    f"required artifacts missing: {', '.join(map(str, missing))}",
                    refs,
                )
            return _result(
                self.rule_id, RuleOutcome.SATISFIED, "all required artifacts present", refs
            )
        if isinstance(min_artifacts, int):
            if len(artifacts) >= min_artifacts:
                return _result(
                    self.rule_id,
                    RuleOutcome.SATISFIED,
                    f"{len(artifacts)} artifact(s) ≥ required {min_artifacts}",
                    refs,
                )
            return _result(
                self.rule_id,
                RuleOutcome.VIOLATED,
                f"{len(artifacts)} artifact(s) < required {min_artifacts}",
                refs,
            )
        # Criteria present but in an unrecognized shape — cannot decide deterministically.
        return _result(
            self.rule_id,
            RuleOutcome.INSUFFICIENT_EVIDENCE,
            "completion criteria present but not deterministically evaluable",
            refs,
        )


class OutcomeConditionsRule:
    """Assess the finite file/JUnit acceptance conditions independently of runtime claims."""

    rule_id = "outcome_conditions"

    def evaluate(self, context: RuleContext) -> RuleResult:
        if context.precomputed_outcome_condition is not None:
            return context.precomputed_outcome_condition
        from nexus_validation.outcome_evidence import OutcomeConditionEvaluator

        result, _evidence = OutcomeConditionEvaluator().evaluate(context)
        return result


DEFAULT_RULES: tuple[ValidationRule, ...] = (
    ProcessOutcomeRule(),
    ExitStatusRule(),
    ErrorAbsenceRule(),
    CompletionCriteriaRule(),
    OutcomeConditionsRule(),
    ArtifactCorroborationRule(),
)
