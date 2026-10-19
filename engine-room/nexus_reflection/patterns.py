"""Operational patterns & knowledge candidates — Reflection's immutable analytical outputs.

An :class:`OperationalPattern` is one deterministic finding over the history (a repeated
failure, a retry frequency, a bottleneck, ...). A :class:`KnowledgeCandidate` is an *advisory*
recommendation for the future Knowledge subsystem — Reflection produces candidates, never
persistent Knowledge (INV-25). Both are immutable and reference the episodes/reports/plans they
were derived from by id (INV-12); they never embed collected data.

Confidence is derived **deterministically from repetition count** (doc 26 *Confidence* levels),
not learned or AI-scored: a one-off finding is ``Experimental``; corroboration raises it toward
``Proven``. This lets Knowledge prioritise higher-confidence reflections (doc 26).
"""

from __future__ import annotations

from pydantic import Field

from nexus_core.contracts.base import Reference, Struct, ValueObject
from nexus_reflection.vocabulary import (
    KNOWLEDGE_CANDIDATE_TARGET_TYPE,
    OPERATIONAL_PATTERN_TARGET_TYPE,
    ConfidenceLevel,
    PatternKind,
)


def confidence_for(occurrences: int) -> ConfidenceLevel:
    """Map a repetition count onto a doc-26 confidence level (deterministic)."""
    if occurrences >= 5:
        return ConfidenceLevel.PROVEN
    if occurrences >= 3:
        return ConfidenceLevel.VALIDATED
    if occurrences == 2:
        return ConfidenceLevel.OBSERVED
    return ConfidenceLevel.EXPERIMENTAL


class OperationalPattern(ValueObject):
    """One immutable, evidence-referencing finding over the operational history."""

    identity: str
    kind: PatternKind
    subject: str
    description: str
    occurrences: int
    population: int
    confidence: ConfidenceLevel
    detail: Struct = Field(default_factory=dict)
    evidence_refs: tuple[Reference, ...] = ()
    correlation_identifier: str = ""

    def reference(self) -> Reference:
        """A typed by-id pointer to this pattern."""
        return Reference(target_type=OPERATIONAL_PATTERN_TARGET_TYPE, identifier=self.identity)

    @property
    def is_confirmed(self) -> bool:
        """Whether the finding is corroborated (repeated at least twice)."""
        return self.occurrences >= 2


class KnowledgeCandidate(ValueObject):
    """An advisory recommendation for the future Knowledge subsystem (INV-25 — a candidate)."""

    identity: str
    summary: str
    confidence: ConfidenceLevel
    source_pattern_ref: Reference | None = None
    evidence_refs: tuple[Reference, ...] = ()

    def reference(self) -> Reference:
        """A typed by-id pointer to this candidate."""
        return Reference(target_type=KNOWLEDGE_CANDIDATE_TARGET_TYPE, identifier=self.identity)
