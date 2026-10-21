"""Unit tests for the immutable :class:`WorkPackage` domain model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Constraint, Correlation, Reference
from nexus_core.contracts.enums import Priority
from nexus_core.contracts.status import WorkPackageStatus
from nexus_core.domain.work_package import WorkPackage
from nexus_core.state.transitions import MACHINES


def _build_work_package() -> WorkPackage:
    return WorkPackage(
        identifier="wp-1",
        parent_goal=Reference(target_type="goal", identifier="goal-1"),
        parent_plan=Reference(target_type="plan", identifier="plan-1"),
        priority=Priority.HIGH,
        objective="Publish the release notes document.",
        context=Reference(target_type="context_package", identifier="ctx-1"),
        constraints=(Constraint(kind="approval", detail={"level": "human_review"}),),
        resources=(Reference(target_type="resource", identifier="res-1"),),
        skills=(Reference(target_type="skill", identifier="skill-1"),),
        inputs=(Reference(target_type="artifact", identifier="draft-1"),),
        outputs=({"kind": "document", "name": "release_notes"},),
        evidence={"requires": ["published_url"]},
        completion_criteria={"published": True},
        status=WorkPackageStatus.READY,
        checkpoints=(Reference(target_type="checkpoint", identifier="cp-1"),),
        dependencies=(Reference(target_type="work_package", identifier="wp-0"),),
        execution_strategy_ref=Reference(target_type="execution_strategy", identifier="es-1"),
        correlation=Correlation(correlation_identifier="c1"),
    )


def test_construction() -> None:
    wp = _build_work_package()
    assert wp.identifier == "wp-1"
    assert wp.priority is Priority.HIGH
    assert wp.context == Reference(target_type="context_package", identifier="ctx-1")
    assert wp.outputs == ({"kind": "document", "name": "release_notes"},)
    assert wp.evidence == {"requires": ["published_url"]}
    assert wp.status is WorkPackageStatus.READY
    assert wp.evidence_refs == ()


def test_immutable() -> None:
    wp = _build_work_package()
    with pytest.raises(ValidationError):
        wp.objective = "something else"  # type: ignore[misc]


def test_missing_required_raises() -> None:
    with pytest.raises(ValidationError):
        WorkPackage(
            identifier="wp-1",
            parent_goal=Reference(target_type="goal", identifier="goal-1"),
            parent_plan=Reference(target_type="plan", identifier="plan-1"),
            priority=Priority.HIGH,
            objective="do it",
            context=Reference(target_type="context_package", identifier="ctx-1"),
            constraints=(),
            resources=(),
            skills=(),
            inputs=(),
            outputs=(),
            evidence={},
            # completion_criteria omitted
        )  # type: ignore[call-arg]


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        WorkPackage(
            identifier="wp-1",
            parent_goal=Reference(target_type="goal", identifier="goal-1"),
            parent_plan=Reference(target_type="plan", identifier="plan-1"),
            priority=Priority.HIGH,
            objective="do it",
            context=Reference(target_type="context_package", identifier="ctx-1"),
            constraints=(),
            resources=(),
            skills=(),
            inputs=(),
            outputs=(),
            evidence={},
            completion_criteria={},
            unexpected="nope",  # type: ignore[call-arg]
        )


def test_serialization_round_trip() -> None:
    wp = _build_work_package()
    assert WorkPackage.model_validate(wp.model_dump()) == wp


def test_lifecycle_name() -> None:
    assert WorkPackage.LIFECYCLE_NAME in MACHINES
