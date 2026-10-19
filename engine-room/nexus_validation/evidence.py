"""Evidence — Validation's immutable, traceable record of an observed fact.

Evidence is **produced by Validation** (INV-12): Execution emits Evidence *Candidates*
(e.g. ``runtime.artifact_emitted`` events, captured output, metrics); Validation inspects
them and promotes each into an immutable :class:`Evidence` value that is *observable,
repeatable, independent, traceable, and auditable* (doc 14 *Evidence Model*).

Evidence references its source **by id** and never embeds artifact content (INV-12,
ADR-003): an artifact Evidence carries the artifact ``Reference`` and a small,
deterministic descriptor (kind, and — for captured output — a length/first-line summary),
not the payload. ``derived_from`` records provenance (the events / execution result the
fact was read from), so every downstream verdict is traceable to its source.
"""

from __future__ import annotations

from pydantic import Field

from nexus_core.contracts.base import Reference, Struct, ValueObject
from nexus_validation.vocabulary import EVIDENCE_TARGET_TYPE, EvidenceSource


class Evidence(ValueObject):
    """One immutable, traceable observed fact promoted from an Evidence Candidate."""

    identity: str
    source: EvidenceSource
    kind: str
    subject_ref: Reference | None = None
    """The object the Evidence is about (an artifact, a session), by id — never embedded."""
    observed: Struct = Field(default_factory=dict)
    """Deterministic descriptor of the observed fact (e.g. exit_status, length, outcome)."""
    derived_from: tuple[Reference, ...] = ()
    """Provenance: the event/result references this fact was read from (auditability)."""
    correlation_identifier: str = ""

    def reference(self) -> Reference:
        """A typed by-id pointer to this Evidence."""
        return Reference(target_type=EVIDENCE_TARGET_TYPE, identifier=self.identity)
