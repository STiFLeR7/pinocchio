"""Knowledge model -- the immutable Version record and the Item projection (doc 03/10).

The durable **Knowledge Item is the frozen core contract**
:class:`nexus_core.domain.Knowledge` (doc 03 -- "without inventing a competing model"): its
``identity`` is the deterministic Subject Key, and it is the *projection of the latest version*.
Because the core contract carries no version ordinal, the **version chain** -- the auditable
history of how understanding evolved -- is a Knowledge-layer value object,
:class:`KnowledgeVersion`. Each accepted change appends one immutable version; the current Item
is folded from the newest.

Nothing here is ever mutated in place: evolution, supersession, and expiration each produce a new
version and/or a new projected Item (ADR-001). Every reference is by id (INV-27); provenance only
grows across versions (INV-24).
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, Struct, ValueObject
from nexus_core.contracts.enums import (
    ConfidenceLadder,
    Domain,
    Freshness,
    KnowledgeSource,
    KnowledgeType,
)
from nexus_core.contracts.status import KnowledgeIngestionStatus
from nexus_core.domain.knowledge import Knowledge
from nexus_knowledge import ids
from nexus_knowledge.vocabulary import KNOWLEDGE_VERSION_TARGET_TYPE


class KnowledgeVersion(ValueObject):
    """One immutable version record in a Subject Key's audit chain (doc 03/10)."""

    subject_key: str
    version: int
    kind: KnowledgeType
    subject: str
    statement: str
    confidence: ConfidenceLadder
    evidence_refs: tuple[Reference, ...] = ()
    domain: Domain | None = None
    applicability: Struct | None = None
    source_goal_ref: Reference | None = None
    source_run_refs: tuple[Reference, ...] = ()
    validation_report_refs: tuple[Reference, ...] = ()
    feedback_refs: tuple[Reference, ...] = ()
    provenance_added: tuple[Reference, ...] = ()
    candidate_ref: Reference | None = None
    supersedes: Reference | None = None
    policy_version: str = ""
    rationale: str = ""
    correlation_identifier: str = ""
    timestamp: str = ""

    @property
    def identity(self) -> str:
        """The deterministic version id ``(subject_key, ordinal)``."""
        return ids.version_id(self.subject_key, self.version)

    def reference(self) -> Reference:
        """A typed by-id pointer to this version record."""
        return Reference(target_type=KNOWLEDGE_VERSION_TARGET_TYPE, identifier=self.identity)


def build_item(
    version: KnowledgeVersion,
    *,
    status: KnowledgeIngestionStatus,
    freshness: Freshness,
    superseded_by: Reference | None = None,
    related_refs: tuple[Reference, ...] = (),
) -> Knowledge:
    """Project the current core Knowledge Item from the latest version + lifecycle facts.

    The Item carries the validated evidence and originating candidate (INV-24 grounding, INV-25
    provenance); the *full* provenance ledger (patterns, reflection reports, every prior evidence
    ref) lives in the version chain. ``evidence_refs`` is guaranteed non-empty because acceptance
    requires ``minimum_evidence >= 1`` (doc 04), satisfying the contract's ``min_length=1``.
    """
    return Knowledge(
        identity=version.subject_key,
        correlation_identifier=version.correlation_identifier or version.subject_key,
        type=version.kind,
        understanding=version.statement,
        evidence_refs=version.evidence_refs,
        confidence=version.confidence,
        freshness=freshness,
        status=status,
        relationships=related_refs,
        source=KnowledgeSource.REFLECTION,
        candidate_ref=version.candidate_ref,
        superseded_by=superseded_by,
        rationale=version.rationale,
        domain=version.domain,
        applicability=version.applicability,
        metadata={
            "source_goal_ref": version.source_goal_ref.model_dump(mode="json")
            if version.source_goal_ref
            else None,
            "source_run_refs": [ref.model_dump(mode="json") for ref in version.source_run_refs],
            "validation_report_refs": [
                ref.model_dump(mode="json") for ref in version.validation_report_refs
            ],
            "feedback_refs": [ref.model_dump(mode="json") for ref in version.feedback_refs],
        },
    )
