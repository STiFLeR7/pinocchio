"""``nexus_workflows.spine`` — the Constitutional Spine: one durable Goal→Knowledge pipeline (P13).

The constitutional capabilities exist independently (P0-P11) and were validated as a coherent platform
(P12). This subsystem **fuses** them into a single deterministic pipeline while preserving every owner::

    Intent → Engineering → Context → Planning → Execution Actuation
        → [Execution→Validation seam] → Validation → Recovery → Reflection → Knowledge

It owns the *orchestration of the constitutional stages only* (the additive ``pipeline.*`` events); it
owns none of their behavior. It closes the three P12 findings additively — F-1 (one unified driver, no
competing coordinator), F-2 (one durable pipeline session that restarts from the last completed
constitutional boundary), F-3 (a pure ExecutionState→ExecutionResult projection so Execution Actuation
hands off cleanly to Validation). It redesigns nothing and modifies no owner, ADR, contract, or invariant.
"""

from __future__ import annotations

from nexus_workflows.spine.bridge import execution_results
from nexus_workflows.spine.composition import (
    SpinePipelineContext,
    build_constitutional_pipeline,
)
from nexus_workflows.spine.coordinator import (
    ConstitutionalPipeline,
    PipelineObservability,
    find_execution_state,
    find_goal,
    find_plan,
    find_strategy,
    reconstruct_pipeline_session,
)
from nexus_workflows.spine.events import (
    PIPELINE_COMPLETED,
    PIPELINE_PAUSED,
    PIPELINE_PRODUCER,
    PIPELINE_RESUMED,
    PIPELINE_STAGE_COMPLETED,
    PIPELINE_STAGE_STARTED,
    PIPELINE_STARTED,
)
from nexus_workflows.spine.model import (
    ORDERED_STAGES,
    PipelineSession,
    SpineControl,
    SpineRequest,
    SpineRun,
    SpineStage,
    SpineStatus,
)
from nexus_workflows.spine.reference import spine_reference_request
from nexus_workflows.spine.serialization import dump_spine_request, load_spine_request

__all__ = [
    "ORDERED_STAGES",
    "PIPELINE_COMPLETED",
    "PIPELINE_PAUSED",
    "PIPELINE_PRODUCER",
    "PIPELINE_RESUMED",
    "PIPELINE_STAGE_COMPLETED",
    "PIPELINE_STAGE_STARTED",
    "PIPELINE_STARTED",
    "ConstitutionalPipeline",
    "PipelineObservability",
    "PipelineSession",
    "SpineControl",
    "SpinePipelineContext",
    "SpineRequest",
    "SpineRun",
    "SpineStage",
    "SpineStatus",
    "build_constitutional_pipeline",
    "dump_spine_request",
    "execution_results",
    "find_execution_state",
    "find_goal",
    "find_plan",
    "find_strategy",
    "load_spine_request",
    "reconstruct_pipeline_session",
    "spine_reference_request",
]
