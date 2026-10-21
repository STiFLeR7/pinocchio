"""Unit tests for the immutable ``Reflection`` domain model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import ConfidenceLadder, ReflectionCategory
from nexus_core.contracts.status import ReflectionStatus
from nexus_core.domain.reflection import Reflection
from nexus_core.state.transitions import MACHINES


def _valid_reflection() -> Reflection:
    return Reflection(
        identity="ref-1",
        correlation_identifier="corr-1",
        category=ReflectionCategory.SUCCESS,
        inputs=(Reference(target_type="artifact", identifier="art-1"),),
        findings="The chosen strategy completed under budget because of early caching.",
        confidence=ConfidenceLadder.OBSERVED,
    )


def test_construction() -> None:
    ref = _valid_reflection()
    assert ref.category is ReflectionCategory.SUCCESS
    assert ref.inputs[0].identifier == "art-1"
    assert ref.status is None
    assert ref.lessons == ()


def test_construction_with_optionals() -> None:
    ref = Reflection(
        identity="ref-2",
        correlation_identifier="corr-1",
        category=ReflectionCategory.FAILURE,
        inputs=(Reference(target_type="event", identifier="ev-1"),),
        findings="Timeout cascaded from an unbounded retry loop.",
        confidence=ConfidenceLadder.VALIDATED,
        status=ReflectionStatus.CANDIDATES_PROPOSED,
        lessons=("bound retries",),
    )
    assert ref.status is ReflectionStatus.CANDIDATES_PROPOSED
    assert ref.lessons == ("bound retries",)


def test_immutable() -> None:
    ref = _valid_reflection()
    with pytest.raises(ValidationError):
        ref.findings = "changed"  # type: ignore[misc]


def test_missing_required_raises() -> None:
    with pytest.raises(ValidationError):
        Reflection(  # type: ignore[call-arg]
            identity="ref-1",
            correlation_identifier="corr-1",
            category=ReflectionCategory.SUCCESS,
            inputs=(Reference(target_type="artifact", identifier="art-1"),),
            findings="incomplete",
        )


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        Reflection(  # type: ignore[call-arg]
            identity="ref-1",
            correlation_identifier="corr-1",
            category=ReflectionCategory.SUCCESS,
            inputs=(Reference(target_type="artifact", identifier="art-1"),),
            findings="x",
            confidence=ConfidenceLadder.OBSERVED,
            unexpected="nope",
        )


def test_serialization_round_trip() -> None:
    ref = _valid_reflection()
    assert Reflection.model_validate(ref.model_dump()) == ref


def test_lifecycle_name() -> None:
    assert Reflection.LIFECYCLE_NAME == "reflection"
    assert Reflection.LIFECYCLE_NAME in MACHINES
