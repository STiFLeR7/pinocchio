"""Validation vocabularies — the closed enumerations and reference tags of the layer.

The **decision vocabulary is doc-14 canon**: ``Passed / Failed / Partial / Requires Review``
(the program prompt's "Success / Failure / Partial Success / Inconclusive" are informal
synonyms mapped 1:1 — see ``docs/runtime/validation/VALIDATION_RULES.md``). The lifecycle
stages are doc-14's Validation States; the automated engine drives the deterministic subset
and reaches ``Requires Review`` where doc 14 would await human review (the human workflow is
a later phase, not implemented here).

There is no frozen core contract for Evidence or a Validation Report — Evidence is *produced
by Validation* (INV-12) and the Report is a Validation output, so both are Validation-layer
value objects (the same pattern as the Runtime Session). Only the closed vocabularies and
canonical ``Reference`` ``target_type`` strings live here.
"""

from __future__ import annotations

from enum import StrEnum


class ValidationDecision(StrEnum):
    """The four canonical validation outcomes (doc 14 *Outputs*)."""

    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    REQUIRES_REVIEW = "requires_review"


class ValidationStage(StrEnum):
    """The Validation lifecycle (doc 14 *Validation States*; human/cancel deferred)."""

    PENDING = "pending"
    COLLECTING_EVIDENCE = "collecting_evidence"
    VALIDATING = "validating"
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    REQUIRES_REVIEW = "requires_review"


class EvidenceSource(StrEnum):
    """Where a piece of Evidence was collected from (doc 14 *Evidence Model*, Milestone 1)."""

    ARTIFACT = "artifact"
    STDOUT = "stdout"
    STDERR = "stderr"
    STRUCTURED_OUTPUT = "structured_output"
    RUNTIME_METADATA = "runtime_metadata"
    EXECUTION_METRIC = "execution_metric"


class RuleOutcome(StrEnum):
    """The deterministic outcome of one validation rule against the Evidence."""

    SATISFIED = "satisfied"
    VIOLATED = "violated"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"


# --- canonical Reference target_type strings ---------------------------------- #
EVIDENCE_TARGET_TYPE = "evidence"
VALIDATION_REPORT_TARGET_TYPE = "validation_report"
EXECUTION_RESULT_TARGET_TYPE = "execution_result"
ARTIFACT_TARGET_TYPE = "artifact"
