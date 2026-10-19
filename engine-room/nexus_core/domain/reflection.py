"""Reflection — interpretation of validated outcomes into reusable understanding.

Contract: ``contracts/reflection.md``. Owned by the Reflection layer. Binding:
ADR-003 (canonical object model; reflection produces candidates), ADR-001
(event-sourced state; operates on validated outcomes from the log). Invariants:
INV-25 (Reflection produces Knowledge Candidates only and never writes Knowledge
directly — it is advisory until Knowledge accepts), validated-inputs-only
(``inputs`` are exclusively validated outcomes — required AND non-empty via
``Field(min_length=1)``; Reflection never operates on incomplete information),
INV-26 (no direct Planning dependency — learning reaches Planning only through
persisted Knowledge), INV-13/14/15, INV-17, INV-31.

Uses ``ConfidenceLadder`` (the earned ladder shared with Knowledge), NOT
``InterpretationConfidence``. The ``status`` field is the lifecycle status (a
projection of the event log), optional until projected.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from nexus_core.contracts.base import DomainObject, Reference, Struct
from nexus_core.contracts.enums import ConfidenceLadder, ReflectionCategory
from nexus_core.contracts.status import ReflectionStatus


class Reflection(DomainObject):
    """An interpretation of validated outcomes (contract: reflection.md). Candidates only."""

    LIFECYCLE_NAME: ClassVar[str] = "reflection"

    # --- required ---------------------------------------------------------- #
    identity: str = Field(min_length=1)
    """Stable, unique identifier; addressable and replayable for the platform's life."""
    correlation_identifier: str = Field(min_length=1)
    """Correlation/trace lineage tying the Reflection to the validated operation(s) it interprets."""
    category: ReflectionCategory
    """The reflection category (Success / Failure / Process / Strategy / Knowledge)."""
    inputs: tuple[Reference, ...] = Field(min_length=1)
    """References (by id) to validated operational inputs — required AND non-empty; validated only."""
    findings: str = Field(min_length=1)
    """The interpretation produced: what happened, why, what worked, what failed, what should change."""
    confidence: ConfidenceLadder
    """Confidence on the earned ladder shared with Knowledge (Experimental / Observed / Validated / Proven)."""

    # --- optional ---------------------------------------------------------- #
    status: ReflectionStatus | None = None
    """Current lifecycle state — a projection of the event log (ADR-001); optional until projected."""
    lessons: tuple[str, ...] = ()
    """Discrete, actionable takeaways from the validated outcome."""
    patterns: tuple[Struct, ...] = ()
    """Identified operational patterns (repeated successes, bottlenecks, reusable strategies, …)."""
    anti_patterns: tuple[Struct, ...] = ()
    """Identified failure patterns / things that should never be repeated."""
    recommendations: tuple[Struct, ...] = ()
    """Improvement recommendations, advisory until accepted."""
    knowledge_candidates: tuple[Struct, ...] = ()
    """The Knowledge Candidates this Reflection proposes for ingestion (present once proposed)."""
    root_causes: tuple[Struct, ...] = ()
    """For Failure/Process reflections, analyzed root causes and recovery effectiveness."""
    assumptions_assessment: Struct | None = None
    """Which assumptions proved correct and which proved incorrect."""
    evidence_refs: tuple[Reference, ...] = ()
    """References (by id) to the validated evidence underpinning the findings (keeps Knowledge backed)."""
    rationale: str | None = None
    """Explanation of how the findings follow from the evidence (explainability)."""
    metadata: Struct | None = None
    """Non-behavioral descriptive attributes (tags, ownership notes) that do not affect interpretation."""
