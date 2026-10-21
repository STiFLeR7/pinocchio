"""PipelineBuilder -- assemble every existing engine over one shared substrate (Milestone 1).

The builder wires the ten implemented engines (Context Engineering, Planning, Orchestration,
Harness, Runtime, Execution, Validation, Recovery, Reflection, Knowledge) over a single
:class:`InfrastructureContext` and a single injected ``TimestampSource`` -- so every engine appends
to one authoritative event log and one deterministic clock (ADR-001, INV-17). It orchestrates
existing engines only; it contains **no business logic** and redesigns nothing.

A :class:`Pipeline` is one execution's wiring: engine ids are deterministic per Goal, so a pipeline
hosts one workflow execution. To carry learning across executions (Milestone 5), pass a shared
``knowledge_repositories`` so two pipelines serve and accept against the same durable Knowledge
store while keeping fully independent event logs.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_context import ContextEngineeringContext, build_context_engineering
from nexus_execution import ExecutionContext, build_execution
from nexus_harness import HarnessContext, build_harness
from nexus_infra import InfrastructureContext, InMemoryObservability, build_infrastructure
from nexus_knowledge import KnowledgeContextBundle, build_knowledge
from nexus_knowledge.persistence import KnowledgeRepositories
from nexus_knowledge.policy import DEFAULT_PERSISTENCE_POLICY, PersistencePolicy
from nexus_orchestration import (
    InMemoryHarnessRegistry,
    OrchestrationContext,
    build_orchestration,
)
from nexus_planning import (
    InMemoryCapabilityRegistry,
    PlanningContext,
    build_planning,
)
from nexus_recovery import RecoveryContextBundle, build_recovery
from nexus_reflection import ReflectionContextBundle, build_reflection
from nexus_runtime import RuntimeContext, build_runtime
from nexus_runtime.events import FixedTimestampSource, TimestampSource
from nexus_validation import ValidationContext, build_validation


@dataclass(frozen=True, slots=True)
class Pipeline:
    """The wired, shared-substrate assembly of every engine for one workflow execution."""

    infrastructure: InfrastructureContext
    timestamps: TimestampSource
    context: ContextEngineeringContext
    capability_registry: InMemoryCapabilityRegistry
    planning: PlanningContext
    harness_registry: InMemoryHarnessRegistry
    orchestration: OrchestrationContext
    harness: HarnessContext
    runtime: RuntimeContext
    execution: ExecutionContext
    validation: ValidationContext
    recovery: RecoveryContextBundle
    reflection: ReflectionContextBundle
    knowledge: KnowledgeContextBundle


class PipelineBuilder:
    """Wires all ten engines over one infrastructure + one deterministic clock (no logic)."""

    def __init__(
        self,
        *,
        timestamps: TimestampSource | None = None,
        knowledge_repositories: KnowledgeRepositories | None = None,
        knowledge_policy: PersistencePolicy = DEFAULT_PERSISTENCE_POLICY,
        require_knowledge_source_lineage: bool = True,
        infrastructure: InfrastructureContext | None = None,
    ) -> None:
        self._timestamps = timestamps or FixedTimestampSource()
        self._knowledge_repositories = knowledge_repositories
        self._knowledge_policy = knowledge_policy
        self._require_knowledge_source_lineage = require_knowledge_source_lineage
        # The durable seam (P13/F-2): when an infrastructure context is injected the pipeline wires
        # every engine over it instead of a fresh in-memory one, so a durable (ADR-007) log carries
        # the whole Goal→Knowledge run and a reopened file replays/restarts it. Default is unchanged.
        self._infrastructure = infrastructure

    def build(self) -> Pipeline:
        """Assemble a fresh pipeline; every engine shares one event log and one clock."""
        infra = self._infrastructure or build_infrastructure(observability=InMemoryObservability())
        ts = self._timestamps
        capability_registry = InMemoryCapabilityRegistry()
        harness_registry = InMemoryHarnessRegistry()
        return Pipeline(
            infrastructure=infra,
            timestamps=ts,
            context=build_context_engineering(infra, timestamps=ts),
            capability_registry=capability_registry,
            planning=build_planning(infra, capability_registry=capability_registry, timestamps=ts),
            harness_registry=harness_registry,
            orchestration=build_orchestration(
                infra, harness_registry=harness_registry, timestamps=ts
            ),
            harness=build_harness(infra, timestamps=ts),
            runtime=build_runtime(infra, harness_registry=harness_registry, timestamps=ts),
            execution=build_execution(infra, timestamps=ts),
            validation=build_validation(infra, timestamps=ts),
            recovery=build_recovery(infra, timestamps=ts),
            reflection=build_reflection(infra, timestamps=ts),
            knowledge=build_knowledge(
                infra,
                repositories=self._knowledge_repositories,
                timestamps=ts,
                policy=self._knowledge_policy,
                require_source_lineage=self._require_knowledge_source_lineage,
            ),
        )
