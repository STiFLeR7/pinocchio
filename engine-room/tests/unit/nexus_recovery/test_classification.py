"""Unit tests for deterministic failure classification (doc 19 Failure Categories)."""

from __future__ import annotations

from nexus_execution.signals import TerminalOutcome
from nexus_recovery import FailureCategory, FailureClassifier
from nexus_validation.vocabulary import ValidationDecision
from tests.unit.nexus_recovery.helpers import execution_result, report


def _classify(*, decision, result):  # type: ignore[no-untyped-def]
    return FailureClassifier().classify(report(decision=decision), result)


def test_passed_verdict_classifies_as_none() -> None:
    signal = _classify(decision=ValidationDecision.PASSED, result=execution_result())
    assert signal.category is FailureCategory.NONE
    assert signal.is_failure is False


def test_provider_error_is_runtime_failure() -> None:
    signal = _classify(
        decision=ValidationDecision.FAILED,
        result=execution_result(
            outcome=TerminalOutcome.FAILED, error_class="provider-failure", error_owner="provider"
        ),
    )
    assert signal.category is FailureCategory.RUNTIME
    assert signal.owner == "provider"
    assert "provider-failure" in signal.detail or "detail" in signal.detail


def test_transport_error_is_resource_failure() -> None:
    signal = _classify(
        decision=ValidationDecision.FAILED,
        result=execution_result(
            outcome=TerminalOutcome.FAILED, error_class="transport-failure", error_owner="transport"
        ),
    )
    assert signal.category is FailureCategory.RESOURCE


def test_user_cancellation_is_governance_failure() -> None:
    signal = _classify(
        decision=ValidationDecision.REQUIRES_REVIEW,
        result=execution_result(
            outcome=TerminalOutcome.CANCELLED, error_class="user-cancellation", error_owner="user"
        ),
    )
    assert signal.category is FailureCategory.GOVERNANCE


def test_unknown_error_class_falls_back_to_owner() -> None:
    signal = _classify(
        decision=ValidationDecision.FAILED,
        result=execution_result(
            outcome=TerminalOutcome.FAILED, error_class="mystery-failure", error_owner="transport"
        ),
    )
    assert signal.category is FailureCategory.RESOURCE


def test_unknown_error_class_and_owner_defaults_to_runtime() -> None:
    signal = _classify(
        decision=ValidationDecision.FAILED,
        result=execution_result(
            outcome=TerminalOutcome.FAILED, error_class="mystery-failure", error_owner=None
        ),
    )
    assert signal.category is FailureCategory.RUNTIME


def test_not_passed_without_execution_error_is_validation_failure() -> None:
    signal = _classify(
        decision=ValidationDecision.FAILED,
        result=execution_result(),  # no typed execution error
    )
    assert signal.category is FailureCategory.VALIDATION
    assert signal.owner == "validation"
    assert signal.is_failure is True
