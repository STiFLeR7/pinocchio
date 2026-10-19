"""Per-object lifecycle status enums.

Each operational object owns exactly one current state (INV-13/14), which is a
*projection* of the append-only event log — never an independently stored,
authoritative machine. These enums name each object's lifecycle vocabulary; the
allowed transitions between them are defined in ``nexus_core.state.transitions``
and validated by ``nexus_core.state.machine``.

Per-object vocabularies are specialized projections of the unified ``CoreState``
(``nexus_core.state.core_state``); each conforms to it while using object-specific
state names taken verbatim from the frozen contracts.
"""

from __future__ import annotations

from enum import StrEnum


class IntentStatus(StrEnum):
    RECEIVED = "received"
    INTERPRETING = "interpreting"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"


class GoalStatus(StrEnum):
    NORMALIZED = "normalized"
    CONTEXTUALIZING = "contextualizing"
    PLANNING = "planning"
    EXECUTING = "executing"
    ACHIEVED = "achieved"
    ABANDONED = "abandoned"


class ContextPackageStatus(StrEnum):
    ASSEMBLING = "assembling"
    VALIDATING = "validating"
    READY = "ready"
    ENRICHING = "enriching"
    SUPERSEDED = "superseded"
    INVALIDATED = "invalidated"


class PlanStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class WorkPackageStatus(StrEnum):
    CREATED = "created"
    READY = "ready"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    FAILED = "failed"
    EXPIRED = "expired"


class ExecutionStrategyStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class ExecutionGraphStatus(StrEnum):
    CREATED = "created"
    READY = "ready"
    EXECUTING = "executing"
    PAUSED = "paused"
    WAITING = "waiting"
    BLOCKED = "blocked"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SkillStatus(StrEnum):
    REGISTERED = "registered"
    SELECTED = "selected"
    PREPARED = "prepared"
    EXECUTING = "executing"
    VALIDATED = "validated"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class CapabilityStatus(StrEnum):
    DRAFT = "draft"
    REGISTERED = "registered"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class ObservationStage(StrEnum):
    DERIVED = "derived"
    RECORDED = "recorded"
    SUPERSEDED = "superseded"


class EventStage(StrEnum):
    """Delivery stages of a fixed, immutable Event record (not mutable state)."""

    OCCURRED = "occurred"
    CREATED = "created"
    PUBLISHED = "published"
    DELIVERED = "delivered"
    PROCESSED = "processed"
    PERSISTED = "persisted"
    ARCHIVED = "archived"


class CheckpointStage(StrEnum):
    CREATED = "created"
    PERSISTED = "persisted"
    AVAILABLE = "available"
    RESTORED = "restored"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class PolicyStatus(StrEnum):
    REGISTERED = "registered"
    VALIDATED = "validated"
    ENABLED = "enabled"
    DISABLED = "disabled"


class KnowledgeIngestionStatus(StrEnum):
    CANDIDATE = "candidate"
    VALIDATING = "validating"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ReflectionStatus(StrEnum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    CANDIDATES_PROPOSED = "candidates_proposed"
    DISCARDED = "discarded"
