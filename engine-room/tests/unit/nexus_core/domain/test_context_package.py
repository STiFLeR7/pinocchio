"""Unit tests for the immutable :class:`ContextPackage` domain model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Constraint, Correlation, Reference
from nexus_core.contracts.enums import InterpretationConfidence
from nexus_core.contracts.status import ContextPackageStatus
from nexus_core.domain.context_package import ContextCategories, ContextPackage
from nexus_core.state.transitions import MACHINES


def _build_context_package() -> ContextPackage:
    return ContextPackage(
        identity="ctx-1",
        goal_ref=Reference(target_type="goal", identifier="goal-1"),
        correlation=Correlation(correlation_identifier="c1"),
        context_categories=ContextCategories(
            goal_context={"outcome": "publish release notes"},
            workspace_context={"repo": "nexus"},
        ),
        constraints=(Constraint(kind="deadline", detail={"by": "2026-07-01"}),),
        resources=(Reference(target_type="resource", identifier="res-1"),),
        confidence=InterpretationConfidence.MEDIUM,
        validation_status={"complete": True},
        status=ContextPackageStatus.READY,
        supporting_artifacts=(Reference(target_type="artifact", identifier="art-1"),),
        references=("https://example.test/spec",),
        known_unknowns=("audience undefined",),
    )


def test_construction() -> None:
    pkg = _build_context_package()
    assert pkg.identity == "ctx-1"
    assert pkg.goal_ref == Reference(target_type="goal", identifier="goal-1")
    assert pkg.context_categories.goal_context == {"outcome": "publish release notes"}
    assert pkg.context_categories.historical_context == {}
    assert pkg.confidence is InterpretationConfidence.MEDIUM
    assert pkg.validation_status == {"complete": True}
    assert pkg.status is ContextPackageStatus.READY
    assert pkg.enrichment_history == ()


def test_immutable() -> None:
    pkg = _build_context_package()
    with pytest.raises(ValidationError):
        pkg.confidence = InterpretationConfidence.LOW  # type: ignore[misc]


def test_missing_required_raises() -> None:
    with pytest.raises(ValidationError):
        ContextPackage(
            identity="ctx-1",
            goal_ref=Reference(target_type="goal", identifier="goal-1"),
            correlation=Correlation(correlation_identifier="c1"),
            context_categories=ContextCategories(),
            constraints=(),
            resources=(),
            confidence=InterpretationConfidence.MEDIUM,
            # validation_status omitted
        )  # type: ignore[call-arg]


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        ContextPackage(
            identity="ctx-1",
            goal_ref=Reference(target_type="goal", identifier="goal-1"),
            correlation=Correlation(correlation_identifier="c1"),
            context_categories=ContextCategories(),
            constraints=(),
            resources=(),
            confidence=InterpretationConfidence.MEDIUM,
            validation_status={},
            unexpected="nope",  # type: ignore[call-arg]
        )


def test_serialization_round_trip() -> None:
    pkg = _build_context_package()
    assert ContextPackage.model_validate(pkg.model_dump()) == pkg


def test_lifecycle_name() -> None:
    assert ContextPackage.LIFECYCLE_NAME in MACHINES
