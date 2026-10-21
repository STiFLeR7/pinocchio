"""Deterministic factories for valid domain objects used across infra tests.

Every builder fills all required contract fields with stable, deterministic
defaults and accepts overrides for the fields a test cares about. Keeping
construction in one place means a test reads as intent (what differs) rather than
boilerplate, and a contract change is fixed in one spot.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import (
    ArtifactStatus,
    ArtifactType,
    ConfidenceLadder,
    Domain,
    Freshness,
    InterpretationConfidence,
    KnowledgeType,
    PolicyDecision,
    Priority,
)
from nexus_core.domain import (
    Artifact,
    Goal,
    Knowledge,
    Milestone,
    Plan,
    Policy,
    Scope,
)
from nexus_core.domain.event import Event


def make_event(
    identifier: str = "evt-1",
    *,
    type: str = "goal.created",  # noqa: A002 — mirrors the Event contract field name
    version: str = "1",
    correlation_identifier: str = "cor-1",
    sequence_position: int | None = None,
    payload: dict[str, object] | None = None,
    producer: str = "intent_resolution",
    source: str = "test",
    **overrides: object,
) -> Event:
    """Build a valid :class:`Event` with deterministic defaults."""
    return Event(
        identifier=identifier,
        type=type,
        version=version,
        timestamp="2026-01-01T00:00:00Z",
        producer=producer,
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload=payload or {},
        source=source,
        sequence_position=sequence_position,
        **overrides,
    )


def make_goal(identity: str = "goal-1", *, outcome: str = "Resolve the issue") -> Goal:
    """Build a valid :class:`Goal`."""
    return Goal(
        identity=identity,
        outcome=outcome,
        domain=Domain.SOFTWARE,
        priority=Priority.HIGH,
        confidence=InterpretationConfidence.HIGH,
        constraints=(),
        scope=Scope(included=("x",), excluded=()),
    )


def make_plan(identity: str = "plan-1") -> Plan:
    """Build a valid :class:`Plan`."""
    return Plan(
        identity=identity,
        parent_goal=Reference(target_type="goal", identifier="goal-1"),
        version="1",
        approach_summary="approach",
        milestones=(Milestone(identifier="m1", meaning="first", completion_condition="done"),),
        priorities={},
        dependency_summary="none",
        work_package_refs=(Reference(target_type="work_package", identifier="wp-1"),),
        execution_graph_ref=Reference(target_type="execution_graph", identifier="eg-1"),
        rationale="because",
    )


def make_artifact(identity: str = "artifact-1") -> Artifact:
    """Build a valid :class:`Artifact`."""
    return Artifact(
        identity=identity,
        type=ArtifactType.SOURCE,
        owner="execution",
        producer="execution",
        created_time="2026-01-01T00:00:00Z",
        updated_time="2026-01-01T00:00:00Z",
        version="1",
        status=ArtifactStatus.GENERATED,
        lineage={},
        correlation_identifier="cor-1",
    )


def make_policy(identity: str = "policy-1") -> Policy:
    """Build a valid :class:`Policy`."""
    return Policy(
        identity=identity,
        version="1",
        purpose="guard",
        conditions={},
        decision=PolicyDecision.ALLOW,
        priority=10,
        owner="governance",
    )


def make_knowledge(identity: str = "knowledge-1") -> Knowledge:
    """Build a valid :class:`Knowledge`."""
    return Knowledge(
        identity=identity,
        correlation_identifier="cor-1",
        type=KnowledgeType.LESSON,
        understanding="learned something",
        evidence_refs=(Reference(target_type="evidence", identifier="ev-1"),),
        confidence=ConfidenceLadder.OBSERVED,
        freshness=Freshness.CURRENT,
    )
