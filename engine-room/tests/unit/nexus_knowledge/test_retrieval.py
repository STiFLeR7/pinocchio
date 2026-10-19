"""Unit tests for read-only Knowledge retrieval -- Active-by-default, deterministic (doc 09)."""

from __future__ import annotations

from nexus_core.contracts.enums import ConfidenceLadder, Freshness, KnowledgeType
from nexus_core.contracts.status import KnowledgeIngestionStatus
from nexus_knowledge.model import KnowledgeVersion, build_item
from nexus_knowledge.persistence import build_knowledge_repositories
from nexus_knowledge.policy import DEFAULT_PERSISTENCE_POLICY
from nexus_knowledge.retrieval import KnowledgeQuery, KnowledgeRetrieval
from tests.unit.nexus_knowledge.helpers import ref


def _item(
    subject: str,
    *,
    kind=KnowledgeType.LESSON,
    freshness=Freshness.CURRENT,
    confidence=ConfidenceLadder.OBSERVED,
):  # type: ignore[no-untyped-def]
    from nexus_knowledge import ids

    key = ids.subject_key(kind, subject)
    version = KnowledgeVersion(
        subject_key=key,
        version=1,
        kind=kind,
        subject=subject,
        statement=f"about {subject}",
        confidence=confidence,
        evidence_refs=(ref("validation_report", f"ev-{subject}"),),
    )
    return build_item(version, status=KnowledgeIngestionStatus.ACCEPTED, freshness=freshness)


def _retrieval():  # type: ignore[no-untyped-def]
    repos = build_knowledge_repositories()
    repos.items.add(_item("retry storm"))
    repos.items.add(_item("cache miss", confidence=ConfidenceLadder.PROVEN))
    repos.items.add(_item("old lesson", freshness=Freshness.SUPERSEDED))
    repos.items.add(_item("bottleneck", kind=KnowledgeType.PATTERN))
    return KnowledgeRetrieval(repos.items, DEFAULT_PERSISTENCE_POLICY)


def test_active_by_default_excludes_retired() -> None:
    got = _retrieval().resolve(KnowledgeQuery())
    subjects = {i.identity for i in got}
    assert "ki-lesson-old-lesson" not in subjects
    assert len(got) == 3


def test_include_historical_returns_retired_items() -> None:
    got = _retrieval().resolve(KnowledgeQuery(include_historical=True))
    assert len(got) == 4


def test_filter_by_kind() -> None:
    got = _retrieval().resolve(KnowledgeQuery(kind=KnowledgeType.PATTERN))
    assert len(got) == 1 and got[0].type is KnowledgeType.PATTERN


def test_filter_by_subject_key() -> None:
    got = _retrieval().resolve(KnowledgeQuery(subject_key="ki-lesson-cache-miss"))
    assert len(got) == 1 and got[0].identity == "ki-lesson-cache-miss"


def test_filter_by_subject_text_normalises() -> None:
    got = _retrieval().resolve(KnowledgeQuery(kind=KnowledgeType.LESSON, subject="Storm  Retry"))
    assert len(got) == 1 and got[0].identity == "ki-lesson-retry-storm"


def test_filter_by_confidence_floor() -> None:
    got = _retrieval().resolve(KnowledgeQuery(confidence_floor=ConfidenceLadder.PROVEN))
    assert len(got) == 1 and got[0].identity == "ki-lesson-cache-miss"


def test_limit_truncates_deterministically() -> None:
    got = _retrieval().resolve(KnowledgeQuery(limit=1))
    assert len(got) == 1
