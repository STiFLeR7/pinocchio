"""Engine behavior — one Strategy, one recorded fact, full explainable shape, absence-tolerance."""

from __future__ import annotations

from nexus_engineering import ReasoningInputs
from nexus_engineering.events import ENGINEERING_STRATEGIZED
from tests.unit.nexus_engineering.fixtures import make_goal, make_knowledge, strategy_for, wired


def test_strategize_produces_one_strategy_and_one_event() -> None:
    infra, eng, est, pol = wired()
    goal = make_goal()
    strategy = eng.strategize_for_goal(goal, estimation_engine=est.engine, policy_engine=pol.engine)

    events = [e for e in infra.event_store.read_all() if e.type == ENGINEERING_STRATEGIZED]
    assert len(events) == 1
    assert events[0].correlation_identifier == "cor-1"
    assert events[0].payload["strategy"]["identity"] == strategy.identity


def test_every_facet_carries_the_required_explainability_shape() -> None:
    strategy = strategy_for(make_goal(), persist=False)
    # Constitution / engineering/03: every recommendation is self-explaining (INV-31).
    for facet in strategy.facets():
        assert facet.selection, facet.facet
        assert facet.reasoning_chain, facet.facet
        assert facet.contributing_evidence, facet.facet
        assert 0.0 <= facet.confidence <= 1.0, facet.facet


def test_strategy_has_every_required_section() -> None:
    s = strategy_for(make_goal(), persist=False)
    assert s.engineering_objective
    assert s.classification.selection[0]
    assert s.approach.selection[0]  # strategy type
    assert s.complexity_class.selection[0]
    assert s.execution_style.selection[0]
    assert s.runtime_preferences.selection  # recommended runtime capabilities
    assert s.skill_requirements.selection  # recommended skills
    assert s.validation_rigor.selection  # recommended validation approach
    assert s.recovery_posture.selection[0]  # recommended recovery posture
    assert s.autonomy_level.selection  # approval recommendations
    assert s.observability.selection[0]  # observability requirements
    assert s.rationale
    assert s.coherence_notes


def test_influences_are_recorded_on_the_relevant_facets() -> None:
    s = strategy_for(make_goal(), knowledge=(make_knowledge(),), persist=False)
    # estimation influence on complexity; policy influence on autonomy; knowledge influence on approach.
    assert s.complexity_class.estimation_influences
    assert s.autonomy_level.policy_influences
    assert s.approach.knowledge_influences == ("k1",)
    assert s.estimation_ref is not None
    assert s.policy_context is not None
    assert s.knowledge_refs == ("k1",)


def test_absence_tolerant_reasons_with_only_a_goal() -> None:
    # No estimation, no policy, no knowledge, no repo, no prefs, no environment.
    infra, eng, _, _ = wired()
    strategy = eng.engine.strategize(ReasoningInputs(goal=make_goal()))
    assert strategy.identity
    assert strategy.estimation_ref is None
    assert strategy.policy_context is None
    # fail-closed without policy: autonomy capped.
    assert strategy.autonomy_level.selection[0] in ("gated", "manual")


def test_engine_records_reasoner_version() -> None:
    s = strategy_for(make_goal(), persist=False)
    assert s.reasoner_version == "1"
