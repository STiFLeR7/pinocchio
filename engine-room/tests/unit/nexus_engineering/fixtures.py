"""Shared fixtures for the Engineering Intelligence (P5) suite."""

from __future__ import annotations

from nexus_core.contracts.base import Constraint, Correlation, Reference
from nexus_core.contracts.enums import (
    ConfidenceLadder,
    Domain,
    Freshness,
    InterpretationConfidence,
    KnowledgeType,
    Priority,
)
from nexus_core.domain.goal import Goal, Scope
from nexus_core.domain.knowledge import Knowledge
from nexus_engineering import build_engineering
from nexus_estimation import build_estimation
from nexus_infra import build_infrastructure
from nexus_policy import build_policy

_NOW = "2026-01-01T00:00:00Z"


def make_goal(
    *,
    identity: str = "g1",
    outcome: str = "fix the failing authentication bug reported by the partner in production",
    domain: Domain = Domain.SOFTWARE,
    priority: Priority = Priority.HIGH,
    confidence: InterpretationConfidence = InterpretationConfidence.MEDIUM,
    correlation: str = "cor-1",
) -> Goal:
    return Goal(
        identity=identity,
        outcome=outcome,
        domain=domain,
        priority=priority,
        confidence=confidence,
        constraints=(Constraint(kind="governance", detail={"note": "partner repo"}),),
        scope=Scope(included=("auth",), excluded=("billing",)),
        correlation=Correlation(correlation_identifier=correlation),
    )


def make_knowledge(identity: str = "k1", domain: Domain = Domain.SOFTWARE) -> Knowledge:
    return Knowledge(
        identity=identity,
        correlation_identifier="cor-prior",
        type=KnowledgeType.STRATEGY,
        understanding="surgical minimal-change works well for partner-reported auth bugs",
        evidence_refs=(Reference(target_type="evidence", identifier="ev-1"),),
        confidence=ConfidenceLadder.VALIDATED,
        freshness=Freshness.CURRENT,
        domain=domain,
    )


def wired(now=lambda: _NOW):
    """An infra with policy, estimation, and engineering all wired over one context."""
    infra = build_infrastructure()
    return (
        infra,
        build_engineering(infra, now=now),
        build_estimation(infra, now=now),
        build_policy(infra, now=now),
    )


def strategy_for(goal, *, persist=True, **kwargs):
    """Convenience: fully-wired strategy for a goal (consumes estimation + policy)."""
    _, eng, est, pol = wired()
    return eng.strategize_for_goal(
        goal, estimation_engine=est.engine, policy_engine=pol.engine, persist=persist, **kwargs
    )
