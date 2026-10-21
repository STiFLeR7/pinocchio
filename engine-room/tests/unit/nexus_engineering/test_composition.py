"""Composition — additive DI wiring; EI consumes Estimation + Policy without owning them."""

from __future__ import annotations

from nexus_engineering import EngineeringContext
from nexus_engineering.composition import signals_from_goal
from nexus_estimation.events import ESTIMATION_ESTIMATED
from nexus_policy.events import POLICY_EVALUATED
from tests.unit.nexus_engineering.fixtures import make_goal, wired


def test_build_engineering_returns_a_wired_context() -> None:
    infra, eng, _, _ = wired()
    assert isinstance(eng, EngineeringContext)
    assert eng.infrastructure is infra
    assert eng.engine.reasoner_version == "1"


def test_strategize_for_goal_consumes_estimation_and_policy() -> None:
    infra, eng, est, pol = wired()
    strategy = eng.strategize_for_goal(
        make_goal(), estimation_engine=est.engine, policy_engine=pol.engine
    )
    # estimation was consumed (it recorded its own fact) and its report referenced by EI
    assert strategy.estimation_ref is not None
    assert any(e.type == ESTIMATION_ESTIMATED for e in infra.event_store.read_all())
    # policy was queried via side-effect-free simulate → NO policy.evaluated fact recorded
    assert not any(e.type == POLICY_EVALUATED for e in infra.event_store.read_all())
    assert strategy.policy_context is not None


def test_strategy_is_persisted_in_the_repository() -> None:
    _, eng, est, pol = wired()
    strategy = eng.strategize_for_goal(
        make_goal(), estimation_engine=est.engine, policy_engine=pol.engine
    )
    assert eng.repositories.strategies.get(strategy.identity) == strategy


def test_signals_from_goal_are_factual_counts() -> None:
    sig = signals_from_goal(make_goal())
    assert sig["constraint_count"] == 1.0
    assert sig["scope_included"] == 1.0
    assert all(isinstance(v, float) for v in sig.values())
