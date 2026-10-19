"""Grounding collectors — selected facts become incumbent RawContextFragments, by reference."""

from __future__ import annotations

from nexus_context.categories import ContextCategory, ContextSource
from nexus_context.grounding import GroundingSelector, grounding_collectors
from nexus_context.grounding.collectors import (
    HistoryGroundingCollector,
    KnowledgeGroundingCollector,
    RepositoryGroundingCollector,
    StrategyGroundingCollector,
)
from nexus_context.grounding.model import GroundingInputs
from nexus_context.requests import ContextRequest
from tests.unit.nexus_context.grounding.fixtures import make_goal, make_inputs


def _collect(collector, goal):
    return collector.collect(goal, ContextRequest())


def test_repository_collector_emits_facts_and_selected_refs(tmp_path) -> None:
    inputs = make_inputs(tmp_path)
    selection = GroundingSelector().select(inputs)
    fragments = _collect(RepositoryGroundingCollector(inputs, selection), inputs.goal)
    keys = {f.key for f in fragments}
    assert {"repository", "toolchain", "validation_signals"} <= keys
    assert "selected_modules" in keys and "selected_packages" in keys
    modules = next(f for f in fragments if f.key == "selected_modules")
    assert modules.category is ContextCategory.WORKSPACE
    assert any(ref.startswith("module:") for ref in modules.references)


def test_history_collector_surfaces_summary_and_selected_priors(tmp_path) -> None:
    inputs = make_inputs(tmp_path)
    selection = GroundingSelector().select(inputs)
    fragments = _collect(HistoryGroundingCollector(inputs, selection), inputs.goal)
    keys = {f.key for f in fragments}
    assert "execution_summary" in keys and "selected_prior_executions" in keys
    priors = next(f for f in fragments if f.key == "selected_prior_executions")
    assert priors.references == ("execution:pkg-a-fix",)
    assert priors.category is ContextCategory.HISTORICAL


def test_knowledge_collector_is_by_reference_only(tmp_path) -> None:
    inputs = make_inputs(tmp_path)
    selection = GroundingSelector().select(inputs)
    fragments = _collect(KnowledgeGroundingCollector(inputs, selection), inputs.goal)
    assert len(fragments) == 1
    frag = fragments[0]
    assert frag.source is ContextSource.KNOWLEDGE
    assert set(frag.references) == {"knowledge:k1", "knowledge:k2"}
    # by reference — ids + a short summary, never embedded evidence.
    assert all(set(item) == {"id", "type", "domain", "summary"} for item in frag.payload["items"])


def test_strategy_collector_surfaces_facets_as_context(tmp_path) -> None:
    inputs = make_inputs(tmp_path)
    fragments = _collect(StrategyGroundingCollector(inputs), inputs.goal)
    keys = {f.key for f in fragments}
    assert keys == {"context_objectives", "validation_rigor", "runtime_capabilities", "autonomy"}


def test_absent_sources_emit_no_fragments() -> None:
    inputs = GroundingInputs(goal=make_goal())
    selection = GroundingSelector().select(inputs)
    for collector in grounding_collectors(inputs, selection):
        assert collector.collect(inputs.goal, ContextRequest()) == ()
