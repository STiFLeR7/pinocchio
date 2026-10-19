"""Shared, deterministic builders for the orchestration test suite.

A single source of truth for constructing Execution Graphs, Execution Strategies,
orchestration requests, harness descriptors, and a fully-wired orchestration
environment with a fixed timestamp source — so orchestration tests read as intent
and stay reproducible. Graphs are built directly (no dependency on Planning's
correctness); node ids follow Planning's ``node-{key}`` convention.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from nexus_core.contracts.base import Constraint, Correlation, Reference, Struct
from nexus_core.contracts.enums import (
    ApprovalTaxonomy,
    CoordinationModel,
    EdgeType,
    RetryBehavior,
)
from nexus_core.domain.execution_graph import ExecutionGraph, GraphEdge, GraphNode
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_core.registries.interfaces import HarnessCategory, HarnessDescriptor
from nexus_infra import InfrastructureContext, build_infrastructure
from nexus_orchestration import (
    FixedTimestampSource,
    InMemoryHarnessRegistry,
    OrchestrationContext,
    OrchestrationRequest,
    build_orchestration,
)


def gnode(
    key: str,
    *,
    work_package: str | None = None,
    capabilities: Sequence[str] = (),
    skills: Sequence[Reference] = (),
    context: str | None = "context-goal-1",
    approval: bool = False,
    strategy_ref: Reference | None = None,
) -> GraphNode:
    """Build a :class:`GraphNode` (id ``node-{key}``) with optional capabilities/approval."""
    capability_refs = tuple(
        Reference(target_type="capability", identifier=cap) for cap in capabilities
    )
    constraints: tuple[Constraint, ...] = (Constraint(kind="approval"),) if approval else ()
    return GraphNode(
        identifier=f"node-{key}",
        work_package_ref=Reference(
            target_type="work_package", identifier=work_package or f"wp-goal-1-{key}"
        ),
        execution_strategy_ref=strategy_ref,
        required_skill_refs=(*skills, *capability_refs),
        required_context_ref=(
            Reference(target_type="context_package", identifier=context) if context else None
        ),
        constraints=constraints,
    )


def gedge(
    source_key: str, target_key: str, *, edge_type: EdgeType = EdgeType.EXECUTION
) -> GraphEdge:
    """Build a :class:`GraphEdge` between ``node-{source_key}`` and ``node-{target_key}``."""
    source = f"node-{source_key}"
    target = f"node-{target_key}"
    return GraphEdge(
        identifier=f"edge-{source}->{target}:{edge_type.value}",
        edge_type=edge_type,
        source_node=source,
        target_node=target,
    )


def make_graph(
    nodes: Iterable[GraphNode],
    edges: Iterable[GraphEdge] = (),
    *,
    goal: str = "goal-1",
    plan: str = "plan-goal-1-v1",
    version: str = "1",
    coordination: str = "sequential",
    approval_gates: Sequence[str] = (),
    synchronization_points: Sequence[str] = (),
    checkpoints: Sequence[Reference] = (),
    loops: Sequence[Struct] = (),
    correlation: str | None = None,
) -> ExecutionGraph:
    """Build a deterministic :class:`ExecutionGraph` mirroring Planning's output shape."""
    node_tuple = tuple(nodes)
    edge_tuple = tuple(edges)
    return ExecutionGraph(
        identity=f"graph-{goal}-v{version}",
        parent_goal=Reference(target_type="goal", identifier=goal),
        parent_plan=Reference(target_type="plan", identifier=plan),
        version=version,
        nodes=node_tuple,
        edges=edge_tuple,
        conditions=(),
        checkpoints=tuple(checkpoints),
        policies={
            "coordination": coordination,
            "approval_gates": list(approval_gates),
            "synchronization_points": list(synchronization_points),
        },
        metadata={
            "goal": goal,
            "plan": plan,
            "version": version,
            "node_count": len(node_tuple),
            "edge_count": len(edge_tuple),
        },
        correlation=(
            Correlation(correlation_identifier=correlation) if correlation is not None else None
        ),
        loops=tuple(loops),
    )


def make_strategy(
    identity: str = "strategy-goal-1-v1",
    *,
    coordination: CoordinationModel = CoordinationModel.SEQUENTIAL,
    approval_policy: ApprovalTaxonomy = ApprovalTaxonomy.AUTOMATIC,
    runtime_policy: Struct | None = None,
    correlation: str | None = None,
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
        correlation=(
            Correlation(correlation_identifier=correlation) if correlation is not None else None
        ),
    )


def make_request(
    graph: ExecutionGraph,
    strategy: ExecutionStrategy,
    *,
    context_ref: Reference | None = None,
    completed_nodes: tuple[str, ...] = (),
    paused_nodes: tuple[str, ...] = (),
    approved_gates: tuple[str, ...] = (),
    rejected_gates: tuple[str, ...] = (),
    correlation_identifier: str | None = None,
    session_version: str = "1",
) -> OrchestrationRequest:
    """Build an :class:`OrchestrationRequest` from a graph + strategy and any overrides."""
    return OrchestrationRequest(
        execution_graph=graph,
        execution_strategy=strategy,
        context_ref=context_ref,
        completed_nodes=completed_nodes,
        paused_nodes=paused_nodes,
        approved_gates=approved_gates,
        rejected_gates=rejected_gates,
        correlation_identifier=correlation_identifier,
        session_version=session_version,
    )


def harness(
    identity: str, *, capabilities: Sequence[str] = (), category: HarnessCategory | None = None
) -> HarnessDescriptor:
    """Build a :class:`HarnessDescriptor` advertising the given capabilities."""
    return HarnessDescriptor(
        identity=identity,
        category=category or HarnessCategory.RUNTIME,
        version="1",
        advertised_capabilities=tuple(
            Reference(target_type="capability", identifier=cap) for cap in capabilities
        ),
    )


@dataclass(frozen=True, slots=True)
class OrchestrationEnv:
    """A wired infrastructure + orchestration pair for a test."""

    infrastructure: InfrastructureContext
    orchestration: OrchestrationContext


def orchestration_env(*harnesses: HarnessDescriptor) -> OrchestrationEnv:
    """Build a fresh, deterministic orchestration environment with registered harnesses."""
    infrastructure = build_infrastructure()
    registry = InMemoryHarnessRegistry()
    for descriptor in harnesses:
        registry.register(descriptor)
    orchestration = build_orchestration(
        infrastructure,
        harness_registry=registry,
        timestamps=FixedTimestampSource(),
    )
    return OrchestrationEnv(infrastructure=infrastructure, orchestration=orchestration)
