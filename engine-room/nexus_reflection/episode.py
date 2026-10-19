"""Operational episode — the correlated, immutable view of one completed operation.

The Reflection Collector (Milestone 1) correlates the three per-execution outputs — the
Execution Result, the Validation Report, and the Recovery Plan — into one
:class:`OperationalEpisode` keyed by the execution **session**. The episode is a *read-only
projection*: it references the underlying objects by id (INV-12) and copies only the small,
deterministic descriptors the analyzers aggregate over (verdict, recovery decision, failure
category, retry basis, runtime, exit status, metrics). It never modifies the collected data
(doc 26 *Evidence First*).
"""

from __future__ import annotations

from pydantic import Field

from nexus_core.contracts.base import Reference, Struct, ValueObject
from nexus_recovery.vocabulary import FailureCategory, RecoveryDecision
from nexus_reflection.vocabulary import OPERATIONAL_EPISODE_TARGET_TYPE
from nexus_validation.vocabulary import ValidationDecision


class OperationalEpisode(ValueObject):
    """One correlated, immutable operation: execution + validation + recovery, by reference."""

    session: str
    correlation_identifier: str = ""
    runtime: str | None = None
    validation_decision: ValidationDecision | None = None
    recovery_decision: RecoveryDecision | None = None
    failure_category: FailureCategory | None = None
    succeeded: bool = False
    retry_eligible: bool = False
    attempts_used: int = 0
    exit_status: int | None = None
    error_class: str | None = None
    metrics: Struct = Field(default_factory=dict)
    execution_result_ref: Reference | None = None
    validation_report_ref: Reference | None = None
    recovery_plan_ref: Reference | None = None
    evidence_refs: tuple[Reference, ...] = ()

    def reference(self) -> Reference:
        """A typed by-id pointer to this episode."""
        return Reference(target_type=OPERATIONAL_EPISODE_TARGET_TYPE, identifier=self.session)

    @property
    def is_failure(self) -> bool:
        """Whether this operation did not pass validation (a failure factor)."""
        return self.validation_decision is not None and not self.succeeded
