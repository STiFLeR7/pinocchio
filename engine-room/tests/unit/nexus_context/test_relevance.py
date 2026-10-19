"""Unit tests for the deterministic Relevance Ranker (Step 4, Phase 4).

Relevance is fixed integer math — no AI, no floats, no clock. Each item's score is
``_CATEGORY_BASE[category] + _SOURCE_WEIGHT[source]`` plus any additive overrides the
request supplies in ``relevance_weights`` (keyed by the category *or* source value,
int only, bool excluded). ``rank`` returns frozen enriched copies sorted by relevance
descending then identity ascending. These tests pin the exact scores, the ordering,
the override rules, the bool/non-int exclusion, determinism, and frozen-copy isolation.
"""

from __future__ import annotations

from nexus_context.categories import ContextCategory, ContextSource
from nexus_context.normalizer import Normalizer
from nexus_context.relevance import RelevanceRanker
from nexus_context.requests import ContextItem
from tests.unit.nexus_context.helpers import fragment, request


def _items(*fragments: object) -> tuple[ContextItem, ...]:
    """Normalize raw fragments into the canonical item set the ranker consumes."""
    return Normalizer().normalize(tuple(fragments))  # type: ignore[arg-type]


def _by_identity(items: tuple[ContextItem, ...]) -> dict[str, ContextItem]:
    return {item.identity: item for item in items}


# --------------------------------------------------------------------------- #
# Exact scoring                                                               #
# --------------------------------------------------------------------------- #


def test_exact_score_for_known_category_source_pair() -> None:
    # GOAL base (100) + OPERATOR weight (20) = 120, with no overrides.
    items = _items(
        fragment("objective", source=ContextSource.OPERATOR, category=ContextCategory.GOAL)
    )
    ranked = RelevanceRanker().rank(items, request())

    assert len(ranked) == 1
    assert ranked[0].relevance == 120


def test_exact_score_for_lowest_pair() -> None:
    # HISTORICAL base (20) + WORKSPACE weight (5) = 25.
    items = _items(
        fragment("old", source=ContextSource.WORKSPACE, category=ContextCategory.HISTORICAL)
    )
    ranked = RelevanceRanker().rank(items, request())

    assert ranked[0].relevance == 25


def test_default_helper_fragment_scores_workspace_workspace() -> None:
    # Helper defaults: WORKSPACE category (30) + WORKSPACE source (5) = 35.
    ranked = RelevanceRanker().rank(_items(fragment("w")), request())

    assert ranked[0].relevance == 35


# --------------------------------------------------------------------------- #
# Ordering                                                                    #
# --------------------------------------------------------------------------- #


def test_ranks_by_relevance_descending() -> None:
    items = _items(
        fragment("low", source=ContextSource.WORKSPACE, category=ContextCategory.HISTORICAL),
        fragment("high", source=ContextSource.OPERATOR, category=ContextCategory.GOAL),
        fragment("mid", source=ContextSource.KNOWLEDGE, category=ContextCategory.DOMAIN),
    )
    ranked = RelevanceRanker().rank(items, request())

    relevances = [item.relevance for item in ranked]
    assert relevances == sorted(relevances, reverse=True)
    # GOAL+OPERATOR (120) > DOMAIN+KNOWLEDGE (60) > HISTORICAL+WORKSPACE (25).
    assert relevances == [120, 60, 25]


def test_ties_break_by_identity_ascending() -> None:
    # Two distinct keys, identical (category, source) -> identical relevance (35).
    items = _items(
        fragment("bbb"),
        fragment("aaa"),
    )
    ranked = RelevanceRanker().rank(items, request())

    assert {item.relevance for item in ranked} == {35}
    identities = [item.identity for item in ranked]
    assert identities == sorted(identities)


def test_goal_outranks_historical_for_same_source() -> None:
    items = _items(
        fragment("g", source=ContextSource.WORKSPACE, category=ContextCategory.GOAL),
        fragment("h", source=ContextSource.WORKSPACE, category=ContextCategory.HISTORICAL),
    )
    ranked = RelevanceRanker().rank(items, request())

    by_id = _by_identity(ranked)
    goal = by_id["ctxitem-workspace-goal_context-g"]
    historical = by_id["ctxitem-workspace-historical_context-h"]
    # GOAL base (100) + WORKSPACE (5) = 105 > HISTORICAL base (20) + WORKSPACE (5) = 25.
    assert goal.relevance == 105
    assert historical.relevance == 25
    assert ranked[0] is goal


