"""Human-Interaction composition — wire the operator façade over the constitutional pipeline.

Additive DI wiring only: it builds the P13/P14 :class:`~nexus_workflows.spine.ConstitutionalPipeline`
(learning-on by default) and the :class:`HumanInteraction` façade over the *same* infrastructure and
clock, so operator ``interaction.*`` facts share the one durable log with the constitutional owners. It
introduces no engine and modifies no owner.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from nexus_approval import ApprovalExchange, build_approval_exchange
from nexus_engineering.reasoner import Reasoner
from nexus_human_interaction.facade import HumanInteraction
from nexus_human_interaction.observability import OperatorObservability
from nexus_infra import InfrastructureContext
from nexus_knowledge.persistence import KnowledgeRepositories
from nexus_runtime.events import FixedTimestampSource, TimestampSource
from nexus_workflows.spine import SpinePipelineContext, build_constitutional_pipeline
from nexus_workflows.spine.coordinator import AdapterFactory


@dataclass(frozen=True, slots=True)
class HumanInteractionContext:
    """The wired operator surface (immutable wiring; stateful façade + pipeline + approval exchange)."""

    infrastructure: InfrastructureContext
    spine: SpinePipelineContext
    approval: ApprovalExchange
    facade: HumanInteraction


def build_human_interaction(
    infrastructure: InfrastructureContext,
    *,
    timestamps: TimestampSource | None = None,
    adapter_factory: AdapterFactory | None = None,
    knowledge_repositories: KnowledgeRepositories | None = None,
    learning: bool = True,
    action_command_allowlist: Mapping[str, tuple[str, ...]] | None = None,
    action_artifact_directory: str | None = None,
    engineering_reasoner: Reasoner | None = None,
) -> HumanInteractionContext:
    """Wire the operator façade over the constitutional pipeline (durable-capable, learning-on).

    ``adapter_factory`` is forwarded unchanged to :func:`build_constitutional_pipeline` (the same
    seam every existing runtime swap already uses — see ``examples/04-runtime-selection``); left
    ``None``, behavior is exactly as before this parameter existed (the default Claude adapter).

    Also wires the P15 Approval Exchange over the *same* pipeline + infrastructure + clock, so the façade
    can surface and coordinate approvals through it (never bypassing it) on one shared durable log.
    """
    ts = timestamps or FixedTimestampSource()
    spine = build_constitutional_pipeline(
        infrastructure,
        timestamps=ts,
        adapter_factory=adapter_factory,
        knowledge_repositories=knowledge_repositories,
        learning=learning,
        action_command_allowlist=action_command_allowlist,
        action_artifact_directory=action_artifact_directory,
        engineering_reasoner=engineering_reasoner,
    )
    approval = build_approval_exchange(spine.coordinator, infrastructure, now=ts.now)
    facade = HumanInteraction(
        spine.coordinator,
        infrastructure,
        approval,
        now=ts.now,
        observability=OperatorObservability(infrastructure.observability),
    )
    return HumanInteractionContext(
        infrastructure=infrastructure, spine=spine, approval=approval, facade=facade
    )
