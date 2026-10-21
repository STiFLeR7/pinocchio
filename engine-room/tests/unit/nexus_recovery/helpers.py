"""Shared, deterministic builders for the Recovery Engine test suite.

Provides a :class:`ValidationReport` factory (so rule/evaluator/engine tests exercise recovery
decisions without running a real validation) and reuses the Validation suite's deterministic
:func:`execution_result` factory (the failure signals Recovery classifies). Every builder is
deterministic — no clock, no randomness — so a replay reproduces identical plans and event
streams.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_validation.report import ValidationReport
from nexus_validation.vocabulary import (
    EVIDENCE_TARGET_TYPE,
    EXECUTION_RESULT_TARGET_TYPE,
    ValidationDecision,
    ValidationStage,
)
from tests.unit.nexus_validation.helpers import SESSION, execution_result

CORRELATION = "cor-val"
CHECKPOINT = "cp-rts-pkg-val-01-0003"

__all__ = ["CHECKPOINT", "CORRELATION", "SESSION", "checkpoint_ref", "execution_result", "report"]

_STAGE = {
    ValidationDecision.PASSED: ValidationStage.PASSED,
    ValidationDecision.FAILED: ValidationStage.FAILED,
    ValidationDecision.PARTIAL: ValidationStage.PARTIAL,
    ValidationDecision.REQUIRES_REVIEW: ValidationStage.REQUIRES_REVIEW,
}


def _ref(target_type: str, identifier: str) -> Reference:
    return Reference(target_type=target_type, identifier=identifier)


def report(
    *,
    decision: ValidationDecision = ValidationDecision.PASSED,
    session: str = SESSION,
    work_package_id: str = "wp-val",
    runtime: str | None = "claude-code",
    confidence: float = 1.0,
    evidence: int = 1,
    correlation: str = CORRELATION,
) -> ValidationReport:
    """Build a deterministic :class:`ValidationReport` fixture for recovery tests."""
    return ValidationReport(
        identity=f"vr-{session}",
        decision=decision,
        stage=_STAGE[decision],
        confidence=confidence,
        session_ref=_ref("runtime_session", session),
        work_package_ref=_ref("work_package", work_package_id),
        execution_result_ref=_ref(EXECUTION_RESULT_TARGET_TYPE, session),
        runtime_ref=_ref("harness", runtime) if runtime else None,
        correlation_identifier=correlation,
        evidence_refs=tuple(
            _ref(EVIDENCE_TARGET_TYPE, f"ev-{session}-{i:04d}") for i in range(evidence)
        ),
    )


def checkpoint_ref(identifier: str = CHECKPOINT) -> Reference:
    """A checkpoint :class:`Reference` (the latest valid checkpoint to resume from)."""
    return _ref("checkpoint", identifier)
