"""Unit tests for the small, pure Knowledge modules: ids, policy, model, lifecycle."""

from __future__ import annotations

from nexus_core.contracts.enums import (
    ConfidenceLadder,
    Freshness,
    KnowledgeType,
)
from nexus_core.contracts.status import KnowledgeIngestionStatus
from nexus_knowledge import ids
from nexus_knowledge.lifecycle import (
    freshness_for,
    is_served,
    is_stale,
    lifecycle_of,
    status_for,
)
from nexus_knowledge.model import KnowledgeVersion, build_item
from nexus_knowledge.policy import (
    DEFAULT_PERSISTENCE_POLICY,
    PersistencePolicy,
    at_least,
    confidence_for,
    ladder_index,
)
from nexus_knowledge.vocabulary import KnowledgeLifecycle
from tests.unit.nexus_knowledge.helpers import ref

# --- ids -------------------------------------------------------------------- #


def test_subject_key_is_deterministic_and_order_independent() -> None:
    a = ids.subject_key(KnowledgeType.LESSON, "Retry Storm")
    b = ids.subject_key(KnowledgeType.LESSON, "storm   retry")
    assert a == b == "ki-lesson-retry-storm"


def test_normalize_subject_handles_symbol_only_subject() -> None:
    assert ids.normalize_subject("***") == "unspecified"
    assert ids.subject_key(KnowledgeType.PATTERN, "   ") == "ki-pattern-unspecified"


def test_version_and_event_ids_are_stable() -> None:
    key = ids.subject_key(KnowledgeType.LESSON, "retry storm")
    assert ids.version_id(key, 2) == f"{key}-v0002"
    assert ids.event_id(key, "created", 3) == f"evt-{key}-know-created-0003"


# --- policy ----------------------------------------------------------------- #


def test_ladder_index_and_at_least() -> None:
    assert ladder_index(ConfidenceLadder.EXPERIMENTAL) == 0
    assert ladder_index(ConfidenceLadder.PROVEN) == 3
    assert at_least(ConfidenceLadder.VALIDATED, ConfidenceLadder.OBSERVED)
    assert not at_least(ConfidenceLadder.OBSERVED, ConfidenceLadder.PROVEN)


def test_confidence_for_ladder_thresholds() -> None:
    assert confidence_for(1) is ConfidenceLadder.EXPERIMENTAL
    assert confidence_for(2) is ConfidenceLadder.OBSERVED
    assert confidence_for(4) is ConfidenceLadder.VALIDATED
    assert confidence_for(5) is ConfidenceLadder.PROVEN


def test_promoted_confidence_respects_toggle_and_only_rises() -> None:
    policy = DEFAULT_PERSISTENCE_POLICY
    # 5 pieces of evidence -> proven, above an asserted Observed.
    assert policy.promoted_confidence(ConfidenceLadder.OBSERVED, 5) is ConfidenceLadder.PROVEN
    # count-derived weaker than asserted -> keep asserted (never downgrade).
    assert policy.promoted_confidence(ConfidenceLadder.PROVEN, 1) is ConfidenceLadder.PROVEN
    frozen = PersistencePolicy(confidence_promotion=False)
    assert frozen.promoted_confidence(ConfidenceLadder.OBSERVED, 5) is ConfidenceLadder.OBSERVED


def test_kind_accepted() -> None:
    policy = PersistencePolicy(accepted_kinds=(KnowledgeType.LESSON,))
    assert policy.kind_accepted(KnowledgeType.LESSON)
    assert not policy.kind_accepted(KnowledgeType.STRATEGY)


# --- model ------------------------------------------------------------------ #


def _version(**over: object) -> KnowledgeVersion:
    base: dict[str, object] = {
        "subject_key": "ki-lesson-retry-storm",
        "version": 1,
        "kind": KnowledgeType.LESSON,
        "subject": "retry storm",
        "statement": "prefer backoff",
        "confidence": ConfidenceLadder.OBSERVED,
        "evidence_refs": (ref("validation_report", "ev-1"),),
        "candidate_ref": ref("knowledge_candidate", "kc-1"),
        "correlation_identifier": "cor-k",
        "timestamp": "1970-01-01T00:00:00+00:00",
    }
    base.update(over)
    return KnowledgeVersion(**base)  # type: ignore[arg-type]


