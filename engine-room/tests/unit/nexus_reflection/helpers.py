"""Shared, deterministic builders for the Reflection Engine test suite.

Reflection analyses a *history* of completed operations, so the helpers build correlated
triples — an Execution Result, a Validation Report, and a Recovery Plan — per session, from
which tests assemble multi-episode histories. The Execution Result factory is reused from the
Validation suite; the Validation Report and Recovery Plan are built directly (decoupled from
the engines). Every builder is deterministic.
"""

from __future__ import annotations

from collections.abc import Sequence

from nexus_core.contracts.base import Reference, Struct
from nexus_recovery.plan import RecoveryPlan
from nexus_recovery.vocabulary import FailureCategory, RecoveryDecision, RecoveryStage
from nexus_validation.report import ValidationReport
from nexus_validation.vocabulary import (
    EVIDENCE_TARGET_TYPE,
    EXECUTION_RESULT_TARGET_TYPE,
    ValidationDecision,
    ValidationStage,
)
from tests.unit.nexus_validation.helpers import execution_result as _val_execution_result

SCOPE = "op-window-1"
CORRELATION = "cor-refl"

_VAL_STAGE = {
    ValidationDecision.PASSED: ValidationStage.PASSED,
    ValidationDecision.FAILED: ValidationStage.FAILED,
    ValidationDecision.PARTIAL: ValidationStage.PARTIAL,
    ValidationDecision.REQUIRES_REVIEW: ValidationStage.REQUIRES_REVIEW,
}
_REC_STAGE = {
    RecoveryDecision.COMPLETE: RecoveryStage.COMPLETE,
    RecoveryDecision.RETRY: RecoveryStage.RETRY,
    RecoveryDecision.RESUME: RecoveryStage.RESUME,
    RecoveryDecision.ESCALATE: RecoveryStage.ESCALATED,
    RecoveryDecision.AWAIT_APPROVAL: RecoveryStage.WAITING_APPROVAL,
    RecoveryDecision.ABORT: RecoveryStage.ABORTED,
}


def _ref(target_type: str, identifier: str) -> Reference:
    return Reference(target_type=target_type, identifier=identifier)


def execution_result(
    session: str, *, runtime: str | None = "claude-code", metrics: Struct | None = None
):  # type: ignore[no-untyped-def]
    """A deterministic Execution Result for a session (reused from the Validation suite)."""
    return _val_execution_result(session=session, runtime=runtime, metrics=metrics)


def validation_report(
    session: str,
    *,
    decision: ValidationDecision = ValidationDecision.PASSED,
    runtime: str | None = "claude-code",
    correlation: str = CORRELATION,
) -> ValidationReport:
    """A deterministic Validation Report for a session."""
    return ValidationReport(
        identity=f"vr-{session}",
        decision=decision,
        stage=_VAL_STAGE[decision],
        confidence=1.0 if decision is ValidationDecision.PASSED else 0.5,
        session_ref=_ref("runtime_session", session),
        work_package_ref=_ref("work_package", "wp"),
        execution_result_ref=_ref(EXECUTION_RESULT_TARGET_TYPE, session),
        runtime_ref=_ref("harness", runtime) if runtime else None,
        correlation_identifier=correlation,
        evidence_refs=(_ref(EVIDENCE_TARGET_TYPE, f"ev-{session}-0000"),),
    )


def recovery_plan(
    session: str,
    *,
    decision: RecoveryDecision = RecoveryDecision.COMPLETE,
    failure_category: FailureCategory = FailureCategory.NONE,
    runtime: str | None = "claude-code",
    retry_eligible: bool = False,
    attempts_used: int = 1,
    correlation: str = CORRELATION,
) -> RecoveryPlan:
    """A deterministic Recovery Plan for a session."""
    return RecoveryPlan(
        identity=f"rp-{session}",
        decision=decision,
        stage=_REC_STAGE[decision],
        failure_category=failure_category,
        session_ref=_ref("runtime_session", session),
        work_package_ref=_ref("work_package", "wp"),
        validation_report_ref=_ref("validation_report", f"vr-{session}"),
        execution_result_ref=_ref(EXECUTION_RESULT_TARGET_TYPE, session),
        runtime_ref=_ref("harness", runtime) if runtime else None,
        correlation_identifier=correlation,
        retry_eligible=retry_eligible,
        attempts_used=attempts_used,
    )


def sessions(n: int, prefix: str = "rts-op") -> Sequence[str]:
    """`n` deterministic session identifiers."""
    return tuple(f"{prefix}-{i:02d}" for i in range(n))
