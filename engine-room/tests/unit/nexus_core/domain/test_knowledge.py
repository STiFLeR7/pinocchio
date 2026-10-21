"""Unit tests for the immutable ``Knowledge`` domain model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import (
    ConfidenceLadder,
    Domain,
    Freshness,
    KnowledgeCategory,
    KnowledgeType,
)
from nexus_core.contracts.status import KnowledgeIngestionStatus
from nexus_core.domain.knowledge import Knowledge
from nexus_core.state.transitions import MACHINES


def _valid_knowledge() -> Knowledge:
    return Knowledge(
        identity="kn-1",
        correlation_identifier="corr-1",
        type=KnowledgeType.LESSON,
        understanding="Retrying flaky network calls with backoff reduces failures.",
        evidence_refs=(Reference(target_type="evidence", identifier="evd-1"),),
        confidence=ConfidenceLadder.OBSERVED,
        freshness=Freshness.CURRENT,
    )


def test_construction() -> None:
    kn = _valid_knowledge()
    assert kn.type is KnowledgeType.LESSON
    assert kn.evidence_refs[0].identifier == "evd-1"
    assert kn.status is None
    assert kn.relationships == ()


def test_construction_with_optionals() -> None:
    kn = Knowledge(
        identity="kn-2",
        correlation_identifier="corr-1",
        type=KnowledgeType.PATTERN,
        understanding="Parallel fan-out scales linearly here.",
        evidence_refs=(Reference(target_type="evidence", identifier="evd-1"),),
        confidence=ConfidenceLadder.VALIDATED,
        freshness=Freshness.CURRENT,
        status=KnowledgeIngestionStatus.ACCEPTED,
        category=KnowledgeCategory.OPERATIONAL,
        domain=Domain.SOFTWARE,
    )
    assert kn.status is KnowledgeIngestionStatus.ACCEPTED
    assert kn.domain is Domain.SOFTWARE


def test_immutable() -> None:
    kn = _valid_knowledge()
    with pytest.raises(ValidationError):
        kn.understanding = "changed"  # type: ignore[misc]


def test_missing_required_raises() -> None:
    with pytest.raises(ValidationError):
        Knowledge(  # type: ignore[call-arg]
            identity="kn-1",
            correlation_identifier="corr-1",
            type=KnowledgeType.LESSON,
            understanding="incomplete",
            evidence_refs=(Reference(target_type="evidence", identifier="evd-1"),),
        )


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        Knowledge(  # type: ignore[call-arg]
            identity="kn-1",
            correlation_identifier="corr-1",
            type=KnowledgeType.LESSON,
            understanding="x",
            evidence_refs=(Reference(target_type="evidence", identifier="evd-1"),),
            confidence=ConfidenceLadder.OBSERVED,
            freshness=Freshness.CURRENT,
            unexpected="nope",
        )


def test_evidence_refs_rejects_empty() -> None:
    with pytest.raises(ValidationError):
        Knowledge(
            identity="kn-1",
            correlation_identifier="corr-1",
            type=KnowledgeType.LESSON,
            understanding="x",
            evidence_refs=(),
            confidence=ConfidenceLadder.OBSERVED,
            freshness=Freshness.CURRENT,
        )


def test_serialization_round_trip() -> None:
    kn = _valid_knowledge()
    assert Knowledge.model_validate(kn.model_dump()) == kn


def test_lifecycle_name() -> None:
    assert Knowledge.LIFECYCLE_NAME == "knowledge"
    assert Knowledge.LIFECYCLE_NAME in MACHINES
