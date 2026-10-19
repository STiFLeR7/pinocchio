"""Unit tests for the Evolution Engine -- versioning, accumulation, supersession (doc 10)."""

from __future__ import annotations

from nexus_core.contracts.enums import ConfidenceLadder
from nexus_knowledge.acceptance import AcceptanceDecision
from nexus_knowledge.evolution import EvolutionEngine
from nexus_knowledge.vocabulary import KnowledgeDecision
from tests.unit.nexus_knowledge.helpers import candidate, ref

EVOLVE = EvolutionEngine()
TS = "1970-01-01T00:00:00+00:00"
KEY = "ki-lesson-retry-storm"


def _decision(outcome, *, evidence=(), confidence_to=ConfidenceLadder.OBSERVED, to_version=1):  # type: ignore[no-untyped-def]
    return AcceptanceDecision(
        outcome=outcome,
        subject_key=KEY,
        candidate_id="kc-0001",
        policy_version="persistence-policy/1",
        rationale=("provenance: ok", "eligibility: ok"),
        confidence_to=confidence_to,
        evidence_added=tuple(ref("validation_report", e) for e in evidence),
        to_version=to_version,
    )


def test_create_version_carries_full_provenance() -> None:
    cand = candidate()
    version = EVOLVE.create_version(cand, _decision(KnowledgeDecision.ACCEPT_CREATE), TS)
    assert version.version == 1
    assert version.statement == cand.statement
    # provenance names the candidate, the source pattern, the reflection, and the evidence.
    idents = {r.identifier for r in version.provenance_added}
    assert {"kc-0001", "pat-op-1", "rr-op-1", "ev-0001"} <= idents


def test_create_version_without_pattern_or_reflection_refs() -> None:
    cand = candidate(pattern=None, reflection=None)
    version = EVOLVE.create_version(cand, _decision(KnowledgeDecision.ACCEPT_CREATE), TS)
    assert version.provenance_added[0].identifier == "kc-0001"


def test_evolve_advances_statement_and_accumulates_evidence() -> None:
    prior = EVOLVE.create_version(candidate(), _decision(KnowledgeDecision.ACCEPT_CREATE), TS)
    cand = candidate(statement="prefer jittered backoff", evidence=("ev-0002",))
    decision = _decision(KnowledgeDecision.ACCEPT_EVOLVE, evidence=("ev-0002",), to_version=2)
    nxt = EVOLVE.next_version(prior, cand, decision, TS)
    assert nxt.version == 2
    assert nxt.statement == "prefer jittered backoff"
    assert {r.identifier for r in nxt.evidence_refs} == {"ev-0001", "ev-0002"}


def test_merge_keeps_statement_but_grows_evidence() -> None:
    prior = EVOLVE.create_version(candidate(), _decision(KnowledgeDecision.ACCEPT_CREATE), TS)
    cand = candidate(statement="ignored on merge", evidence=("ev-0002",))
    decision = _decision(KnowledgeDecision.MERGE, evidence=("ev-0002",), to_version=2)
    nxt = EVOLVE.next_version(prior, cand, decision, TS)
    assert nxt.statement == prior.statement
    assert len(nxt.evidence_refs) == 2


def test_accumulate_deduplicates_by_reference_id() -> None:
    prior = EVOLVE.create_version(candidate(), _decision(KnowledgeDecision.ACCEPT_CREATE), TS)
    # re-adding ev-0001 must not duplicate.
    decision = _decision(KnowledgeDecision.MERGE, evidence=("ev-0001",), to_version=2)
    nxt = EVOLVE.next_version(prior, candidate(), decision, TS)
    assert len(nxt.evidence_refs) == 1


def test_supersede_version_records_the_replaced_subject() -> None:
    prior = EVOLVE.create_version(candidate(), _decision(KnowledgeDecision.ACCEPT_CREATE), TS)
    old = ref("knowledge", "ki-lesson-old-lesson")
    nxt = EVOLVE.supersede_version(prior, old, TS)
    assert nxt.supersedes == old
    assert "supersedes" in nxt.rationale
