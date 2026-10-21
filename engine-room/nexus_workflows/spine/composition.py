"""Constitutional-pipeline composition — wire the whole spine over one shared infrastructure.

Assembles the single Goal→Knowledge driver additively from existing composition roots, all over one
:class:`~nexus_infra.InfrastructureContext` (durable transparently over ``build_durable_infrastructure``
— ADR-007), so every constitutional owner appends to one authoritative log and one injected clock:

* the front reasoning owners — Intent, Engineering, Estimation, Policy (``now``-clocked);
* grounded Planning (P10) — consumes the Engineering Strategy + Context Package by value;
* the incumbent :class:`~nexus_workflows.pipeline.Pipeline` — **reused** (via the F-2 durable seam) for
  Context Engineering and the Validate→Learn back chain (Validation/Recovery/Reflection/Knowledge);
* Execution Actuation (P11) — built per run by the coordinator, so a restart re-registers its runtime
  over the reopened log.

It redesigns nothing and modifies no owner: it is DI wiring only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from nexus_context.grounding import (
    GroundedContextEngineeringContext,
    build_grounded_context_engineering,
)
from nexus_engineering import EngineeringContext, build_engineering
from nexus_engineering.reasoner import Reasoner
from nexus_estimation import build_estimation
from nexus_execution.adapter import RuntimeAdapter
from nexus_infra import InfrastructureContext
from nexus_intent import build_intent
from nexus_knowledge.persistence import KnowledgeRepositories
from nexus_knowledge.policy import DEFAULT_PERSISTENCE_POLICY, PersistencePolicy
from nexus_planning.grounded import GroundedPlanningContext, build_grounded_planning
from nexus_policy import PolicyContext, build_policy
from nexus_runtime.events import FixedTimestampSource, TimestampSource
from nexus_runtime_claude import ClaudeRuntimeAdapter, StubClaudeInvoker
from nexus_workflows.pipeline import Pipeline, PipelineBuilder
from nexus_workflows.spine.coordinator import (
    AdapterFactory,
    ConstitutionalPipeline,
    PipelineObservability,
)
from nexus_workflows.spine.learning import KnowledgeSelector, knowledge_grounding_baseline
from nexus_workflows.spine.model import SpineRequest


def _default_adapter_factory(request: SpineRequest) -> RuntimeAdapter:
    """The default runtime: Claude, honoring the request's failure-path selection (the one seam)."""
    return ClaudeRuntimeAdapter(invoker=StubClaudeInvoker(fail=request.fail))


@dataclass(frozen=True, slots=True)
class SpinePipelineContext:
    """The wired constitutional pipeline (immutable wiring; stateful coordinator + owners)."""

    infrastructure: InfrastructureContext
    pipeline: Pipeline
    engineering: EngineeringContext
    grounded_context: GroundedContextEngineeringContext
    planning: GroundedPlanningContext
    policy: PolicyContext
    coordinator: ConstitutionalPipeline


def build_constitutional_pipeline(
    infrastructure: InfrastructureContext,
    *,
    timestamps: TimestampSource | None = None,
    adapter_factory: AdapterFactory | None = None,
    knowledge_repositories: KnowledgeRepositories | None = None,
    knowledge_policy: PersistencePolicy = DEFAULT_PERSISTENCE_POLICY,
    learning: bool = True,
    action_command_allowlist: Mapping[str, tuple[str, ...]] | None = None,
    action_artifact_directory: str | None = None,
    engineering_reasoner: Reasoner | None = None,
) -> SpinePipelineContext:
    """Wire the single Goal→Knowledge pipeline over one infrastructure context (durable-capable).

    ``learning`` (P14/A) enables the governed Knowledge grounding loop (Knowledge → Engineering →
    Context → Planning): it registers the overridable ``knowledge_grounding`` allow-baseline and wires
    the deterministic selector. With ``learning=False`` the pipeline is the P13 driver unchanged.
    """
    ts = timestamps or FixedTimestampSource()
    now = ts.now

    # Reuse the incumbent pipeline over the injected infra (F-2 durable seam) for the back chain.
    pipeline = PipelineBuilder(
        timestamps=ts,
        knowledge_repositories=knowledge_repositories,
        knowledge_policy=knowledge_policy,
        infrastructure=infrastructure,
    ).build()

    intent = build_intent(infrastructure, now=now)
    engineering = build_engineering(infrastructure, reasoner=engineering_reasoner, now=now)
    estimation = build_estimation(infrastructure, now=now)
    policy = build_policy(infrastructure, now=now)
    # Context becomes grounding-aware (P9 path) so Knowledge can flow into it (INV-06, read-only).
    grounded_context = build_grounded_context_engineering(infrastructure, timestamps=ts)
    planning = build_grounded_planning(infrastructure, timestamps=ts)

    selector: KnowledgeSelector | None = None
    if learning:
        policy.registry.register(
            knowledge_grounding_baseline()
        )  # governed on, overridable by a deny
        selector = KnowledgeSelector(pipeline.knowledge.engine, policy.engine)

    coordinator = ConstitutionalPipeline(
        infrastructure,
        intent=intent,
        engineering=engineering,
        estimation=estimation,
        policy=policy,
        grounded_context=grounded_context,
        planning=planning,
        validation=pipeline.validation,
        recovery=pipeline.recovery,
        reflection=pipeline.reflection,
        knowledge=pipeline.knowledge,
        adapter_factory=adapter_factory or _default_adapter_factory,
        action_command_allowlist=action_command_allowlist,
        action_artifact_directory=action_artifact_directory,
        selector=selector,
        timestamps=ts,
        now=now,
        observability=PipelineObservability(infrastructure.observability),
    )
    return SpinePipelineContext(
        infrastructure=infrastructure,
        pipeline=pipeline,
        engineering=engineering,
        grounded_context=grounded_context,
        planning=planning,
        policy=policy,
        coordinator=coordinator,
    )
