"""Unit tests for the four validation dimensions and report value objects."""

from __future__ import annotations

import pytest

from nexus_core.contracts.base import Constraint, Correlation, Reference
from nexus_core.contracts.enums import (
    CapabilityCategory,
    Domain,
    InterpretationConfidence,
    Priority,
)
from nexus_core.contracts.status import GoalStatus, WorkPackageStatus
from nexus_core.domain.capability import Capability
from nexus_core.domain.event import Event
from nexus_core.domain.goal import Goal, Scope
from nexus_core.domain.work_package import WorkPackage
from nexus_core.validation.errors import (
    InvariantViolation,
    LifecycleViolation,
    RelationshipViolation,
    SchemaViolation,
)
from nexus_core.validation.framework import (
    ValidationIssue,
    ValidationReport,
)
from nexus_core.validation.invariants import InvariantValidator
from nexus_core.validation.lifecycle import LifecycleValidator
from nexus_core.validation.relationships import RelationshipValidator
from nexus_core.validation.schema import SchemaValidator, validate_schema

# --------------------------------------------------------------------------- #
# Builders                                                                     #
# --------------------------------------------------------------------------- #


def _build_goal() -> Goal:
    return Goal(
        identity="goal-1",
        outcome="The release notes are published.",
        domain=Domain.SOFTWARE,
        priority=Priority.HIGH,
        confidence=InterpretationConfidence.HIGH,
        constraints=(Constraint(kind="deadline", detail={"by": "2026-07-01"}),),
        scope=Scope(included=("notes",), excluded=("marketing",)),
        correlation=Correlation(correlation_identifier="corr-1"),
        status=GoalStatus.NORMALIZED,
    )


def _build_work_package(
    parent_goal: Reference | None = None,
) -> WorkPackage:
    return WorkPackage(
        identifier="wp-1",
        parent_goal=parent_goal or Reference(target_type="goal", identifier="goal-1"),
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
    )


def _build_capability() -> Capability:
    return Capability(
        identifier="cap-1",
        name="Repository Analysis",
        version="1.0.0",
        category=CapabilityCategory.ANALYSIS,
        description="Produce a structural analysis of a repository.",
        inputs=({"role": "repository"},),
        outputs=({"role": "analysis"},),
    )


def _build_event() -> Event:
    return Event(
        identifier="evt-1",
        type="goal.created",
        version="1.0.0",
        timestamp="2026-06-29T00:00:00Z",
        producer="intent",
        correlation_identifier="corr-1",
        execution_identifier=None,
        payload={"goal": "goal-1"},
        source="cli",
    )


# --------------------------------------------------------------------------- #
# SchemaValidator                                                             #
# --------------------------------------------------------------------------- #


def test_schema_validator_passes_valid_object() -> None:
    report = SchemaValidator().check(_build_goal())
    assert report.ok is True
    assert report.issues == ()


def test_schema_validator_validates_each_object() -> None:
    for obj in (_build_goal(), _build_work_package(), _build_capability(), _build_event()):
        assert SchemaValidator().check(obj).ok is True


def test_validate_schema_round_trips_to_equal_object() -> None:
    goal = _build_goal()
    rebuilt = validate_schema(Goal, goal.model_dump())
    assert rebuilt == goal


def test_validate_schema_bad_data_raises_schema_violation() -> None:
    with pytest.raises(SchemaViolation) as exc_info:
        validate_schema(Goal, {"identity": "goal-1"})
    assert exc_info.value.object_name == "goal"
    assert "schema validation failed" in exc_info.value.message


# --------------------------------------------------------------------------- #
# InvariantValidator                                                          #
# --------------------------------------------------------------------------- #


def test_invariant_validator_passes_valid_object() -> None:
    assert InvariantValidator().check(_build_work_package()).ok is True
    InvariantValidator().validate(_build_work_package())  # does not raise


def test_invariant_validator_flags_malformed_reference() -> None:
    malformed = _build_work_package(parent_goal=Reference(target_type="", identifier=""))
    validator = InvariantValidator()
    assert validator.check(malformed).ok is False
    with pytest.raises(InvariantViolation) as exc_info:
        validator.validate(malformed)
    assert "malformed reference" in exc_info.value.message


# --------------------------------------------------------------------------- #
# LifecycleValidator                                                          #
# --------------------------------------------------------------------------- #


def test_lifecycle_validator_passes_valid_status() -> None:
    assert LifecycleValidator().check(_build_goal()).ok is True


def test_lifecycle_validator_transition_illegal_raises() -> None:
    with pytest.raises(LifecycleViolation):
        LifecycleValidator().validate_transition("goal", GoalStatus.NORMALIZED, GoalStatus.ACHIEVED)


def test_lifecycle_validator_transition_legal_is_silent() -> None:
    # Does not raise for a legal transition.
    LifecycleValidator().validate_transition(
        "goal", GoalStatus.NORMALIZED, GoalStatus.CONTEXTUALIZING
    )


# --------------------------------------------------------------------------- #
# RelationshipValidator                                                       #
# --------------------------------------------------------------------------- #


def test_relationship_validator_passes_correctly_typed_references() -> None:
    assert RelationshipValidator().check(_build_work_package()).ok is True
    RelationshipValidator().validate(_build_work_package())  # does not raise


def test_relationship_validator_wrong_target_type_raises() -> None:
    wrong = _build_work_package(parent_goal=Reference(target_type="plan", identifier="goal-1"))
    validator = RelationshipValidator()
    assert validator.check(wrong).ok is False
    with pytest.raises(RelationshipViolation) as exc_info:
        validator.validate(wrong)
    assert "must reference 'goal'" in exc_info.value.message


def test_find_dangling_reports_unknown_identifiers() -> None:
    report = RelationshipValidator().find_dangling(_build_work_package(), frozenset())
    assert report.ok is False
    assert any("dangling reference" in issue.message for issue in report.issues)


def test_find_dangling_ok_when_all_ids_known() -> None:
    wp = _build_work_package()
    known = frozenset({"goal-1", "plan-1", "ctx-1", "res-1", "skill-1", "draft-1"})
    report = RelationshipValidator().find_dangling(wp, known)
    assert report.ok is True


# --------------------------------------------------------------------------- #
# Report / issue value objects                                                #
# --------------------------------------------------------------------------- #


def test_validation_report_ok_when_empty() -> None:
    assert ValidationReport().ok is True
    ValidationReport().raise_for_issues()  # does not raise


def test_validation_report_raise_for_issues_raises_first() -> None:
    report = ValidationReport(
        issues=(
            ValidationIssue(category="schema", object_name="goal", message="bad"),
            ValidationIssue(category="schema", object_name="goal", message="worse"),
        )
    )
    assert report.ok is False
    with pytest.raises(Exception) as exc_info:
        report.raise_for_issues()
    assert "bad" in str(exc_info.value)


def test_validation_issue_is_immutable() -> None:
    issue = ValidationIssue(category="schema", object_name="goal", message="bad")
    with pytest.raises(Exception):  # noqa: B017 - pydantic ValidationError on frozen set
        issue.message = "changed"  # type: ignore[misc]