# --------------------------------------------------------------------------- #
# relevance_weights overrides                                                 #
# --------------------------------------------------------------------------- #


def test_category_override_is_additive() -> None:
    items = _items(fragment("g", source=ContextSource.OPERATOR, category=ContextCategory.GOAL))
    # +7 keyed by the category value ("goal_context"): 100 + 20 + 7 = 127.
    req = request(relevance_weights={ContextCategory.GOAL.value: 7})
    ranked = RelevanceRanker().rank(items, req)

    assert ranked[0].relevance == 127


def test_source_override_is_additive() -> None:
    items = _items(fragment("g", source=ContextSource.OPERATOR, category=ContextCategory.GOAL))
    # +3 keyed by the source value ("operator"): 100 + 20 + 3 = 123.
    req = request(relevance_weights={ContextSource.OPERATOR.value: 3})
    ranked = RelevanceRanker().rank(items, req)

    assert ranked[0].relevance == 123


def test_category_and_source_overrides_stack() -> None:
    items = _items(fragment("g", source=ContextSource.OPERATOR, category=ContextCategory.GOAL))
    req = request(
        relevance_weights={
            ContextCategory.GOAL.value: 7,
            ContextSource.OPERATOR.value: 3,
        }
    )
    ranked = RelevanceRanker().rank(items, req)

    # 100 + 20 + 7 + 3 = 130.
    assert ranked[0].relevance == 130


def test_negative_override_lowers_score() -> None:
    items = _items(fragment("g", source=ContextSource.OPERATOR, category=ContextCategory.GOAL))
    req = request(relevance_weights={ContextCategory.GOAL.value: -50})
    ranked = RelevanceRanker().rank(items, req)

    # 100 + 20 - 50 = 70.
    assert ranked[0].relevance == 70


def test_bool_override_is_ignored() -> None:
    items = _items(fragment("g", source=ContextSource.OPERATOR, category=ContextCategory.GOAL))
    # bool is excluded even though bool is an int subclass: True must not add 1.
    req = request(relevance_weights={ContextCategory.GOAL.value: True})
    ranked = RelevanceRanker().rank(items, req)

    assert ranked[0].relevance == 120


def test_non_int_override_is_ignored() -> None:
    items = _items(fragment("g", source=ContextSource.OPERATOR, category=ContextCategory.GOAL))
    req = request(
        relevance_weights={
            ContextCategory.GOAL.value: "5",
            ContextSource.OPERATOR.value: 4.5,
        }
    )
    ranked = RelevanceRanker().rank(items, req)

    # Neither a str nor a float contributes; base score only.
    assert ranked[0].relevance == 120


def test_unrelated_override_keys_have_no_effect() -> None:
    items = _items(fragment("g", source=ContextSource.OPERATOR, category=ContextCategory.GOAL))
    # Override keyed by a category/source this item does not have.
    req = request(
        relevance_weights={
            ContextCategory.HISTORICAL.value: 99,
            ContextSource.WORKSPACE.value: 99,
        }
    )
    ranked = RelevanceRanker().rank(items, req)

    assert ranked[0].relevance == 120


# --------------------------------------------------------------------------- #
# Determinism & immutability                                                  #
# --------------------------------------------------------------------------- #


def test_rank_is_deterministic() -> None:
    items = _items(
        fragment("a", source=ContextSource.OPERATOR, category=ContextCategory.GOAL),
        fragment("b", source=ContextSource.WORKSPACE, category=ContextCategory.HISTORICAL),
        fragment("c", source=ContextSource.KNOWLEDGE, category=ContextCategory.DOMAIN),
    )
    req = request(relevance_weights={ContextCategory.GOAL.value: 5})
    ranker = RelevanceRanker()

    first = ranker.rank(items, req)
    second = ranker.rank(items, req)

    assert first == second


def test_rank_returns_frozen_copies_leaving_originals_unchanged() -> None:
    items = _items(fragment("g", source=ContextSource.OPERATOR, category=ContextCategory.GOAL))
    original = items[0]
    assert original.relevance == 0

    ranked = RelevanceRanker().rank(items, request())

    # The original is untouched; the ranked item is a distinct enriched copy.
    assert original.relevance == 0
    assert ranked[0] is not original
    assert ranked[0].relevance == 120
    assert ranked[0].identity == original.identity
