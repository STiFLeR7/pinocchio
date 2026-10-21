"""``nexus_context.grounding`` — P9 grounding-aware context assembly (additive).

Context Engineering is the constitutional **Contextualize** owner (`nexus_context`),
the *only* producer of the frozen :class:`~nexus_core.domain.context_package.ContextPackage`
(INV-02, INV-07; contract ``context_package.md`` — "the only producer of this object").
This submodule does **not** create a second producer. It makes the incumbent producer
*grounding-aware*: it consumes the new grounding/reasoning artifacts —
**RepositoryProfile** (P7), **ExecutionHistoryProfile** (P8), the **EngineeringStrategy**'s
*context objectives* (P5), and **Knowledge** (INV-06, read-only) — performs deterministic,
explainable relevance **selection**, and feeds the selected facts to the incumbent
:class:`~nexus_context.service.ContextEngineeringService`, which packages and persists the
one Context Package (the P9 "ExecutionContext").

The whole assembly is deterministic and explainable: every inclusion *and every omission*
carries why-selected / source / relationship / priority, recorded as a
``context.grounding.selected`` fact; the assembled package is recorded in
``context.grounding.assembled`` so replay reconstructs the grounded context without
rebuilding. No AI, no embeddings, no semantic search — only deterministic heuristics over
recorded facts.

Dependency direction is one-way: ``nexus_context.grounding → {nexus_context, nexus_core,
nexus_infra}`` plus **read-only, by-value** consumption of the upstream grounding value
objects (``nexus_repository``, ``nexus_history``, ``nexus_engineering`` models,
``nexus_core.domain.knowledge``). It imports no downstream engine and mutates none of its
inputs.
"""

from __future__ import annotations

from nexus_context.grounding.assembler import (
    GroundingAssembler,
    GroundingObservability,
)
from nexus_context.grounding.collectors import grounding_collectors
from nexus_context.grounding.composition import (
    GroundedContextEngineeringContext,
    build_grounded_context_engineering,
)
from nexus_context.grounding.model import (
    GroundedContextResult,
    GroundingInputs,
    GroundingSelection,
    SelectionRecord,
)
from nexus_context.grounding.selection import GroundingSelector

__all__ = [
    "GroundedContextEngineeringContext",
    "GroundedContextResult",
    "GroundingAssembler",
    "GroundingInputs",
    "GroundingObservability",
    "GroundingSelection",
    "GroundingSelector",
    "SelectionRecord",
    "build_grounded_context_engineering",
    "grounding_collectors",
]
