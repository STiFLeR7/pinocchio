"""Unit tests for the immutable :class:`Plan` domain model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Correlation, Reference
from nexus_core.contracts.status import PlanStatus
from nexus_core.domain.plan import Milestone, Plan
from nexus_core.state.transitions import MACHINES


def _build_plan() -> Plan:
    return Plan(
        identity="plan-1",
        parent_goal=Reference(target_type="goal", identifier="goal-1"),
        version="1",
        approach_summary="Draft, review, then publish.",
        milestones=(
            Milestone(
                identifier="m1",
                meaning="Draft complete",
                completion_condition="draft document exists",
            ),
        ),
        priorities={"order": ["draft", "review", "publish"]},
        dependency_summary="Review depends on the draft.",
        work_package_refs=(Reference(target_type="work_package", identifier="wp-1"),),
        execution_graph_ref=Reference(target_type="execution_graph", identifier="eg-1"),
        rationale="Linear approach fits a single deliverable.",
        status=PlanStatus.READY,
        assumptions=("reviewer available",),
        supersedes=Reference(target_type="plan", identifier="plan-0"),
        correlation=Correlation(correlation_identifier="c1"),
    )


def test_construction() -> None:
    plan = _build_plan()
    assert plan.identity == "plan-1"
    assert plan.parent_goal == Reference(target_type="goal", identifier="goal-1")
    assert plan.version == "1"
    assert plan.milestones[0].identifier == "m1"
    assert plan.execution_graph_ref == Reference(target_type="execution_graph", identifier="eg-1")
    assert plan.status is PlanStatus.READY
    assert plan.operational_risks == ()


def test_immutable() -> None:
    plan = _build_plan()
    with pytest.raises(ValidationError):
        plan.version = "2"  # type: ignore[misc]


def test_missing_required_raises() -> None:
    with pytest.raises(ValidationError):
        Plan(
            identity="plan-1",
            parent_goal=Reference(target_type="goal", identifier="goal-1"),
            version="1",
            approach_summary="approach",
            milestones=(),
            priorities={},
            dependency_summary="none",
            work_package_refs=(),
            execution_graph_ref=Reference(target_type="execution_graph", identifier="eg-1"),
            # rationale omitted
        )  # type: ignore[call-arg]


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        Plan(
            identity="plan-1",
            parent_goal=Reference(target_type="goal", identifier="goal-1"),
            version="1",
            approach_summary="approach",
            milestones=(),
            priorities={},
            dependency_summary="none",
            work_package_refs=(),
            execution_graph_ref=Reference(target_type="execution_graph", identifier="eg-1"),
            rationale="because",
            unexpected="nope",  # type: ignore[call-arg]
        )


def test_serialization_round_trip() -> None:
    plan = _build_plan()
    assert Plan.model_validate(plan.model_dump()) == plan


def test_lifecycle_name() -> None:
    assert Plan.LIFECYCLE_NAME in MACHINES
