"""Knowledge Candidate -- the immutable, advisory boundary contract Knowledge ingests (doc 02).

A :class:`KnowledgeCandidate` is the single input to the ingest pipeline: a *proposed* piece of
understanding together with everything needed to judge it -- its kind and subject (the basis of
the deterministic Subject Key, doc 03), its proposed statement, its confidence, its provenance,
and its supporting evidence **by id** (INV-27). Candidates are **advisory until accepted**
(INV-25): the Engine re-verifies provenance and evidence against policy and never persists a
candidate merely because it exists.

This is a **Knowledge-layer** value object, deliberately *not* imported from the Reflection
package: the candidate crosses the Reflection to Knowledge boundary **by value**, so
``nexus_knowledge`` imports only ``{nexus_core, nexus_infra}`` and no consumer can reach Reflection
through Knowledge (INV-26, structurally; doc 00, the G9 "adapt at the boundary" choice). The
orchestrating caller constructs a candidate from a Reflection Report's advisory outputs; Knowledge
never imports the producer.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, Struct, ValueObject
from nexus_core.contracts.enums import ConfidenceLadder, Domain, KnowledgeType
from nexus_knowledge.vocabulary import KNOWLEDGE_CANDIDATE_TARGET_TYPE


class KnowledgeCandidate(ValueObject):
    """An immutable, evidence-referencing proposal for durable Knowledge (advisory; INV-25)."""

    identity: str
    kind: KnowledgeType
    subject: str
    statement: str
    confidence: ConfidenceLadder
    evidence_refs: tuple[Reference, ...] = ()
    originating_reflection_ref: Reference | None = None
    source_pattern_ref: Reference | None = None
    supersedes_subject: str | None = None
    correlation_identifier: str = ""
    source_goal_ref: Reference | None = None
    source_run_refs: tuple[Reference, ...] = ()
    validation_report_refs: tuple[Reference, ...] = ()
    feedback_refs: tuple[Reference, ...] = ()
    domain: Domain | None = None
    applicability: Struct | None = None

    def reference(self) -> Reference:
        """A typed by-id pointer to this candidate."""
        return Reference(target_type=KNOWLEDGE_CANDIDATE_TARGET_TYPE, identifier=self.identity)
