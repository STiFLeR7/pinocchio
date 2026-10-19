"""Unit tests for the Normalizer (Step 2, Phase 4).

Normalization is a pure adapter: it maps each raw fragment to a canonical
ContextItem, assigns a deterministic identity, preserves all provenance, defaults
relevance/freshness to their neutral values, and returns the set sorted by identity.
It never merges, drops, or resolves anything — these tests pin that exact contract.
"""

from __future__ import annotations

import pytest

from nexus_context import ids
from nexus_context.categories import ContextCategory, ContextSource, FreshnessState
from nexus_context.normalizer import Normalizer
from tests.unit.nexus_context.helpers import fragment

# --------------------------------------------------------------------------- #
# Field-by-field mapping                                                      #
# --------------------------------------------------------------------------- #


def test_normalize_maps_fragment_to_canonical_item() -> None:
    frag = fragment(
        "objective",
        source=ContextSource.OPERATOR,
        category=ContextCategory.GOAL,
        payload={"outcome": "ship"},
        observed_at="2026-01-01T00:00:00Z",
        references=("ref-1",),
        supersedes=("old-key",),
    )

    (item,) = Normalizer().normalize((frag,))

    assert item.identity == ids.item_id(
        ContextSource.OPERATOR.value, ContextCategory.GOAL.value, "objective"
    )
    assert item.category is ContextCategory.GOAL
    assert item.key == "objective"
    assert item.source is ContextSource.OPERATOR
    assert item.value == {"outcome": "ship"}
    assert item.observed_at == "2026-01-01T00:00:00Z"
    assert item.references == ("ref-1",)
    assert item.supersedes == ("old-key",)


def test_normalize_defaults_relevance_and_freshness() -> None:
    (item,) = Normalizer().normalize((fragment("a"),))

    # A freshly normalized item carries neutral relevance/freshness.
    assert item.relevance == 0
    assert item.freshness is FreshnessState.UNKNOWN


# --------------------------------------------------------------------------- #
# Deterministic ordering                                                      #
# --------------------------------------------------------------------------- #


def test_normalize_sorts_items_by_identity() -> None:
    # Supplied out of identity order; result must be sorted by identity.
    frag_c = fragment("c")
    frag_a = fragment("a")
    frag_b = fragment("b")

    items = Normalizer().normalize((frag_c, frag_a, frag_b))

    identities = [item.identity for item in items]
    assert identities == sorted(identities)
    assert [item.key for item in items] == ["a", "b", "c"]


def test_normalize_empty_fragments_yields_empty_tuple() -> None:
    assert Normalizer().normalize(()) == ()


# --------------------------------------------------------------------------- #
# Immutability                                                                #
# --------------------------------------------------------------------------- #


def test_context_item_is_frozen() -> None:
    (item,) = Normalizer().normalize((fragment("a"),))

    with pytest.raises(Exception):  # noqa: B017 — pydantic raises on frozen mutation.
        item.relevance = 99  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Determinism                                                                 #
# --------------------------------------------------------------------------- #


def test_normalize_is_deterministic() -> None:
    fragments = (fragment("b"), fragment("a"), fragment("c"))
    normalizer = Normalizer()

    first = normalizer.normalize(fragments)
    second = normalizer.normalize(fragments)

    assert first == second
