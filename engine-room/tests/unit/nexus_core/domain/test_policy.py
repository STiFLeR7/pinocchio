"""Unit tests for the immutable ``Policy`` domain model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.enums import ApprovalTaxonomy, PolicyCategory, PolicyDecision
from nexus_core.contracts.status import PolicyStatus
from nexus_core.domain.policy import Policy
from nexus_core.state.transitions import MACHINES


def _valid_policy() -> Policy:
    return Policy(
        identity="pol-1",
        version="v1",
        purpose="Bound runtime cost for high-risk actions.",
        conditions={"all": [{"attribute": "risk_level", "op": "equals", "value": "high"}]},
        decision=PolicyDecision.REQUIRE_APPROVAL,
        priority=10,
        owner="governance",
    )


def test_construction() -> None:
    pol = _valid_policy()
    assert pol.decision is PolicyDecision.REQUIRE_APPROVAL
    assert pol.priority == 10
    assert pol.status is None
    assert pol.dependencies == ()


def test_construction_with_optionals() -> None:
    pol = Policy(
        identity="pol-2",
        version="v1",
        purpose="Allow ungoverned reads.",
        conditions={},
        decision=PolicyDecision.ALLOW,
        priority=1,
        owner="governance",
        status=PolicyStatus.ENABLED,
        approval_requirement=ApprovalTaxonomy.HUMAN_REVIEW,
        category=PolicyCategory.GOVERNANCE,
    )
    assert pol.status is PolicyStatus.ENABLED
    assert pol.category is PolicyCategory.GOVERNANCE


def test_immutable() -> None:
    pol = _valid_policy()
    with pytest.raises(ValidationError):
        pol.priority = 99  # type: ignore[misc]


def test_missing_required_raises() -> None:
    with pytest.raises(ValidationError):
        Policy(  # type: ignore[call-arg]
            identity="pol-1",
            version="v1",
            purpose="incomplete",
            conditions={},
            decision=PolicyDecision.ALLOW,
        )


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        Policy(  # type: ignore[call-arg]
            identity="pol-1",
            version="v1",
            purpose="x",
            conditions={},
            decision=PolicyDecision.ALLOW,
            priority=1,
            owner="governance",
            unexpected="nope",
        )


def test_decision_rejects_recovery_value() -> None:
    with pytest.raises(ValidationError):
        Policy(
            identity="pol-1",
            version="v1",
            purpose="x",
            conditions={},
            decision="retry",
            priority=1,
            owner="governance",
        )


def test_serialization_round_trip() -> None:
    pol = _valid_policy()
    assert Policy.model_validate(pol.model_dump()) == pol


def test_lifecycle_name() -> None:
    assert Policy.LIFECYCLE_NAME == "policy"
    assert Policy.LIFECYCLE_NAME in MACHINES
