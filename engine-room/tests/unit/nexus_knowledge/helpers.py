"""Shared, deterministic builders for the Knowledge Engine test suite.

Knowledge ingests advisory Candidates, so the central helper is a candidate factory whose every
field is explicit and deterministic. Evidence references default to a *validated* origin
(``validation_report``) so a candidate clears the default policy's validated-provenance gate; tests
override the origin to exercise rejection paths.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import ConfidenceLadder, KnowledgeType
from nexus_knowledge.candidate import KnowledgeCandidate


def ref(target_type: str, identifier: str) -> Reference:
    """A typed by-id reference."""
    return Reference(target_type=target_type, identifier=identifier)


def candidate(
    identity: str = "kc-0001",
    *,
    kind: KnowledgeType = KnowledgeType.LESSON,
    subject: str = "retry storm",
    statement: str = "prefer exponential backoff on runtime retries",
    confidence: ConfidenceLadder = ConfidenceLadder.OBSERVED,
    evidence: tuple[str, ...] = ("ev-0001",),
    evidence_type: str = "validation_report",
    reflection: str | None = "rr-op-1",
    pattern: str | None = "pat-op-1",
    supersedes_subject: str | None = None,
    correlation: str = "cor-k",
) -> KnowledgeCandidate:
    """A deterministic Knowledge Candidate; defaults clear the default Persistence Policy."""
    return KnowledgeCandidate(
        identity=identity,
        kind=kind,
        subject=subject,
        statement=statement,
        confidence=confidence,
        evidence_refs=tuple(ref(evidence_type, e) for e in evidence),
        originating_reflection_ref=ref("reflection_report", reflection) if reflection else None,
        source_pattern_ref=ref("operational_pattern", pattern) if pattern else None,
        supersedes_subject=supersedes_subject,
        correlation_identifier=correlation,
    )
