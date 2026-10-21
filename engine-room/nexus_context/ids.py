"""Deterministic identifier derivation for Context Engineering.

Every identifier a context cycle produces is a pure function of the Goal identity
and the inputs' stable handles — no clock, no counter, no randomness. This is what
makes context assembly reproducible: the same Goal and the same
:class:`~nexus_context.requests.ContextRequest` always yield byte-identical
Context Packages, items, conflicts, and event identifiers.
"""

from __future__ import annotations


def context_id(goal_identity: str, version: str = "1") -> str:
    return f"context-{goal_identity}-v{version}"


def item_id(source: str, category: str, key: str) -> str:
    return f"ctxitem-{source}-{category}-{key}"


def event_id(context_identity: str, kind: str, sequence: int) -> str:
    return f"evt-{context_identity}-{kind}-{sequence:04d}"


def correlation_id(goal_identity: str) -> str:
    return f"cor-{goal_identity}"
