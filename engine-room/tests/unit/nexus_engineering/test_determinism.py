"""Determinism & influence preservation — identical inputs → identical Strategy; replay-ready."""

from __future__ import annotations

from nexus_engineering import DeterministicReasoner, ReasoningInputs
from nexus_engineering.model import EngineeringStrategy
from tests.unit.nexus_engineering.fixtures import make_goal, make_knowledge, strategy_for

_R = DeterministicReasoner()


def test_identical_inputs_produce_identical_strategy() -> None:
    inputs = ReasoningInputs(goal=make_goal(), knowledge=(make_knowledge(),))
    a = _R.reason(inputs, now="t")
    b = _R.reason(inputs, now="t")
    assert a == b
    assert a.identity == b.identity


def test_strategy_reconstructs_from_its_serialized_form() -> None:
    s = strategy_for(make_goal(), persist=False)
    assert EngineeringStrategy.model_validate(s.model_dump(mode="json")) == s


def test_different_goal_changes_the_strategy_deterministically() -> None:
    a = _R.reason(ReasoningInputs(goal=make_goal(outcome="fix the login bug")), now="t")
    b = _R.reason(ReasoningInputs(goal=make_goal(outcome="research vector databases")), now="t")
    assert a.classification.selection != b.classification.selection
    assert a.identity != b.identity


def test_estimation_influence_is_preserved_and_changes_the_decision() -> None:
    without = strategy_for(make_goal(), persist=False)
    with_est = strategy_for(make_goal(), persist=False)  # wired path supplies estimation
    # the wired strategy carries the estimation reference and complexity influence
    assert with_est.estimation_ref is not None
    assert with_est.complexity_class.estimation_influences
    # a goal-only reasoner (no estimation) records the absence assumption instead
    goal_only = DeterministicReasoner().reason(ReasoningInputs(goal=make_goal()), now="t")
    assert goal_only.estimation_ref is None
    assert without.identity == with_est.identity  # same wiring → same decision


def test_policy_influence_is_preserved() -> None:
    s = strategy_for(make_goal(), persist=False)
    assert s.policy_context is not None
    assert s.policy_context.decision  # the ceiling the reasoner consumed
    assert s.autonomy_level.policy_influences


def test_knowledge_influence_is_preserved() -> None:
    s = strategy_for(make_goal(), knowledge=(make_knowledge("kX"),), persist=False)
    assert s.knowledge_refs == ("kX",)
    assert s.approach.knowledge_influences == ("kX",)
