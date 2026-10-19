"""``nexus_human_interaction`` — the first constitutional Human Interaction surface (P14/B).

A **façade** over the constitutional platform, not a UI framework. An operator submits a Goal, inspects
pipeline status / execution history / execution graph / Knowledge, replays and restarts sessions, and has
execution lineage explained — and every operation invokes **only** the
:class:`~nexus_workflows.spine.ConstitutionalPipeline`. No engine is directly user-callable; the façade
owns request translation, response formatting, session lookup, and progress reporting, and owns **no
reasoning**. It records its own durable ``interaction.*`` facts (producer ``human_interaction``) so an
operator session replays exactly and a restart resumes without replaying completed constitutional stages.

Dependency direction is one-way: ``nexus_human_interaction → {nexus_workflows.spine, nexus_core,
nexus_infra}``; it imports and orchestrates no engine, introduces no contract/ADR/invariant, and modifies
no owner.
"""

from __future__ import annotations

from nexus_human_interaction.composition import (
    HumanInteractionContext,
    build_human_interaction,
)
from nexus_human_interaction.events import (
    INTERACTION_PRODUCER,
    INTERACTION_REQUEST_SUBMITTED,
    INTERACTION_RESPONSE_RECORDED,
    INTERACTION_RESUMED,
    INTERACTION_SESSION_STARTED,
)
from nexus_human_interaction.facade import HumanInteraction
from nexus_human_interaction.model import (
    ExecutionGraphView,
    InteractionResponse,
    InteractionSession,
    InteractionStatus,
    KnowledgeView,
    LineageView,
    OperatorRequest,
)
from nexus_human_interaction.reference import reference_operator_request
from nexus_human_interaction.session import reconstruct_interaction_session

__version__ = "2.5.0"

__all__ = [
    "INTERACTION_PRODUCER",
    "INTERACTION_REQUEST_SUBMITTED",
    "INTERACTION_RESPONSE_RECORDED",
    "INTERACTION_RESUMED",
    "INTERACTION_SESSION_STARTED",
    "ExecutionGraphView",
    "HumanInteraction",
    "HumanInteractionContext",
    "InteractionResponse",
    "InteractionSession",
    "InteractionStatus",
    "KnowledgeView",
    "LineageView",
    "OperatorRequest",
    "build_human_interaction",
    "reconstruct_interaction_session",
    "reference_operator_request",
]
