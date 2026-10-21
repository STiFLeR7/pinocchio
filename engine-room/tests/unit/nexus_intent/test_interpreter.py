"""Understanding correctness — Intent Resolution infers what the operator wants (not how)."""

from __future__ import annotations

import pytest

from nexus_core.contracts.enums import Domain, InterpretationConfidence, Priority
from nexus_intent import DeterministicInterpreter
from tests.unit.nexus_intent.fixtures import interpret, req


def test_objective_strips_imperative_prefix() -> None:
    a = interpret("please fix the login bug in the auth module")
    assert a.intent.detected_intent == "fix the login bug in the auth module"


@pytest.mark.parametrize(
    "text,domain",
    [
        ("fix the failing code in the module", Domain.SOFTWARE),
        ("research and compare vector databases", Domain.RESEARCH),
        ("write documentation for the onboarding flow", Domain.WRITING),
    ],
)
def test_domain_detection(text, domain) -> None:
    assert interpret(text).intent.detected_domain == domain


def test_clear_request_resolves_to_a_goal() -> None:
    a = interpret("fix the failing authentication bug in the auth module")
    assert a.resolved is True
    assert a.goal is not None
    assert a.goal.outcome == "fix the failing authentication bug in the auth module"
    assert a.confidence.level == InterpretationConfidence.HIGH
    assert not a.clarifications


def test_vague_request_emits_clarifications_and_no_goal() -> None:
    a = interpret("do something")
    assert a.resolved is False
    assert a.goal is None  # clarification preferred over incorrect execution
    assert a.interaction_required is True
    assert a.confidence.level == InterpretationConfidence.LOW
    assert {c.kind.value for c in a.clarifications} <= {"ambiguity", "missing_information"}


def test_constraint_extraction() -> None:
    a = interpret("fix the auth bug but do not touch the billing api")
    kinds = {c.kind for c in a.goal.constraints}
    assert "prohibition" in kinds


def test_preference_extraction() -> None:
    a = interpret("do a thorough and careful refactor of the auth module")
    assert set(a.operator_preferences) >= {"thorough", "careful"}


def test_priority_extraction() -> None:
    assert (
        interpret("urgent: fix the crashing auth module now").intent.priority_estimate
        == Priority.CRITICAL
    )
    assert interpret("fix the auth module whenever you can").intent.priority_estimate in (
        Priority.LOW,
        Priority.BACKGROUND,
    )


def test_missing_information_detected_for_bare_request() -> None:
    a = interpret("help")
    assert a.intent.missing_information
    assert a.resolved is False


def test_confidence_carries_explainable_factors() -> None:
    a = interpret("fix the failing auth bug in the module")
    assert 0.0 <= a.confidence.score <= 1.0
    assert a.confidence.factors


def test_provided_priority_overrides_detection() -> None:
    a = DeterministicInterpreter().interpret(
        req("rp", "fix the auth bug in the module", provided_priority="low"), now="t"
    )
    assert a.intent.priority_estimate == Priority.LOW
