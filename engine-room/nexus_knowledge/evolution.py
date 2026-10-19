"""The Evolution Engine -- how durable Knowledge improves without losing provenance (doc 10).

Evolution is always **additive and auditable, never destructive**: every accepted change produces
a new immutable :class:`~nexus_knowledge.model.KnowledgeVersion`. Evidence accumulates
(deduplicated by reference id, INV-16; reference-only, INV-27); confidence advances
deterministically along the earned ladder as corroboration grows; and provenance *only grows* --
each version records the candidate, pattern, reflection, and evidence refs added, so the chain is
the unbroken audit of how the understanding was learned (INV-24).

- **Evolve** appends a new version whose *statement advances*.
- **Merge** appends a new version whose *statement is unchanged* but evidence/confidence grow.
- **Supersede** links two *different* Subject Keys where one replaces the other (doc 10).

There is no clock and no randomness here: the same candidate sequence yields the same version
chain, confidence trajectory, and supersession graph.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_knowledge.acceptance import AcceptanceDecision
from nexus_knowledge.candidate import KnowledgeCandidate
from nexus_knowledge.model import KnowledgeVersion
from nexus_knowledge.vocabulary import KnowledgeDecision


class EvolutionEngine:
    """Builds immutable version records for create / evolve / merge and supersession (doc 10)."""

    def create_version(
        self, candidate: KnowledgeCandidate, decision: AcceptanceDecision, timestamp: str
    ) -> KnowledgeVersion:
        """The first version of a newly created Item (Accepted)."""
        confidence = decision.confidence_to or candidate.confidence
        return KnowledgeVersion(
            subject_key=decision.subject_key,
            version=1,
            kind=candidate.kind,
            subject=candidate.subject,
            statement=candidate.statement,
            confidence=confidence,
            evidence_refs=candidate.evidence_refs,
            source_goal_ref=candidate.source_goal_ref,
            source_run_refs=candidate.source_run_refs,
            validation_report_refs=candidate.validation_report_refs,
            feedback_refs=candidate.feedback_refs,
            domain=candidate.domain,
            applicability=candidate.applicability,
            provenance_added=self._provenance(candidate, candidate.evidence_refs),
            candidate_ref=candidate.reference(),
            policy_version=decision.policy_version,
            rationale=self._rationale(decision),
            correlation_identifier=candidate.correlation_identifier,
            timestamp=timestamp,
        )

    def next_version(
        self,
        prior: KnowledgeVersion,
        candidate: KnowledgeCandidate,
        decision: AcceptanceDecision,
        timestamp: str,
    ) -> KnowledgeVersion:
        """The next version for an evolve or merge (statement advances on evolve only)."""
        evolves = decision.outcome is KnowledgeDecision.ACCEPT_EVOLVE
        statement = candidate.statement if evolves else prior.statement
        evidence = self._accumulate(prior.evidence_refs, decision.evidence_added)
        confidence = decision.confidence_to or prior.confidence
        return KnowledgeVersion(
            subject_key=prior.subject_key,
            version=prior.version + 1,
            kind=prior.kind,
            subject=prior.subject,
            statement=statement,
            confidence=confidence,
            evidence_refs=evidence,
            source_goal_ref=candidate.source_goal_ref or prior.source_goal_ref,
            source_run_refs=self._unique((*prior.source_run_refs, *candidate.source_run_refs)),
            validation_report_refs=self._unique(
                (*prior.validation_report_refs, *candidate.validation_report_refs)
            ),
            feedback_refs=self._unique((*prior.feedback_refs, *candidate.feedback_refs)),
            domain=candidate.domain or prior.domain,
            applicability=candidate.applicability or prior.applicability,
            provenance_added=self._provenance(candidate, decision.evidence_added),
            candidate_ref=candidate.reference(),
            policy_version=decision.policy_version,
            rationale=self._rationale(decision),
            correlation_identifier=candidate.correlation_identifier or prior.correlation_identifier,
            timestamp=timestamp,
        )

    def supersede_version(
        self, prior: KnowledgeVersion, superseded: Reference, timestamp: str
    ) -> KnowledgeVersion:
        """A version that records this Item now supersedes another Subject Key (doc 10)."""
        return KnowledgeVersion(
            subject_key=prior.subject_key,
            version=prior.version + 1,
            kind=prior.kind,
            subject=prior.subject,
            statement=prior.statement,
            confidence=prior.confidence,
            evidence_refs=prior.evidence_refs,
            source_goal_ref=prior.source_goal_ref,
            source_run_refs=prior.source_run_refs,
            validation_report_refs=prior.validation_report_refs,
            feedback_refs=prior.feedback_refs,
            domain=prior.domain,
            applicability=prior.applicability,
            provenance_added=(superseded,),
            candidate_ref=prior.candidate_ref,
            supersedes=superseded,
            policy_version=prior.policy_version,
            rationale=f"supersedes {superseded.identifier}",
            correlation_identifier=prior.correlation_identifier,
            timestamp=timestamp,
        )

    # -- helpers ------------------------------------------------------------- #

    def _accumulate(
        self, existing: tuple[Reference, ...], added: tuple[Reference, ...]
    ) -> tuple[Reference, ...]:
        """Additive, id-deduplicated evidence accumulation (INV-16/INV-27)."""
        seen = {ref.identifier for ref in existing}
        merged = list(existing)
        for ref in added:
            if ref.identifier not in seen:
                seen.add(ref.identifier)
                merged.append(ref)
        return tuple(merged)

    def _provenance(
        self, candidate: KnowledgeCandidate, evidence: tuple[Reference, ...]
    ) -> tuple[Reference, ...]:
        """The provenance refs a version adds: candidate, pattern, reflection, and new evidence."""
        refs: list[Reference] = [candidate.reference()]
        if candidate.source_pattern_ref is not None:
            refs.append(candidate.source_pattern_ref)
        if candidate.originating_reflection_ref is not None:
            refs.append(candidate.originating_reflection_ref)
        refs.extend(evidence)
        return tuple(refs)

    def _rationale(self, decision: AcceptanceDecision) -> str:
        return " | ".join(decision.rationale)

    def _unique(self, refs: tuple[Reference, ...]) -> tuple[Reference, ...]:
        seen: set[tuple[str, str]] = set()
        result: list[Reference] = []
        for ref in refs:
            key = (ref.target_type, ref.identifier)
            if key not in seen:
                seen.add(key)
                result.append(ref)
        return tuple(result)
