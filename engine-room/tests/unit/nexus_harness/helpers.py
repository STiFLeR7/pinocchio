"""Shared, deterministic builders for the harness test suite.

A single source of truth for constructing the objects the Harness resolves against
(Skills, Capabilities, Policies, Context Packages, Work Packages, Execution
Strategies, Artifacts), the upstream Harness Requests it compiles, and a fully-wired
harness environment with a fixed timestamp source — so harness tests read as intent
and stay reproducible. Harness Requests are built directly (no dependency on
Orchestration's correctness); the integration test exercises the real
Planning → Orchestration → Harness seam separately.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from nexus_core.contracts.base import Constraint, Correlation, Reference, Struct
from nexus_core.contracts.enums import (
    ApprovalTaxonomy,
    ArtifactStatus,
    ArtifactType,
    CapabilityCategory,
    CoordinationModel,
    InterpretationConfidence,
    PolicyCategory,
    PolicyDecision,
    Priority,
    RetryBehavior,
    SkillCategory,
)
from nexus_core.domain.artifact import Artifact
from nexus_core.domain.capability import Capability
from nexus_core.domain.context_package import ContextCategories, ContextPackage
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_core.domain.policy import Policy
from nexus_core.domain.skill import Skill
from nexus_core.domain.work_package import WorkPackage
from nexus_harness import (
    FixedTimestampSource,
    HarnessContext,
    build_harness,
)
from nexus_infra import InfrastructureContext, build_infrastructure
from nexus_orchestration.harness_requests import HarnessRequest

DEFAULT_GOAL = "goal-1"
DEFAULT_PLAN = "plan-goal-1-v1"
DEFAULT_CONTEXT = "ctx-1"
DEFAULT_SESSION = "session-goal-1-v1"
DEFAULT_STRATEGY = "strat-1"


def ref(target_type: str, identifier: str) -> Reference:
    """Build a typed :class:`Reference`."""
    return Reference(target_type=target_type, identifier=identifier)


def skill(
    identity: str,
    *,
    capabilities: Sequence[str] = (),
    category: SkillCategory = SkillCategory.ANALYSIS,
    version: str = "1",
) -> Skill:
    """Build a valid runtime-independent :class:`Skill`."""
    return Skill(
        identity=identity,
        name=identity.replace("-", " ").title(),
        version=version,
        purpose=f"perform {identity}",
        inputs=(),
        outputs=(),
        procedure={},
        category=category,
        required_capabilities=tuple(ref("capability", cap) for cap in capabilities),
    )


def capability(
    identifier: str,
    *,
    category: CapabilityCategory = CapabilityCategory.ANALYSIS,
    version: str = "1",
) -> Capability:
    """Build a valid provider-independent :class:`Capability`."""
    return Capability(
        identifier=identifier,
        name=identifier.replace("-", " ").title(),
        version=version,
        category=category,
        description=f"capability {identifier}",
        inputs=(),
        outputs=(),
    )


def policy(
    identity: str,
    *,
    version: str = "1",
    decision: PolicyDecision = PolicyDecision.ALLOW,
    category: PolicyCategory | None = PolicyCategory.GOVERNANCE,
) -> Policy:
    """Build a valid declarative :class:`Policy`."""
    return Policy(
        identity=identity,
        version=version,
        purpose=f"govern {identity}",
        conditions={},
        decision=decision,
        priority=0,
        owner="governance",
        category=category,
    )


def context_package(
    identity: str = DEFAULT_CONTEXT,
    *,
    goal: str = DEFAULT_GOAL,
    confidence: InterpretationConfidence = InterpretationConfidence.HIGH,
    constraints: Sequence[Constraint] = (),
    resources: Sequence[Reference] = (),
    known_unknowns: Sequence[str] = (),
    categories: ContextCategories | None = None,
) -> ContextPackage:
    """Build a valid :class:`ContextPackage`."""
    return ContextPackage(
        identity=identity,
        goal_ref=ref("goal", goal),
        correlation=Correlation(correlation_identifier=f"cor-{goal}"),
        context_categories=categories or ContextCategories(),
        constraints=tuple(constraints),
        resources=tuple(resources),
        confidence=confidence,
        validation_status={"validated": True},
        known_unknowns=tuple(known_unknowns),
    )


def work_package(
    identifier: str,
    *,
    goal: str = DEFAULT_GOAL,
    plan: str = DEFAULT_PLAN,
    context: str = DEFAULT_CONTEXT,
    skills: Sequence[Reference] = (),
    inputs: Sequence[Reference] = (),
    priority: Priority = Priority.MEDIUM,
) -> WorkPackage:
    """Build a valid :class:`WorkPackage`."""
    return WorkPackage(
        identifier=identifier,
        parent_goal=ref("goal", goal),
        parent_plan=ref("plan", plan),
        priority=priority,
        objective=f"accomplish {identifier}",
        context=ref("context_package", context),
        constraints=(),
        resources=(),
        skills=tuple(skills),
        inputs=tuple(inputs),
        outputs=(),
        evidence={},
        completion_criteria={},
    )


def strategy(
    identity: str = DEFAULT_STRATEGY,
    *,
    coordination: CoordinationModel = CoordinationModel.SEQUENTIAL,
    approval_policy: ApprovalTaxonomy = ApprovalTaxonomy.AUTOMATIC,
    runtime_policy: Struct | None = None,
) -> ExecutionStrategy:
    """Build a valid declarative :class:`ExecutionStrategy`."""
    return ExecutionStrategy(
        identity=identity,
        coordination=coordination,
        runtime_policy=runtime_policy if runtime_policy is not None else {},
        approval_policy=approval_policy,
        retry_policy=RetryBehavior.NEVER_RETRY,
        timeout_policy={},
        validation_policy={},
        recovery_policy={},
        checkpoint_policy={},
    )


def artifact(
    identity: str,
    *,
    artifact_type: ArtifactType = ArtifactType.DOCUMENTATION,
    status: ArtifactStatus = ArtifactStatus.PUBLISHED,
    version: str = "1",
) -> Artifact:
    """Build a valid immutable :class:`Artifact`."""
    return Artifact(
        identity=identity,
        type=artifact_type,
        owner="planning",
        producer="planning",
        created_time="1970-01-01T00:00:00+00:00",
        updated_time="1970-01-01T00:00:00+00:00",
        version=version,
        status=status,
        lineage={},
        correlation_identifier="cor-goal-1",
    )


def hrequest(
    node: str,
    *,
    identity: str | None = None,
    session: str = DEFAULT_SESSION,
    work_package: str = "wp-1",
    context: str | None = DEFAULT_CONTEXT,
    strategy_ref: str | None = DEFAULT_STRATEGY,
    skills: Sequence[Reference] = (),
    capabilities: Sequence[Reference] = (),
    constraints: Sequence[Constraint] = (),
    coordination: CoordinationModel = CoordinationModel.SEQUENTIAL,
    correlation: str | None = "cor-goal-1",
) -> HarnessRequest:
    """Build a :class:`HarnessRequest` directly (mirrors Orchestration's output shape)."""
    return HarnessRequest(
        identity=identity or f"hreq-{session}-{node}",
        session_ref=ref("execution_session", session),
        node=node,
        work_package_ref=ref("work_package", work_package),
        execution_strategy_ref=(ref("execution_strategy", strategy_ref) if strategy_ref else None),
        context_ref=(ref("context_package", context) if context else None),
        coordination=coordination,
        required_skill_refs=tuple(skills),
        required_capability_refs=tuple(capabilities),
        constraints=tuple(constraints),
        correlation=(
            Correlation(correlation_identifier=correlation) if correlation is not None else None
        ),
    )


@dataclass(frozen=True, slots=True)
class HarnessEnv:
    """A wired infrastructure + harness pair for a test."""

    infrastructure: InfrastructureContext
    harness: HarnessContext


def harness_env(
    *,
    skills: Sequence[Skill] = (),
    capabilities: Sequence[Capability] = (),
    policies: Sequence[Policy] = (),
    context_packages: Sequence[ContextPackage] = (),
    work_packages: Sequence[WorkPackage] = (),
    strategies: Sequence[ExecutionStrategy] = (),
    artifacts: Sequence[Artifact] = (),
) -> HarnessEnv:
    """Build a fresh, deterministic harness environment with its sources populated."""
    infrastructure = build_infrastructure()
    harness = build_harness(infrastructure, timestamps=FixedTimestampSource())
    sources = harness.sources
    for one_skill in skills:
        sources.skills.register(one_skill)
    for one_capability in capabilities:
        sources.capabilities.register(one_capability)
    for one_policy in policies:
        sources.policies.register(one_policy)
    for package in context_packages:
        sources.context_packages.add(package)
    for package in work_packages:
        sources.work_packages.add(package)
    for one_strategy in strategies:
        sources.strategies.add(one_strategy)
    for one_artifact in artifacts:
        infrastructure.artifacts.add(one_artifact)
    return HarnessEnv(infrastructure=infrastructure, harness=harness)


def standard_env() -> HarnessEnv:
    """A common scenario: one Skill (needing one Capability), one Context, one Work Package."""
    return harness_env(
        skills=(skill("skill-investigate", capabilities=("cap-analysis",)),),
        capabilities=(capability("cap-analysis"),),
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1", skills=(ref("skill", "skill-investigate"),)),),
        strategies=(strategy(),),
    )