def test_version_identity_and_reference() -> None:
    v = _version(version=3)
    assert v.identity == "ki-lesson-retry-storm-v0003"
    assert v.reference().target_type == "knowledge_version"


def test_build_item_projects_core_knowledge_contract() -> None:
    item = build_item(
        _version(),
        status=KnowledgeIngestionStatus.ACCEPTED,
        freshness=Freshness.CURRENT,
    )
    assert item.identity == "ki-lesson-retry-storm"
    assert item.type is KnowledgeType.LESSON
    assert item.understanding == "prefer backoff"
    assert item.evidence_refs  # min_length=1 satisfied
    assert item.freshness is Freshness.CURRENT
    assert item.status is KnowledgeIngestionStatus.ACCEPTED


# --- lifecycle -------------------------------------------------------------- #


def test_freshness_and_status_projection() -> None:
    assert freshness_for(KnowledgeLifecycle.ACTIVE) is Freshness.CURRENT
    assert freshness_for(KnowledgeLifecycle.SUPERSEDED) is Freshness.SUPERSEDED
    assert freshness_for(KnowledgeLifecycle.DEPRECATED) is Freshness.DEPRECATED
    assert freshness_for(KnowledgeLifecycle.EXPIRED) is Freshness.HISTORICAL
    assert freshness_for(KnowledgeLifecycle.ARCHIVED) is Freshness.ARCHIVED
    assert status_for(KnowledgeLifecycle.REJECTED) is KnowledgeIngestionStatus.REJECTED
    assert status_for(KnowledgeLifecycle.ACTIVE) is KnowledgeIngestionStatus.ACCEPTED


def _item(
    freshness: Freshness, *, status: KnowledgeIngestionStatus, confidence=ConfidenceLadder.OBSERVED
):  # type: ignore[no-untyped-def]
    return build_item(_version(confidence=confidence), status=status, freshness=freshness)


def test_lifecycle_of_recovers_every_state() -> None:
    assert lifecycle_of(_item(Freshness.CURRENT, status=KnowledgeIngestionStatus.ACCEPTED)) is (
        KnowledgeLifecycle.ACTIVE
    )
    assert lifecycle_of(_item(Freshness.SUPERSEDED, status=KnowledgeIngestionStatus.ACCEPTED)) is (
        KnowledgeLifecycle.SUPERSEDED
    )
    assert lifecycle_of(_item(Freshness.DEPRECATED, status=KnowledgeIngestionStatus.ACCEPTED)) is (
        KnowledgeLifecycle.DEPRECATED
    )
    assert lifecycle_of(_item(Freshness.HISTORICAL, status=KnowledgeIngestionStatus.ACCEPTED)) is (
        KnowledgeLifecycle.EXPIRED
    )
    assert lifecycle_of(_item(Freshness.ARCHIVED, status=KnowledgeIngestionStatus.ACCEPTED)) is (
        KnowledgeLifecycle.ARCHIVED
    )
    assert lifecycle_of(_item(Freshness.CURRENT, status=KnowledgeIngestionStatus.REJECTED)) is (
        KnowledgeLifecycle.REJECTED
    )


def test_is_served_requires_current_and_floor() -> None:
    policy = PersistencePolicy(serving_confidence_floor=ConfidenceLadder.VALIDATED)
    served = _item(
        Freshness.CURRENT,
        status=KnowledgeIngestionStatus.ACCEPTED,
        confidence=ConfidenceLadder.PROVEN,
    )
    below = _item(
        Freshness.CURRENT,
        status=KnowledgeIngestionStatus.ACCEPTED,
        confidence=ConfidenceLadder.OBSERVED,
    )
    retired = _item(
        Freshness.SUPERSEDED,
        status=KnowledgeIngestionStatus.ACCEPTED,
        confidence=ConfidenceLadder.PROVEN,
    )
    assert is_served(served, policy)
    assert not is_served(below, policy)
    assert not is_served(retired, policy)


def test_is_stale_is_deterministic_over_recorded_timestamps() -> None:
    assert is_stale("1970-01-01T00:00:00+00:00", "1970-01-02T00:00:00+00:00", 3600)
    assert not is_stale("1970-01-01T00:00:00+00:00", "1970-01-01T00:00:01+00:00", 3600)
    assert not is_stale("", "1970-01-02T00:00:00+00:00", 3600)
    assert not is_stale("not-a-date", "also-bad", 3600)
