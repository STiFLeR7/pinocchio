"""Knowledge — a unit of persistent, evidence-backed operational understanding.

Contract: ``contracts/knowledge.md``. Owned by the Knowledge System. Binding:
ADR-001 (event-sourced state), ADR-003 (canonical object model). Invariants:
INV-24 (evidence-backed — only validated outcomes become Knowledge; ``evidence_refs``
is required AND non-empty via ``Field(min_length=1)``, an entry with no supporting
evidence cannot exist), INV-25 (Knowledge Entries derive from Reflection's
Knowledge Candidates; Reflection never writes Knowledge directly), INV-27
(references Artifacts/Observations/Evidence by id, never duplicates their content),
INV-26 (Planning depends on Knowledge, not Reflection directly), INV-06,
INV-13/14/15, INV-31.

Uses ``ConfidenceLadder`` (the earned ladder shared with Reflection), NOT
``InterpretationConfidence``. The ``status`` field is the ingestion-lifecycle
status (a projection of the event log), optional until projected.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from nexus_core.contracts.base import DomainObject, Reference, Struct
from nexus_core.contracts.enums import (
    ConfidenceLadder,
    Domain,
    Freshness,
    KnowledgeCategory,
    KnowledgeSource,
    KnowledgeType,
)
from nexus_core.contracts.status import KnowledgeIngestionStatus


class Knowledge(DomainObject):
    """An evidence-backed unit of understanding (contract: knowledge.md). Never assumed."""

    LIFECYCLE_NAME: ClassVar[str] = "knowledge"

    # --- required ---------------------------------------------------------- #
    identity: str = Field(min_length=1)
    """Stable, unique identifier; a stable node id in the operational graph, replayable for life."""
    correlation_identifier: str = Field(min_length=1)
    """Correlation/trace lineage tying the entry to the operations and evidence it derived from."""
    type: KnowledgeType
    """The Knowledge object type (Pattern / Decision / Lesson / Finding / …); not raw text."""
    understanding: str = Field(min_length=1)
    """The operational understanding asserted — it explains, it does not merely record."""
    evidence_refs: tuple[Reference, ...] = Field(min_length=1)
    """References (by id) to validated evidence — required AND non-empty; Knowledge is evidence-backed."""
    confidence: ConfidenceLadder
    """Place on the earned confidence ladder (Experimental / Observed / Validated / Proven)."""
    freshness: Freshness
    """Freshness state (Current / Historical / Deprecated / Archived / Superseded); derived."""

    # --- optional ---------------------------------------------------------- #
    status: KnowledgeIngestionStatus | None = None
    """Current ingestion-lifecycle state — a projection of the event log; optional until projected."""
    category: KnowledgeCategory | None = None
    """The knowledge category (Repository / Workspace / Skill / …), used for retrieval scoping."""
    domain: Domain | None = None
    """Operational domain the understanding applies to; scopes rather than restricts."""
    relationships: tuple[Reference, ...] = ()
    """Typed edges to other Knowledge Entries (and referenced objects), forming the operational graph."""
    artifact_refs: tuple[Reference, ...] = ()
    """References (by id) to Artifacts concerned; references, never duplicated content (INV-27)."""
    observation_refs: tuple[Reference, ...] = ()
    """References (by id) to Supervision Observations that informed the understanding."""
    source: KnowledgeSource | None = None
    """Provenance of the understanding (Execution / Reflection / Validation / …)."""
    candidate_ref: Reference | None = None
    """Reference (by id) to the originating Knowledge Candidate, preserving candidate→entry provenance."""
    superseded_by: Reference | None = None
    """Reference (by id) to the Knowledge Entry that replaced this one when freshness is Superseded."""
    rationale: str | None = None
    """Explanation of why this understanding is held and how the evidence supports it."""
    applicability: Struct | None = None
    """Conditions under which the understanding is relevant (helps retrieval)."""
    metadata: Struct | None = None
    """Non-behavioral descriptive attributes (tags, ownership notes) that do not affect understanding."""
