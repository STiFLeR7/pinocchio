"""Reflection vocabularies — the closed enumerations and reference tags of the layer.

Reflection is the **analytical layer** over completed operational history (doc 26). It
*explains* system behaviour and never changes it: it never executes, retries, plans, mutates
policy, updates Knowledge, or invokes AI (doc 26 boundaries; INV-25 — Reflection produces
Knowledge *Candidates*, it never persists Knowledge; INV-26 — Planning never depends directly
on Reflection).

The **confidence levels are doc-26 canon** (``Experimental / Observed / Validated / Proven``),
derived here deterministically from repetition count (never a learned or AI score). Pattern
kinds enumerate the deterministic analyses the program requires. There is no frozen core
contract for a Reflection Report, an Operational Pattern, or a Knowledge Candidate — they are
Reflection *outputs* (the same pattern as the Runtime Session / Execution Result / Validation
Report / Recovery Plan), so they are Reflection-layer value objects. Only the closed
vocabularies and canonical ``Reference`` ``target_type`` strings live here.
"""

from __future__ import annotations

from enum import StrEnum


class ConfidenceLevel(StrEnum):
    """How strongly an observation is corroborated (doc 26 *Confidence*; derived, not learned)."""

    EXPERIMENTAL = "experimental"
    OBSERVED = "observed"
    VALIDATED = "validated"
    PROVEN = "proven"


class ReflectionStage(StrEnum):
    """The Reflection lifecycle (doc 26 *Reflection Lifecycle*; the deterministic subset)."""

    PENDING = "pending"
    COLLECTING = "collecting"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class PatternKind(StrEnum):
    """The deterministic operational analyses Reflection performs (doc 26 *Pattern ID*)."""

    REPEATED_FAILURE = "repeated_failure"
    REPEATED_SUCCESS = "repeated_success"
    RETRY_FREQUENCY = "retry_frequency"
    VALIDATION_OUTCOME = "validation_outcome"
    RECOVERY_DECISION = "recovery_decision"
    RUNTIME_UTILIZATION = "runtime_utilization"
    EXECUTION_DURATION = "execution_duration"
    BOTTLENECK = "bottleneck"


# --- canonical Reference target_type strings ---------------------------------- #
REFLECTION_REPORT_TARGET_TYPE = "reflection_report"
OPERATIONAL_PATTERN_TARGET_TYPE = "operational_pattern"
KNOWLEDGE_CANDIDATE_TARGET_TYPE = "knowledge_candidate"
OPERATIONAL_EPISODE_TARGET_TYPE = "operational_episode"
VALIDATION_REPORT_TARGET_TYPE = "validation_report"
RECOVERY_PLAN_TARGET_TYPE = "recovery_plan"
EXECUTION_RESULT_TARGET_TYPE = "execution_result"
