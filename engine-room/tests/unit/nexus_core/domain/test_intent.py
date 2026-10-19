"""Unit tests for the immutable :class:`Intent` domain model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Correlation, Reference
from nexus_core.contracts.enums import Domain, InterpretationConfidence, Modality, Priority
from nexus_core.contracts.status import IntentStatus
from nexus_core.domain.intent import Intent
from nexus_core.state.transitions import MACHINES


def _build_intent() -> Intent:
    return Intent(
        identity="intent-1",
        correlation=Correlation(correlation_identifier="c1"),
        raw_request="Ship the release notes for v1.2.0",
        modality=Modality.NATURAL_LANGUAGE,
        detected_intent="Publish v1.2.0 release notes",
        confidence=InterpretationConfidence.HIGH,
        status=IntentStatus.INTERPRETING,
        missing_information=("target audience",),
        detected_domain=Domain.WRITING,
        priority_estimate=Priority.HIGH,
        assumptions=("operator means the public changelog",),
        interpretation_rationale="High confidence on a single clear deliverable.",
        resolved_goal_ref=Reference(target_type="goal", identifier="goal-1"),
    )


def test_construction() -> None:
    intent = _build_intent()
    assert intent.identity == "intent-1"
    assert intent.correlation.correlation_identifier == "c1"
    assert intent.modality is Modality.NATURAL_LANGUAGE
    assert intent.confidence is InterpretationConfidence.HIGH
    assert intent.detected_domain is Domain.WRITING
    assert intent.priority_estimate is Priority.HIGH
    assert intent.resolved_goal_ref == Reference(target_type="goal", identifier="goal-1")
    assert intent.ambiguity == ()


def test_immutable() -> None:
    intent = _build_intent()
    with pytest.raises(ValidationError):
        intent.detected_intent = "something else"  # type: ignore[misc]


def test_missing_required_raises() -> None:
    with pytest.raises(ValidationError):
        Intent(
            identity="intent-1",
            correlation=Correlation(correlation_identifier="c1"),
            raw_request="do it",
            modality=Modality.NATURAL_LANGUAGE,
            detected_intent="do the thing",
            # confidence omitted
        )  # type: ignore[call-arg]


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        Intent(
            identity="intent-1",
            correlation=Correlation(correlation_identifier="c1"),
            raw_request="do it",
            modality=Modality.NATURAL_LANGUAGE,
            detected_intent="do the thing",
            confidence=InterpretationConfidence.LOW,
            unexpected="nope",  # type: ignore[call-arg]
        )


def test_serialization_round_trip() -> None:
    intent = _build_intent()
    assert Intent.model_validate(intent.model_dump()) == intent


def test_lifecycle_name() -> None:
    assert Intent.LIFECYCLE_NAME in MACHINES
