"""Unit tests for the immutable :class:`ExecutionStrategy` domain model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Correlation
from nexus_core.contracts.enums import (
    ApprovalTaxonomy,
    CoordinationModel,
    RecoveryBehavior,
    RetryBehavior,
)
from nexus_core.contracts.status import ExecutionStrategyStatus
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_core.state.transitions import MACHINES


def _build_execution_strategy() -> ExecutionStrategy:
    return ExecutionStrategy(
        identity="es-1",
        coordination=CoordinationModel.SEQUENTIAL,
        runtime_policy={"requires": ["code_execution"]},
        approval_policy=ApprovalTaxonomy.HUMAN_REVIEW,
        retry_policy=RetryBehavior.EXPONENTIAL_RETRY,
        timeout_policy={"max_execution_seconds": 600},
        validation_policy={"validators": ["evidence_present"]},
        recovery_policy={"default": "pause"},
        checkpoint_policy={"frequency": "per_milestone"},
        status=ExecutionStrategyStatus.ACTIVE,
        recovery_options=(RecoveryBehavior.PAUSE, RecoveryBehavior.RETRY),
        correlation=Correlation(correlation_identifier="c1"),
        version="1",
    )


def test_construction() -> None:
    es = _build_execution_strategy()
    assert es.identity == "es-1"
    assert es.coordination is CoordinationModel.SEQUENTIAL
    assert es.approval_policy is ApprovalTaxonomy.HUMAN_REVIEW
    assert es.retry_policy is RetryBehavior.EXPONENTIAL_RETRY
    assert es.runtime_policy == {"requires": ["code_execution"]}
    assert es.recovery_options == (RecoveryBehavior.PAUSE, RecoveryBehavior.RETRY)
    assert es.status is ExecutionStrategyStatus.ACTIVE


def test_immutable() -> None:
    es = _build_execution_strategy()
    with pytest.raises(ValidationError):
        es.coordination = CoordinationModel.PARALLEL  # type: ignore[misc]


def test_missing_required_raises() -> None:
    with pytest.raises(ValidationError):
        ExecutionStrategy(
            identity="es-1",
            coordination=CoordinationModel.SEQUENTIAL,
            runtime_policy={},
            approval_policy=ApprovalTaxonomy.AUTOMATIC,
            retry_policy=RetryBehavior.NEVER_RETRY,
            timeout_policy={},
            validation_policy={},
            recovery_policy={},
            # checkpoint_policy omitted
        )  # type: ignore[call-arg]


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        ExecutionStrategy(
            identity="es-1",
            coordination=CoordinationModel.SEQUENTIAL,
            runtime_policy={},
            approval_policy=ApprovalTaxonomy.AUTOMATIC,
            retry_policy=RetryBehavior.NEVER_RETRY,
            timeout_policy={},
            validation_policy={},
            recovery_policy={},
            checkpoint_policy={},
            unexpected="nope",  # type: ignore[call-arg]
        )


def test_serialization_round_trip() -> None:
    es = _build_execution_strategy()
    assert ExecutionStrategy.model_validate(es.model_dump()) == es


def test_lifecycle_name() -> None:
    assert ExecutionStrategy.LIFECYCLE_NAME in MACHINES
