"""Reflection Report — the immutable, reference-only analytical output of one reflection.

Milestone 3. A :class:`ReflectionReport` is the Reflection Engine's output value object (the
same pattern as the Runtime Session / Execution Result / Validation Report / Recovery Plan: a
layer output, not a frozen core contract). It records the deterministic summaries of the
history, the detected operational patterns, the confirmed observations, the Knowledge
*Candidates* (advisory — INV-25), an explainable reasoning trace, and the overall confidence.

It **references existing objects by id and never duplicates them** (INV-12, ADR-003): patterns
carry episode/report/plan references, and the report's ``evidence_refs`` point at the reflected
operations. Every field is a deterministic function of the collected history, so identical
history yields a byte-identical report (doc 26 *Evidence First* / reproducible; INV-31).
"""

from __future__ import annotations

from pydantic import Field

from nexus_core.contracts.base import Reference, Struct, ValueObject
from nexus_reflection.patterns import KnowledgeCandidate, OperationalPattern
from nexus_reflection.vocabulary import (
    REFLECTION_REPORT_TARGET_TYPE,
    ConfidenceLevel,
    ReflectionStage,
)


class ReflectionReport(ValueObject):
    """The immutable, evidence-referencing analytical summary of one operational window."""

    identity: str
    scope: str
    stage: ReflectionStage
    confidence: ConfidenceLevel
    correlation_identifier: str = ""
    episode_count: int = 0
    execution_summary: Struct = Field(default_factory=dict)
    validation_summary: Struct = Field(default_factory=dict)
    recovery_summary: Struct = Field(default_factory=dict)
    patterns: tuple[OperationalPattern, ...] = ()
    confirmed_observations: tuple[str, ...] = ()
    knowledge_candidates: tuple[KnowledgeCandidate, ...] = ()
    recommendations: tuple[str, ...] = ()
    evidence_refs: tuple[Reference, ...] = ()
    reasoning_trace: tuple[str, ...] = ()
    reflector: str = "nexus_reflection"
    timestamp: str = ""

    def reference(self) -> Reference:
        """A typed by-id pointer to this report."""
        return Reference(target_type=REFLECTION_REPORT_TARGET_TYPE, identifier=self.identity)

    @property
    def is_empty(self) -> bool:
        """Whether there was no operational history to reflect on."""
        return self.episode_count == 0
