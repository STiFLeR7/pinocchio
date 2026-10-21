"""Shared, deterministic builders for the planning test suite.

A single source of truth for constructing valid Goals, Capabilities, work-item
specs, and a fully-wired planning environment with a fixed timestamp source — so
planning tests read as intent and stay reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.contracts.enums import (
    CapabilityCategory,
    Domain,
    InterpretationConfidence,
    Priority,
)
from nexus_core.contracts.status import GoalStatus
from nexus_core.domain import Capability, Goal, Scope
from nexus_infra import InfrastructureContext, build_infrastructure
from nexus_planning import (
    FixedTimestampSource,
    InMemoryCapabilityRegistry,
    PlanningContext,
    WorkItemSpec,
    build_planning,
)


def make_goal(
    identity: str = "goal-1",
    *,
    outcome: str = "Ship the feature",
    status: GoalStatus | None = None,
) -> Goal:
    """Build a valid :class:`Goal` for planning."""
    return Goal(
        identity=identity,
        outcome=outcome,
        domain=Domain.SOFTWARE,
        priority=Priority.HIGH,
        confidence=InterpretationConfidence.HIGH,
        constraints=(),
        scope=Scope(included=("x",), excluded=()),
        status=status,
    )


def make_capability(
    identifier: str,
    *,
    version: str = "1",
    category: CapabilityCategory = CapabilityCategory.ANALYSIS,
) -> Capability:
    """Build a valid :class:`Capability`."""
    return Capability(
        identifier=identifier,
        name=identifier.replace(".", " ").title(),
        version=version,
        category=category,
        description="capability",
        inputs=(),
        outputs=(),
    )


def item(key: str, **overrides: object) -> WorkItemSpec:
    """Build a :class:`WorkItemSpec` with a key and any overrides."""
    return WorkItemSpec(key=key, objective=overrides.pop("objective", f"Do {key}"), **overrides)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class PlanningEnv:
    """A wired infrastructure + planning pair for a test."""

    infrastructure: InfrastructureContext
    planning: PlanningContext


def planning_env(*capabilities: Capability) -> PlanningEnv:
    """Build a fresh, deterministic planning environment with registered capabilities."""
    infrastructure = build_infrastructure()
    registry = InMemoryCapabilityRegistry()
    for capability in capabilities:
        registry.register(capability)
    planning = build_planning(
        infrastructure,
        capability_registry=registry,
        timestamps=FixedTimestampSource(),
    )
    return PlanningEnv(infrastructure=infrastructure, planning=planning)
