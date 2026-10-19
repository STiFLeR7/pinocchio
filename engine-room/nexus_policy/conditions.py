"""Condition-tree matching — the data-driven policy matcher (ADR-004 §3.1).

A policy's ``conditions`` is a structured boolean tree of typed predicates over
named attributes — DATA, never an embedded DSL (contract §6 *No embedded DSL*). This
module is the *only* interpreter of that data: it decides whether a policy applies
to a request and computes the policy's **specificity** (the number of bound attribute
predicates — the primary conflict-resolution metric, ADR-004 §3.1).

Tree grammar (every node is a plain mapping)::

    {}                                    -> always true (catch-all; specificity 0)
    {"all": [node, ...]}                  -> AND (an empty list is true)
    {"any": [node, ...]}                  -> OR  (an empty list is false)
    {"not": node}                         -> negation
    {"attr": name, "op": op, "value": v}  -> a typed predicate (a leaf)

Supported ops: ``eq``, ``ne``, ``in``, ``not_in``, ``gt``, ``gte``, ``lt``, ``lte``,
``contains``, ``contains_any``. A predicate over an *absent* attribute never matches
(deterministic and fail-safe): the policy is simply not applicable, and fail-closed
default-deny (INV-30) still applies when nothing allows. A structurally malformed
tree raises :class:`MalformedConditionError`, which the engine turns into a
fail-closed deny.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class MalformedConditionError(ValueError):
    """A condition tree is not well-formed (unknown node kind or operator, bad predicate)."""


_MISSING = object()


def matches(conditions: Mapping[str, Any], attributes: Mapping[str, Any]) -> bool:
    """Whether ``conditions`` applies to ``attributes`` (the request's evaluation view)."""
    return _eval_node(conditions, attributes)


def specificity(conditions: Mapping[str, Any]) -> int:
    """The number of bound attribute predicates in the tree (ADR-004 §3.1 *Specificity*)."""
    return _count_predicates(conditions)


def _eval_node(node: Any, attributes: Mapping[str, Any]) -> bool:
    if not isinstance(node, Mapping):
        raise MalformedConditionError(
            f"condition node must be a mapping, got {type(node).__name__}"
        )
    if not node:
        return True
    if "all" in node:
        return all(_eval_node(child, attributes) for child in node["all"])
    if "any" in node:
        return any(_eval_node(child, attributes) for child in node["any"])
    if "not" in node:
        return not _eval_node(node["not"], attributes)
    if "attr" in node:
        return _eval_predicate(node, attributes)
    raise MalformedConditionError(f"unknown condition node: {sorted(node)}")


def _eval_predicate(node: Mapping[str, Any], attributes: Mapping[str, Any]) -> bool:
    try:
        attr, op, value = node["attr"], node["op"], node["value"]
    except KeyError as exc:
        raise MalformedConditionError(f"predicate missing key {exc}") from exc
    actual = attributes.get(attr, _MISSING)
    if actual is _MISSING:
        return False
    return _apply(op, actual, value)


def _apply(op: str, actual: Any, value: Any) -> bool:
    if op == "eq":
        return bool(actual == value)
    if op == "ne":
        return bool(actual != value)
    if op == "in":
        return actual in value
    if op == "not_in":
        return actual not in value
    if op == "gt":
        return bool(actual > value)
    if op == "gte":
        return bool(actual >= value)
    if op == "lt":
        return bool(actual < value)
    if op == "lte":
        return bool(actual <= value)
    if op == "contains":
        return value in actual
    if op == "contains_any":
        return any(item in actual for item in value)
    raise MalformedConditionError(f"unknown operator: {op!r}")


def _count_predicates(node: Any) -> int:
    if not isinstance(node, Mapping) or not node:
        return 0
    if "all" in node:
        return sum(_count_predicates(child) for child in node["all"])
    if "any" in node:
        return sum(_count_predicates(child) for child in node["any"])
    if "not" in node:
        return _count_predicates(node["not"])
    if "attr" in node:
        return 1
    return 0
