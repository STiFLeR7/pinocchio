"""Shared value enums and category taxonomies — defined once, reused everywhere.

These are the canonical closed vocabularies the frozen contracts define. Two
confidence ladders are intentionally distinct and must not be merged
(``ConfidenceLadder`` for Knowledge/Reflection vs. ``InterpretationConfidence``
for Intent/Goal/Context). Per-object *lifecycle status* enums live in
``status.py``; the unified ``CoreState`` lives in ``nexus_core.state``.
"""

from __future__ import annotations

from enum import StrEnum

# --------------------------------------------------------------------------- #
# Shared value ladders                                                         #
# --------------------------------------------------------------------------- #


class Priority(StrEnum):
    """Operational priority ladder (Goal, Work Package, Intent estimate, …)."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BACKGROUND = "background"


class Domain(StrEnum):
    """Operational domain classification (domain-agnostic process, domain label)."""

    SOFTWARE = "software"
    RESEARCH = "research"
    WRITING = "writing"
    OPERATIONS = "operations"
    PERSONAL = "personal"
    BUSINESS = "business"


class ConfidenceLadder(StrEnum):
    """Earned confidence ladder for Knowledge and Reflection (rises with evidence)."""

    EXPERIMENTAL = "experimental"
    OBSERVED = "observed"
    VALIDATED = "validated"
    PROVEN = "proven"


class InterpretationConfidence(StrEnum):
    """Interpretation confidence for Intent / Goal / Context (distinct ladder)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


# --------------------------------------------------------------------------- #
# Governance / coordination vocabularies (ADR-004)                            #
# --------------------------------------------------------------------------- #


class ApprovalTaxonomy(StrEnum):
    """The single platform approval taxonomy (ADR-004 §3.3)."""

    AUTOMATIC = "automatic"
    HUMAN_REVIEW = "human_review"
    MULTI_STAGE = "multi_stage"
    DEFERRED = "deferred"


class PolicyDecision(StrEnum):
    """Closed governance decision set (ADR-004 §3.2). Recovery strategies are NOT members."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    DELAY = "delay"
    ESCALATE = "escalate"
    REQUEST_INFORMATION = "request_information"


class CoordinationModel(StrEnum):
    """Execution Strategy coordination models."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HYBRID = "hybrid"
    PIPELINE = "pipeline"
    EVENT_DRIVEN = "event_driven"
    APPROVAL_DRIVEN = "approval_driven"


class RetryBehavior(StrEnum):
    """Execution Strategy retry behaviors (declaration; Recovery selects)."""

    NEVER_RETRY = "never_retry"
    FIXED_RETRY = "fixed_retry"
    EXPONENTIAL_RETRY = "exponential_retry"
    RUNTIME_SWITCH = "runtime_switch"
    HUMAN_ESCALATION = "human_escalation"


class RecoveryBehavior(StrEnum):
    """Recovery options shared by Execution Strategy and Recovery selection."""

    PAUSE = "pause"
    RESUME = "resume"
    RETRY = "retry"
    ESCALATE = "escalate"
    ABORT = "abort"


# --------------------------------------------------------------------------- #
# Topology / runtime / observation vocabularies                               #
# --------------------------------------------------------------------------- #


class EdgeType(StrEnum):
    """Execution Graph edge types (dependencies are Execution edges; INV-10)."""

    EXECUTION = "execution"
    DATA = "data"
    APPROVAL = "approval"
    RECOVERY = "recovery"
    CONDITIONAL = "conditional"
    SYNCHRONIZATION = "synchronization"


class OperationalHealth(StrEnum):
    """Supervision operational-health classification (Observation)."""

    HEALTHY = "healthy"
    WAITING = "waiting"
    PAUSED = "paused"
    DEGRADED = "degraded"
    STALLED = "stalled"
    FAILED = "failed"
    COMPLETED = "completed"


class InterventionRecommendation(StrEnum):
    """Supervision intervention recommendations (Supervision recommends; INV-23)."""

    CONTINUE = "continue"
    PAUSE = "pause"
    RESUME = "resume"
    RETRY = "retry"
    ESCALATE = "escalate"
    REQUEST_CONTEXT = "request_context"
    SWITCH_RUNTIME = "switch_runtime"
    CANCEL = "cancel"


