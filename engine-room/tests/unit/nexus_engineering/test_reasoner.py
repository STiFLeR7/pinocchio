"""Reasoning correctness — EI genuinely infers each facet from multiple signals (not a lookup)."""

from __future__ import annotations

import pytest

from nexus_core.contracts.enums import Domain, InterpretationConfidence, Priority
from nexus_engineering import DeterministicReasoner, ReasoningInputs
from tests.unit.nexus_engineering.fixtures import make_goal

_R = DeterministicReasoner()


def _reason(goal, **kw):
    return _R.reason(ReasoningInputs(goal=goal, **kw), now="t")


@pytest.mark.parametrize(
    "outcome,expected",
    [
        ("fix the failing bug crashing on login", "bug_fix"),
        ("implement a new export feature for reports", "feature"),
        ("refactor and simplify the tangled billing module", "refactor"),
        ("investigate why latency spiked last week", "investigation"),
        ("migrate the datastore from sqlite to postgres", "migration"),
        ("research and compare vector database options", "research"),
        ("document the authentication flow in the readme", "documentation"),
        ("release and deploy version 2 to production", "release"),
    ],
)
def test_classification_infers_from_outcome_signals(outcome, expected) -> None:
    s = _reason(make_goal(outcome=outcome))
    assert s.classification.selection[0] == expected
    assert s.classification.contributing_evidence  # evidence recorded, not a bare answer


def test_unclassifiable_goal_degrades_to_generic_with_recorded_assumption() -> None:
    s = _reason(make_goal(outcome="handle the thing appropriately"))
    assert s.classification.selection[0] == "generic"
    assert any("no classification signal" in a for a in s.classification.assumptions)


def test_domain_nudges_classification() -> None:
    # A research-domain goal with weak text still classifies toward research.
    s = _reason(make_goal(outcome="look into the options", domain=Domain.RESEARCH))
    assert s.classification.selection[0] == "research"


def test_risk_rises_on_irreversible_signals_and_priority() -> None:
    low = _reason(
        make_goal(
            outcome="tidy the local helper in a branch",
            domain=Domain.SOFTWARE,
            priority=Priority.LOW,
        )
    )
    high = _reason(
        make_goal(outcome="deploy the change to production main", priority=Priority.CRITICAL)
    )
    order = ("low", "medium", "high", "critical")
    assert order.index(high.risk_assessment.selection[0]) > order.index(
        low.risk_assessment.selection[0]
    )


def test_reversibility_signal_lowers_risk() -> None:
    s = _reason(make_goal(outcome="fix the bug in a sandbox branch with a revert available"))
    assert s.risk_assessment.selection[0] in ("low", "medium")


def test_validation_rigor_never_below_risk_floor() -> None:
    s = _reason(make_goal(outcome="deploy release to production main", priority=Priority.CRITICAL))
    assert s.validation_rigor.selection[0] in ("high", "strict")
    # mandatory evidence classes are surfaced (INV-20)
    assert len(s.validation_rigor.selection) > 1


def test_autonomy_is_capped_when_policy_context_absent() -> None:
    # No policy context → fail-closed: autonomy never exceeds gated (INV-30).
    s = _reason(make_goal(outcome="fix the bug in a local branch", priority=Priority.LOW))
    assert s.autonomy_level.selection[0] in ("gated", "manual")
    assert any("fail-closed" in a.lower() for a in s.autonomy_level.assumptions)


def test_runtime_preferences_are_capabilities_not_providers() -> None:
    s = _reason(make_goal())
    caps = s.runtime_preferences.selection
    assert "code-generation" in caps
    assert not any(p in caps for p in ("claude", "gemini", "openai", "nexus"))


def test_runtime_preferences_intersect_available_capabilities() -> None:
    s = _reason(make_goal(), environment_capabilities=("filesystem", "high-context"))
    assert set(s.runtime_preferences.selection) <= {"filesystem", "high-context"}
    assert any("dropped unavailable" in c for c in s.runtime_preferences.reasoning_chain)


def test_complexity_class_is_consumed_from_estimation_not_reinvented(monkeypatch) -> None:
    # Without estimation EI degrades to a conservative default and records the assumption.
    s = _reason(make_goal())
    assert s.complexity_class.selection[0] == "moderate"
    assert any("unavailable" in a for a in s.complexity_class.assumptions)


def test_confidence_is_between_zero_and_one() -> None:
    s = _reason(make_goal(confidence=InterpretationConfidence.HIGH))
    assert 0.0 <= s.confidence <= 1.0
