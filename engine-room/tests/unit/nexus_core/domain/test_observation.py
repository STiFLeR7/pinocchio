"""Unit tests for the immutable ``Observation`` domain model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import InterventionRecommendation, OperationalHealth
from nexus_core.contracts.status import ObservationStage
from nexus_core.domain.observation import Observation
from nexus_core.state.transitions import MACHINES


def _valid_observation() -> Observation:
    return Observation(
        identity="obs-1",
        execution_identifier="exec-1",
        correlation_identifier="corr-1",
        timestamp="2026-06-29T00:00:00Z",
        derived_from_events=(Reference(target_type="event", identifier="ev-1"),),
        execution_state="running",
        progress={"completed": 2, "total": 5},
    )


def test_construction() -> None:
    obs = _valid_observation()
    assert obs.identity == "obs-1"
    assert obs.derived_from_events[0].identifier == "ev-1"
    assert obs.stage is None
    assert obs.operational_events == ()


def test_construction_with_optionals() -> None:
    obs = Observation(
        identity="obs-2",
        execution_identifier="exec-1",
        correlation_identifier="corr-1",
        timestamp="2026-06-29T00:00:00Z",
        derived_from_events=(Reference(target_type="event", identifier="ev-1"),),
        execution_state="running",
        progress={},
        stage=ObservationStage.RECORDED,
        health_assessment=OperationalHealth.HEALTHY,
        intervention_recommendation=InterventionRecommendation.CONTINUE,
        rationale="steady progress",
    )
    assert obs.stage is ObservationStage.RECORDED
    assert obs.health_assessment is OperationalHealth.HEALTHY


def test_immutable() -> None:
    obs = _valid_observation()
    with pytest.raises(ValidationError):
        obs.execution_state = "stalled"  # type: ignore[misc]


def test_missing_required_raises() -> None:
    with pytest.raises(ValidationError):
        Observation(  # type: ignore[call-arg]
            identity="obs-1",
            execution_identifier="exec-1",
            correlation_identifier="corr-1",
            timestamp="2026-06-29T00:00:00Z",
            derived_from_events=(Reference(target_type="event", identifier="ev-1"),),
            execution_state="running",
        )


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        Observation(  # type: ignore[call-arg]
            identity="obs-1",
            execution_identifier="exec-1",
            correlation_identifier="corr-1",
            timestamp="2026-06-29T00:00:00Z",
            derived_from_events=(Reference(target_type="event", identifier="ev-1"),),
            execution_state="running",
            progress={},
            unexpected="nope",
        )


def test_derived_from_events_rejects_empty() -> None:
    with pytest.raises(ValidationError):
        Observation(
            identity="obs-1",
            execution_identifier="exec-1",
            correlation_identifier="corr-1",
            timestamp="2026-06-29T00:00:00Z",
            derived_from_events=(),
            execution_state="running",
            progress={},
        )


def test_serialization_round_trip() -> None:
    obs = _valid_observation()
    assert Observation.model_validate(obs.model_dump()) == obs


def test_lifecycle_name() -> None:
    assert Observation.LIFECYCLE_NAME == "observation"
    assert Observation.LIFECYCLE_NAME in MACHINES