class Modality(StrEnum):
    """Operator request modality (Intent input)."""

    NATURAL_LANGUAGE = "natural_language"
    STRUCTURED_REQUEST = "structured_request"
    CONVERSATION = "conversation"
    VOICE_TRANSCRIPT = "voice_transcript"


# --------------------------------------------------------------------------- #
# Resource / artifact / knowledge vocabularies                                #
# --------------------------------------------------------------------------- #


class ResourceAllocationState(StrEnum):
    """Resource allocation state (Orchestration-owned projection)."""

    AVAILABLE = "available"
    RESERVED = "reserved"
    ALLOCATED = "allocated"
    RELEASED = "released"


class ResourceAvailability(StrEnum):
    """Resource availability projection read from the Harness Registry (INV-36)."""

    AVAILABLE = "available"
    BUSY = "busy"
    RESERVED = "reserved"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ArtifactStatus(StrEnum):
    """Single Artifact status vocabulary (ADR-003 §3.7)."""

    DRAFT = "draft"
    GENERATED = "generated"
    VALIDATED = "validated"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Freshness(StrEnum):
    """Knowledge freshness lifecycle."""

    CURRENT = "current"
    HISTORICAL = "historical"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"
    SUPERSEDED = "superseded"


# --------------------------------------------------------------------------- #
# Category taxonomies — intentionally distinct per object (do NOT unify)       #
# --------------------------------------------------------------------------- #


class SkillCategory(StrEnum):
    ANALYSIS = "analysis"
    DEVELOPMENT = "development"
    DOCUMENTATION = "documentation"
    OPERATIONS = "operations"
    PERSONAL = "personal"


class CapabilityCategory(StrEnum):
    ANALYSIS = "analysis"
    DEVELOPMENT = "development"
    DOCUMENTATION = "documentation"
    COMMUNICATION = "communication"
    OPERATIONS = "operations"
    KNOWLEDGE = "knowledge"


class ResourceType(StrEnum):
    HUMAN = "human"
    RUNTIME = "runtime"
    WORKSPACE = "workspace"
    COMMUNICATION = "communication"
    INFRASTRUCTURE = "infrastructure"
    KNOWLEDGE = "knowledge"
    COMPUTE = "compute"


class ArtifactType(StrEnum):
    SOURCE = "source"
    DOCUMENTATION = "documentation"
    RESEARCH = "research"
    OPERATIONAL = "operational"
    COMMUNICATION = "communication"
    KNOWLEDGE = "knowledge"


class CheckpointType(StrEnum):
    EXECUTION = "execution"
    WORKFLOW = "workflow"
    CONTEXT = "context"
    VALIDATION = "validation"
    RECOVERY = "recovery"


class PolicyCategory(StrEnum):
    GOVERNANCE = "governance"
    EXECUTION = "execution"
    PLANNING = "planning"
    VALIDATION = "validation"
    RECOVERY = "recovery"


class KnowledgeCategory(StrEnum):
    REPOSITORY = "repository"
    WORKSPACE = "workspace"
    SKILL = "skill"
    OPERATIONAL = "operational"
    ORGANIZATIONAL = "organizational"
    PERSONAL = "personal"


class KnowledgeType(StrEnum):
    PATTERN = "pattern"
    DECISION = "decision"
    LESSON = "lesson"
    FINDING = "finding"
    RELATIONSHIP = "relationship"
    STRATEGY = "strategy"
    CONSTRAINT = "constraint"
    CAPABILITY = "capability"
    ARTIFACT_REF = "artifact_ref"
    OBSERVATION_REF = "observation_ref"


class KnowledgeSource(StrEnum):
    EXECUTION = "execution"
    REFLECTION = "reflection"
    VALIDATION = "validation"
    DOCUMENTATION = "documentation"
    RESEARCH = "research"
    OPERATOR_DECISIONS = "operator_decisions"
    ARCHITECTURE = "architecture"
    EXTERNAL_SYSTEMS = "external_systems"


class ReflectionCategory(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    PROCESS = "process"
    STRATEGY = "strategy"
    KNOWLEDGE = "knowledge"
