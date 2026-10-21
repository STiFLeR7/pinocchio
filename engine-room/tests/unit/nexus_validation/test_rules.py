"""Unit tests for the deterministic validation rules."""

from __future__ import annotations

from nexus_execution.signals import TerminalOutcome
from nexus_validation import (
    ArtifactCorroborationRule,
    CompletionCriteriaRule,
    ErrorAbsenceRule,
    ExitStatusRule,
    ProcessOutcomeRule,
    RuleContext,
    ValidationPolicy,
    ValidationRule,
)
from nexus_validation.collector import EvidenceCollector
from nexus_validation.vocabulary import EvidenceSource, RuleOutcome
from tests.unit.nexus_validation.helpers import (
    artifact_events,
    execution_result,
    val_work_package,
)


def _context(
    *,
    result=None,  # type: ignore[no-untyped-def]
    work_package=None,  # type: ignore[no-untyped-def]
    artifacts=("wp-val-main.py",),
    policy: ValidationPolicy | None = None,
) -> RuleContext:
    result = result or execution_result()
    events = artifact_events(artifacts)
    evidence = EvidenceCollector().collect(result, events)
    return RuleContext(
        result=result,
        work_package=work_package or val_work_package(),
        evidence=evidence,
        policy=policy or ValidationPolicy(),
    )


# --- ProcessOutcomeRule ----------------------------------------------------- #


def test_process_outcome_completed_satisfied() -> None:
    r = ProcessOutcomeRule().evaluate(_context())
    assert r.outcome is RuleOutcome.SATISFIED


def test_process_outcome_failed_violated() -> None:
    r = ProcessOutcomeRule().evaluate(
        _context(result=execution_result(outcome=TerminalOutcome.FAILED))
    )
    assert r.outcome is RuleOutcome.VIOLATED


def test_process_outcome_cancelled_insufficient() -> None:
    r = ProcessOutcomeRule().evaluate(
        _context(result=execution_result(outcome=TerminalOutcome.CANCELLED))
    )
    assert r.outcome is RuleOutcome.INSUFFICIENT_EVIDENCE


# --- ExitStatusRule --------------------------------------------------------- #


def test_exit_status_zero_satisfied() -> None:
    assert ExitStatusRule().evaluate(_context()).outcome is RuleOutcome.SATISFIED


def test_exit_status_none_satisfied() -> None:
    r = ExitStatusRule().evaluate(_context(result=execution_result(exit_status=None)))
    assert r.outcome is RuleOutcome.SATISFIED


def test_exit_status_nonzero_violated() -> None:
    r = ExitStatusRule().evaluate(_context(result=execution_result(exit_status=1)))
    assert r.outcome is RuleOutcome.VIOLATED


# --- ErrorAbsenceRule ------------------------------------------------------- #


def test_error_absence_satisfied() -> None:
    assert ErrorAbsenceRule().evaluate(_context()).outcome is RuleOutcome.SATISFIED


def test_error_present_violated() -> None:
    r = ErrorAbsenceRule().evaluate(
        _context(result=execution_result(error_class="provider-failure"))
    )
    assert r.outcome is RuleOutcome.VIOLATED
    assert "provider-failure" in r.rationale


# --- ArtifactCorroborationRule ---------------------------------------------- #


def test_corroboration_satisfied_with_artifacts() -> None:
    assert ArtifactCorroborationRule().evaluate(_context()).outcome is RuleOutcome.SATISFIED


def test_corroboration_insufficient_without_artifacts() -> None:
    r = ArtifactCorroborationRule().evaluate(_context(artifacts=()))
    assert r.outcome is RuleOutcome.INSUFFICIENT_EVIDENCE


def test_corroboration_not_applicable_when_policy_disables() -> None:
    r = ArtifactCorroborationRule().evaluate(
        _context(artifacts=(), policy=ValidationPolicy(require_artifact_corroboration=False))
    )
    assert r.outcome is RuleOutcome.NOT_APPLICABLE


# --- CompletionCriteriaRule ------------------------------------------------- #


def test_criteria_not_applicable_when_empty() -> None:
    assert CompletionCriteriaRule().evaluate(_context()).outcome is RuleOutcome.NOT_APPLICABLE


def test_criteria_required_artifacts_present_satisfied() -> None:
    ctx = _context(
        work_package=val_work_package(completion_criteria={"required_artifacts": ["main.py"]}),
        artifacts=("wp-val-main.py",),
    )
    assert CompletionCriteriaRule().evaluate(ctx).outcome is RuleOutcome.SATISFIED


def test_criteria_required_artifacts_missing_violated() -> None:
    ctx = _context(
        work_package=val_work_package(completion_criteria={"required_artifacts": ["report.pdf"]}),
        artifacts=("wp-val-main.py",),
    )
    assert CompletionCriteriaRule().evaluate(ctx).outcome is RuleOutcome.VIOLATED


def test_criteria_min_artifacts_met_satisfied() -> None:
    ctx = _context(
        work_package=val_work_package(completion_criteria={"min_artifacts": 2}),
        artifacts=("a", "b"),
    )
    assert CompletionCriteriaRule().evaluate(ctx).outcome is RuleOutcome.SATISFIED


def test_criteria_min_artifacts_unmet_violated() -> None:
    ctx = _context(
        work_package=val_work_package(completion_criteria={"min_artifacts": 3}),
        artifacts=("a",),
    )
    assert CompletionCriteriaRule().evaluate(ctx).outcome is RuleOutcome.VIOLATED


def test_criteria_unrecognized_shape_insufficient() -> None:
    ctx = _context(work_package=val_work_package(completion_criteria={"quality": "high"}))
    assert CompletionCriteriaRule().evaluate(ctx).outcome is RuleOutcome.INSUFFICIENT_EVIDENCE


# --- protocol + context helpers --------------------------------------------- #


def test_rules_satisfy_protocol() -> None:
    for rule in (ProcessOutcomeRule(), ExitStatusRule(), CompletionCriteriaRule()):
        assert isinstance(rule, ValidationRule)


def test_context_of_source_filters() -> None:
    ctx = _context()
    assert all(e.source is EvidenceSource.ARTIFACT for e in ctx.of_source(EvidenceSource.ARTIFACT))
