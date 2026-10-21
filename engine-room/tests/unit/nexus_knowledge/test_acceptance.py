"""Unit tests for the Acceptance Engine -- the deterministic decision precedence (doc 05)."""

from __future__ import annotations

from nexus_core.contracts.enums import ConfidenceLadder, Freshness, KnowledgeType
from nexus_core.contracts.status import KnowledgeIngestionStatus
from nexus_knowledge.acceptance import AcceptanceEngine, SubjectState
from nexus_knowledge.model import KnowledgeVersion, build_item
from nexus_knowledge.policy import DEFAULT_PERSISTENCE_POLICY, PersistencePolicy
from nexus_knowledge.vocabulary import (
    REASON_BELOW_MINIMUM_CONFIDENCE,
    REASON_DUPLICATE,
    REASON_INSUFFICIENT_EVIDENCE,
    REASON_KIND_NOT_ACCEPTED,
    REASON_PROVENANCE_NOT_VALIDATED,
    REASON_REJECTION_TERMINAL,
    DuplicateStrategy,
    KnowledgeDecision,
)
from tests.unit.nexus_knowledge.helpers import candidate, ref

ENGINE = AcceptanceEngine()
KEY = "ki-lesson-retry-storm"
EMPTY_STATE = SubjectState()


def _state(
    *,
    statement: str = "prefer exponential backoff on runtime retries",
    evidence=("ev-0001",),
    confidence=ConfidenceLadder.OBSERVED,
):  # type: ignore[no-untyped-def]
    version = KnowledgeVersion(
        subject_key=KEY,
        version=1,
        kind=KnowledgeType.LESSON,
        subject="retry storm",
        statement=statement,
        confidence=confidence,
        evidence_refs=tuple(ref("validation_report", e) for e in evidence),
    )
    item = build_item(
        version, status=KnowledgeIngestionStatus.ACCEPTED, freshness=Freshness.CURRENT
    )
    return SubjectState(
        item=item,
        latest_version=version,
        recorded_evidence_ids=frozenset(evidence),
    )


def _decide(cand, state=EMPTY_STATE, policy=DEFAULT_PERSISTENCE_POLICY):  # type: ignore[no-untyped-def]
    return ENGINE.evaluate(cand, state, policy, KEY)


# --- rejection paths (fail-closed) ------------------------------------------ #


def test_terminally_rejected_subject_is_blocked() -> None:
    d = _decide(candidate(), SubjectState(terminally_rejected=True))
    assert d.outcome is KnowledgeDecision.REJECT
    assert d.failed_requirement == REASON_REJECTION_TERMINAL


def test_insufficient_evidence_is_rejected() -> None:
    d = _decide(candidate(evidence=()))
    assert d.failed_requirement == REASON_INSUFFICIENT_EVIDENCE


def test_unvalidated_provenance_is_rejected() -> None:
    d = _decide(candidate(evidence_type="execution_result"))
    assert d.failed_requirement == REASON_PROVENANCE_NOT_VALIDATED


def test_below_minimum_confidence_is_rejected() -> None:
    d = _decide(candidate(confidence=ConfidenceLadder.EXPERIMENTAL))
    assert d.failed_requirement == REASON_BELOW_MINIMUM_CONFIDENCE


def test_kind_not_accepted_is_rejected() -> None:
    policy = PersistencePolicy(accepted_kinds=(KnowledgeType.STRATEGY,))
    d = _decide(candidate(kind=KnowledgeType.LESSON), policy=policy)
    assert d.failed_requirement == REASON_KIND_NOT_ACCEPTED


# --- create / evolve / merge ------------------------------------------------ #


def test_new_subject_is_created() -> None:
    d = _decide(candidate())
    assert d.outcome is KnowledgeDecision.ACCEPT_CREATE
    assert d.to_version == 1
    assert d.rationale  # explainable (INV-31)


def test_stronger_statement_evolves() -> None:
    d = _decide(
        candidate(statement="prefer jittered backoff", evidence=("ev-0002",)),
        _state(),
    )
    assert d.outcome is KnowledgeDecision.ACCEPT_EVOLVE
    assert d.from_version == 1 and d.to_version == 2
    assert d.evidence_added and d.evidence_added[0].identifier == "ev-0002"


def test_corroborating_evidence_merges() -> None:
    d = _decide(candidate(evidence=("ev-0002",)), _state())
    assert d.outcome is KnowledgeDecision.MERGE
    assert d.confidence_to is ConfidenceLadder.OBSERVED  # two evidence -> observed


def test_nothing_new_is_rejected_as_duplicate() -> None:
    d = _decide(candidate(evidence=("ev-0001",)), _state())
    assert d.outcome is KnowledgeDecision.REJECT
    assert d.failed_requirement == REASON_DUPLICATE


def test_reject_as_duplicate_strategy_blocks_any_match() -> None:
    policy = PersistencePolicy(duplicate_strategy=DuplicateStrategy.REJECT_AS_DUPLICATE)
    d = _decide(candidate(statement="new", evidence=("ev-0002",)), _state(), policy)
    assert d.failed_requirement == REASON_DUPLICATE


def test_merge_strategy_forces_merge_even_on_new_statement() -> None:
    policy = PersistencePolicy(duplicate_strategy=DuplicateStrategy.MERGE)
    d = _decide(candidate(statement="different", evidence=("ev-0002",)), _state(), policy)
    assert d.outcome is KnowledgeDecision.MERGE


def test_confidence_promotes_from_stronger_of_asserted_and_current() -> None:
    # current Experimental, candidate Validated, one new evidence (cumulative 2 -> Observed);
    # promoted confidence is the stronger of asserted(Validated) vs derived(Observed) = Validated.
    d = _decide(
        candidate(confidence=ConfidenceLadder.VALIDATED, evidence=("ev-0002",)),
        _state(confidence=ConfidenceLadder.EXPERIMENTAL),
    )
    assert d.confidence_to is ConfidenceLadder.VALIDATED
