"""Deterministic identifier derivation.

Every identifier a planning cycle produces is a pure function of the Goal and the
work-item keys — no clock, no counter, no randomness. This is what makes planning
reproducible: the same Goal and request always yield the same Plan, Work Package,
graph, node, edge, and event identifiers.
"""

from __future__ import annotations


def plan_id(goal_identity: str, version: str = "1") -> str:
    return f"plan-{goal_identity}-v{version}"


def work_package_id(goal_identity: str, item_key: str) -> str:
    return f"wp-{goal_identity}-{item_key}"


def graph_id(goal_identity: str, version: str = "1") -> str:
    return f"graph-{goal_identity}-v{version}"


def strategy_id(goal_identity: str, version: str = "1") -> str:
    return f"strategy-{goal_identity}-v{version}"


def node_id(item_key: str) -> str:
    return f"node-{item_key}"


def edge_id(source_node: str, target_node: str, edge_type: str) -> str:
    return f"edge-{source_node}->{target_node}:{edge_type}"


def event_id(plan_identity: str, kind: str, sequence: int) -> str:
    return f"evt-{plan_identity}-{kind}-{sequence:04d}"


def correlation_id(goal_identity: str) -> str:
    return f"cor-{goal_identity}"
