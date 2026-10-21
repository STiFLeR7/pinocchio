"""Condition-tree matcher + specificity (``nexus_policy.conditions``).

The matcher is the only interpreter of the data-driven condition tree (ADR-004 §3.1).
These prove operator semantics, boolean composition, the catch-all, fail-safe handling
of absent attributes, specificity counting, and that malformed trees raise (→ the engine
turns that into a fail-closed deny).
"""

from __future__ import annotations

import pytest

from nexus_policy.conditions import MalformedConditionError, matches, specificity


def test_empty_tree_is_catch_all() -> None:
    assert matches({}, {}) is True
    assert specificity({}) == 0


@pytest.mark.parametrize(
    ("op", "value", "attr_value", "expected"),
    [
        ("eq", "claude", "claude", True),
        ("eq", "claude", "gemini", False),
        ("ne", "approved", "pending", True),
        ("ne", "approved", "approved", False),
        ("in", ["a", "b"], "b", True),
        ("in", ["a", "b"], "c", False),
        ("not_in", ["a", "b"], "c", True),
        ("not_in", ["a", "b"], "a", False),
        ("gt", 5, 6, True),
        ("gte", 5, 5, True),
        ("lt", 5, 4, True),
        ("lte", 5, 5, True),
        ("contains", "sudo", "sudo rm", True),
        ("contains_any", ["rm -rf /", "sudo "], "run sudo x", True),
        ("contains_any", ["rm -rf /", "sudo "], "safe cmd", False),
    ],
)
def test_predicate_operators(op, value, attr_value, expected) -> None:
    node = {"attr": "x", "op": op, "value": value}
    assert matches(node, {"x": attr_value}) is expected


def test_absent_attribute_never_matches() -> None:
    # Fail-safe: a predicate over a missing attribute is not applicable, never a match.
    assert matches({"attr": "runtime", "op": "eq", "value": "claude"}, {}) is False
    assert matches({"attr": "runtime", "op": "ne", "value": "claude"}, {}) is False


def test_boolean_composition() -> None:
    tree = {
        "all": [
            {"attr": "action_class", "op": "eq", "value": "execution"},
            {
                "any": [
                    {"attr": "risk", "op": "eq", "value": "high"},
                    {"attr": "cost", "op": "gt", "value": 100},
                ]
            },
            {"not": {"attr": "actor", "op": "eq", "value": "system"}},
        ]
    }
    assert matches(tree, {"action_class": "execution", "risk": "high", "actor": "human"}) is True
    assert matches(tree, {"action_class": "execution", "cost": 250, "actor": "human"}) is True
    assert matches(tree, {"action_class": "execution", "risk": "low", "actor": "human"}) is False
    assert matches(tree, {"action_class": "execution", "risk": "high", "actor": "system"}) is False


def test_empty_all_is_true_empty_any_is_false() -> None:
    assert matches({"all": []}, {}) is True
    assert matches({"any": []}, {}) is False


def test_specificity_counts_bound_predicates() -> None:
    assert specificity({"attr": "runtime", "op": "eq", "value": "claude"}) == 1
    tree = {
        "all": [
            {"attr": "action_class", "op": "eq", "value": "execution"},
            {"not": {"attr": "actor", "op": "eq", "value": "system"}},
            {"any": [{"attr": "a", "op": "eq", "value": 1}, {"attr": "b", "op": "eq", "value": 2}]},
        ]
    }
    assert specificity(tree) == 4


def test_malformed_tree_raises() -> None:
    with pytest.raises(MalformedConditionError):
        matches({"bogus": 1}, {})
    with pytest.raises(MalformedConditionError):
        matches({"attr": "x", "op": "sideways", "value": 1}, {"x": 1})
    with pytest.raises(MalformedConditionError):
        matches({"attr": "x", "op": "eq"}, {"x": 1})  # missing value
