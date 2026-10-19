"""Unit tests for the Capability domain model (contract: capability.md)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.enums import CapabilityCategory
from nexus_core.domain.capability import Capability
from nexus_core.state.transitions import MACHINES


def _valid_capability() -> Capability:
    return Capability(
        identifier="cap-1",
        name="Repository Analysis",
        version="1.0.0",
        category=CapabilityCategory.ANALYSIS,
        description="Produce a structural analysis of a repository.",
        inputs=({"role": "repository"},),
        outputs=({"role": "analysis"},),
    )


def test_construction() -> None:
    cap = _valid_capability()
    assert cap.identifier == "cap-1"
    assert cap.category is CapabilityCategory.ANALYSIS
    assert cap.status is None
    assert cap.dependencies == ()


def test_immutable() -> None:
    cap = _valid_capability()
    with pytest.raises(ValidationError):
        cap.version = "2.0.0"  # type: ignore[misc]


def test_missing_required_raises() -> None:
    with pytest.raises(ValidationError):
        Capability(  # type: ignore[call-arg]
            identifier="cap-1",
            name="Repository Analysis",
            version="1.0.0",
            category=CapabilityCategory.ANALYSIS,
            description="Analyze a repository.",
            inputs=(),
            # outputs missing
        )


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        Capability(
            identifier="cap-1",
            name="Repository Analysis",
            version="1.0.0",
            category=CapabilityCategory.ANALYSIS,
            description="Analyze a repository.",
            inputs=(),
            outputs=(),
            provider="claude",  # type: ignore[call-arg]
        )


def test_serialization_round_trip() -> None:
    cap = _valid_capability()
    assert Capability.model_validate(cap.model_dump()) == cap


def test_lifecycle_name() -> None:
    assert Capability.LIFECYCLE_NAME == "capability"
    assert Capability.LIFECYCLE_NAME in MACHINES


def test_capability_has_no_provider_state() -> None:
    """INV-32: provider, availability, and health live in the Harness Registry, not here."""
    assert "provider" not in Capability.model_fields
    assert "availability" not in Capability.model_fields
    assert "health" not in Capability.model_fields
