"""Unit tests for the Artifact domain model (contract: artifact.md)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import ArtifactStatus, ArtifactType
from nexus_core.domain.artifact import Artifact
from nexus_core.state.transitions import MACHINES


def _valid_artifact() -> Artifact:
    return Artifact(
        identity="art-1",
        type=ArtifactType.SOURCE,
        owner="execution",
        producer="claude-runtime",
        created_time="2026-06-29T00:00:00Z",
        updated_time="2026-06-29T00:00:00Z",
        version="1.0.0",
        status=ArtifactStatus.GENERATED,
        lineage={"goal": "g-1", "plan": "p-1"},
        correlation_identifier="corr-1",
    )


def test_construction() -> None:
    art = _valid_artifact()
    assert art.identity == "art-1"
    assert art.status is ArtifactStatus.GENERATED
    assert art.evidence_ref == ()
    assert art.parent_version is None


def test_construction_with_optionals() -> None:
    art = Artifact(
        identity="art-2",
        type=ArtifactType.DOCUMENTATION,
        owner="knowledge",
        producer="execution",
        created_time="2026-06-29T00:00:00Z",
        updated_time="2026-06-29T01:00:00Z",
        version="2.0.0",
        status=ArtifactStatus.VALIDATED,
        lineage={"goal": "g-1"},
        correlation_identifier="corr-2",
        evidence_ref=(Reference(target_type="evidence", identifier="ev-1"),),
        parent_version=Reference(target_type="artifact", identifier="art-1"),
    )
    assert art.evidence_ref[0].identifier == "ev-1"
    assert art.parent_version is not None
    assert art.parent_version.identifier == "art-1"


def test_status_is_required() -> None:
    with pytest.raises(ValidationError):
        Artifact(  # type: ignore[call-arg]
            identity="art-1",
            type=ArtifactType.SOURCE,
            owner="execution",
            producer="claude-runtime",
            created_time="2026-06-29T00:00:00Z",
            updated_time="2026-06-29T00:00:00Z",
            version="1.0.0",
            lineage={},
            correlation_identifier="corr-1",
            # status missing — REQUIRED for Artifact
        )


def test_immutable() -> None:
    art = _valid_artifact()
    with pytest.raises(ValidationError):
        art.status = ArtifactStatus.PUBLISHED  # type: ignore[misc]


def test_missing_required_raises() -> None:
    with pytest.raises(ValidationError):
        Artifact(  # type: ignore[call-arg]
            identity="art-1",
            type=ArtifactType.SOURCE,
            owner="execution",
            producer="claude-runtime",
            created_time="2026-06-29T00:00:00Z",
            updated_time="2026-06-29T00:00:00Z",
            version="1.0.0",
            status=ArtifactStatus.GENERATED,
            lineage={},
            # correlation_identifier missing
        )


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        Artifact(
            identity="art-1",
            type=ArtifactType.SOURCE,
            owner="execution",
            producer="claude-runtime",
            created_time="2026-06-29T00:00:00Z",
            updated_time="2026-06-29T00:00:00Z",
            version="1.0.0",
            status=ArtifactStatus.GENERATED,
            lineage={},
            correlation_identifier="corr-1",
            health="healthy",  # type: ignore[call-arg]
        )


def test_serialization_round_trip() -> None:
    art = _valid_artifact()
    assert Artifact.model_validate(art.model_dump()) == art


def test_lifecycle_name() -> None:
    assert Artifact.LIFECYCLE_NAME == "artifact"
    assert Artifact.LIFECYCLE_NAME in MACHINES
