"""Shared, deterministic builders for the context-engineering test suite.

A single source of truth for constructing valid Goals, raw fragments, context
requests, and a fully-wired context-engineering environment with a fixed timestamp
source — so context tests read as intent and stay reproducible.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from nexus_context import (
    ContextCategory,
    ContextCollector,
    ContextEngineeringContext,
    ContextRequest,
    ContextSource,
    FixedTimestampSource,
    FreshnessPolicy,
    RawContextFragment,
    build_context_engineering,
)
from nexus_core.contracts.base import Constraint, Reference
from nexus_core.contracts.enums import Domain, InterpretationConfidence, Priority
from nexus_core.contracts.status import GoalStatus
from nexus_core.domain import Goal, Scope
from nexus_infra import InfrastructureContext, build_infrastructure


def make_goal(
    identity: str = "goal-1",
    *,
    outcome: str = "Ship the feature",
    status: GoalStatus | None = None,
    success_definition: str | None = None,
    constraints: tuple[Constraint, ...] = (),
) -> Goal:
    """Build a valid :class:`Goal` for context engineering."""
    return Goal(
        identity=identity,
        outcome=outcome,
        domain=Domain.SOFTWARE,
        priority=Priority.HIGH,
        confidence=InterpretationConfidence.HIGH,
        constraints=constraints,
        scope=Scope(included=("x",), excluded=()),
        status=status,
        success_definition=success_definition,
    )


def fragment(
    key: str,
    *,
    source: ContextSource = ContextSource.WORKSPACE,
    category: ContextCategory = ContextCategory.WORKSPACE,
    payload: dict[str, object] | None = None,
    observed_at: str | None = None,
    references: tuple[str, ...] = (),
    supersedes: tuple[str, ...] = (),
) -> RawContextFragment:
    """Build a :class:`RawContextFragment` with sensible defaults."""
    return RawContextFragment(
        source=source,
        category=category,
        key=key,
        payload=payload or {},
        observed_at=observed_at,
        references=references,
        supersedes=supersedes,
    )


def request(
    *fragments: RawContextFragment,
    declared_dependencies: tuple[str, ...] = (),
    known_unknowns: tuple[str, ...] = (),
    constraints: tuple[Constraint, ...] = (),
    resources: tuple[Reference, ...] = (),
    supporting_artifacts: tuple[Reference, ...] = (),
    references: tuple[str, ...] = (),
    freshness_policy: FreshnessPolicy | None = None,
    relevance_weights: dict[str, object] | None = None,
    correlation_identifier: str | None = None,
    package_version: str = "1",
) -> ContextRequest:
    """Build a :class:`ContextRequest` from fragments and any overrides."""
    return ContextRequest(
        fragments=fragments,
        declared_dependencies=declared_dependencies,
        known_unknowns=known_unknowns,
        constraints=constraints,
        resources=resources,
        supporting_artifacts=supporting_artifacts,
        references=references,
        freshness_policy=freshness_policy or FreshnessPolicy(),
        relevance_weights=relevance_weights or {},
        correlation_identifier=correlation_identifier,
        package_version=package_version,
    )


@dataclass(frozen=True, slots=True)
class ContextEnv:
    """A wired infrastructure + context-engineering pair for a test."""

    infrastructure: InfrastructureContext
    context: ContextEngineeringContext


def context_env(*, collectors: Iterable[ContextCollector] | None = None) -> ContextEnv:
    """Build a fresh, deterministic context-engineering environment."""
    infrastructure = build_infrastructure()
    context = build_context_engineering(
        infrastructure,
        collectors=collectors,
        timestamps=FixedTimestampSource(),
    )
    return ContextEnv(infrastructure=infrastructure, context=context)
