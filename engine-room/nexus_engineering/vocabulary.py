"""Engineering-reasoning vocabulary — the closed value sets EI reasons over.

These are Engineering-Intelligence value enums (the engineering-strategy contract is a declared
void, so they are subsystem vocabularies, not new frozen core enums — INV-07 discipline). The
**complexity class** is deliberately *not* redefined here: EI reuses Estimation's
:class:`~nexus_estimation.vocabulary.ComplexityBand` (it consumes the complexity estimate, it
never re-estimates), and approval *levels* reuse the frozen
:class:`~nexus_core.contracts.enums.ApprovalTaxonomy`.
"""

from __future__ import annotations

from enum import StrEnum


class WorkClassification(StrEnum):
    """What kind of engineering work this is (the seed facet — `engineering/04`)."""

    BUG_FIX = "bug_fix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    INVESTIGATION = "investigation"
    MIGRATION = "migration"
    RESEARCH = "research"
    DOCUMENTATION = "documentation"
    RELEASE = "release"
    GENERIC = "generic"


class ApproachType(StrEnum):
    """The engineering posture (strategy type)."""

    SURGICAL = "surgical"
    INVESTIGATE_FIRST = "investigate_first"
    EXPLORATORY = "exploratory"
    RESEARCH_FIRST = "research_first"
    INCREMENTAL = "incremental"
    SPIKE_THEN_IMPLEMENT = "spike_then_implement"
    VALIDATION_FIRST = "validation_first"
    REFACTOR_SAFE = "refactor_safe"


class ExecutionStyle(StrEnum):
    """The coordination style a runtime posture implies (intent; Orchestration enacts)."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    MIXED = "mixed"


class ValidationRigor(StrEnum):
    """How strong the completion bar must be (→ Validation, INV-20)."""

    LOW = "low"
    STANDARD = "standard"
    HIGH = "high"
    STRICT = "strict"


class RecoveryPosture(StrEnum):
    """The recovery bias EI recommends (intent; Recovery decides — INV-22)."""

    RETRY_THEN_ESCALATE = "retry_then_escalate"
    CHECKPOINT_AND_ESCALATE = "checkpoint_and_escalate"
    ESCALATE_IMMEDIATELY = "escalate_immediately"


class AutonomyLevel(StrEnum):
    """How much may proceed without human approval (proposal; Policy decides — INV-28/29)."""

    AUTONOMOUS = "autonomous"
    SUPERVISED = "supervised"
    GATED = "gated"
    MANUAL = "manual"


class RiskLevel(StrEnum):
    """Blast-radius / reversibility envelope EI assesses (→ Governance / Planning)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ObservabilityLevel(StrEnum):
    """The observability posture EI recommends (→ Operations)."""

    MINIMAL = "minimal"
    STANDARD = "standard"
    VERBOSE = "verbose"
    AUDIT = "audit"
