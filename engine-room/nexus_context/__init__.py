"""``nexus_context`` — Phase 4 Context Engineering Layer for Nexus v2.

The first half of the operational-intelligence pipeline. Context Engineering
transforms incomplete operator intent (a **Goal**) plus available operational
information into a single, immutable, validated **Context Package** that Planning
consumes. The pipeline becomes::

    Goal → Context Engineering → Context Package → Planning → …

so Planning no longer operates on a raw Goal — it consumes validated context
(referenced via ``PlanningRequest.context_ref``; see :func:`context_reference`).

It does one job: discover, normalize, detect conflicts in, rank, validate the
freshness of, and package context. It never plans, selects a runtime, executes,
validates execution, invokes an AI provider, or mutates Knowledge (doc 03
*Architectural Boundaries*; INV-06).

Determinism is a hard requirement: identical Goals with identical inputs produce
byte-identical Context Packages. There is no AI reasoning, prompt engineering, or
LLM call here — raw context arrives as explicit structured input (surfaced by
injected collectors) and is assembled mechanically. The seam for real source
collectors is :class:`~nexus_context.collectors.ContextCollector`.

Dependency direction is one-way: ``nexus_context → {nexus_infra, nexus_core}``. It
never imports ``nexus_planning`` — Context Engineering is *upstream* of Planning.
"""

from __future__ import annotations

from nexus_context.builder import ContextPackageBuilder
from nexus_context.categories import (
    ConflictKind,
    ContextCategory,
    ContextSource,
    FreshnessState,
)
from nexus_context.collectors import (
    ContextCollector,
    GoalContextCollector,
    RequestFragmentCollector,
    StaticContextCollector,
)
from nexus_context.composition import (
    ContextEngineeringContext,
    build_context_engineering,
    default_collectors,
)
from nexus_context.conflict_detector import ConflictDetector
from nexus_context.events import (
    FixedTimestampSource,
    SystemTimestampSource,
    TimestampSource,
)
from nexus_context.freshness import FreshnessValidator
from nexus_context.normalizer import Normalizer
from nexus_context.relevance import RelevanceRanker
from nexus_context.requests import (
    Conflict,
    ContextItem,
    ContextRequest,
    ContextResult,
    FreshnessPolicy,
    RawContextFragment,
    context_reference,
)
from nexus_context.service import ContextEngineeringService, ContextRepositories
from nexus_context.validators import (
    ContextError,
    ContextValidationError,
    GoalNotContextualizableError,
    InvalidContextError,
    compute_validation_status,
    validate_goal,
    validate_outputs,
    validate_request,
)

__version__ = "2.5.0"

__all__ = [
    "Conflict",
    "ConflictDetector",
    "ConflictKind",
    "ContextCategory",
    "ContextCollector",
    "ContextEngineeringContext",
    "ContextEngineeringService",
    "ContextError",
    "ContextItem",
    "ContextPackageBuilder",
    "ContextRepositories",
    "ContextRequest",
    "ContextResult",
    "ContextSource",
    "ContextValidationError",
    "FixedTimestampSource",
    "FreshnessPolicy",
    "FreshnessState",
    "FreshnessValidator",
    "GoalContextCollector",
    "GoalNotContextualizableError",
    "InvalidContextError",
    "Normalizer",
    "RawContextFragment",
    "RelevanceRanker",
    "RequestFragmentCollector",
    "StaticContextCollector",
    "SystemTimestampSource",
    "TimestampSource",
    "build_context_engineering",
    "compute_validation_status",
    "context_reference",
    "default_collectors",
    "validate_goal",
    "validate_outputs",
    "validate_request",
]
