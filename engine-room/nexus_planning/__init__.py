"""``nexus_planning`` — Phase 3 Planning Layer for Nexus v2.

The first operational-intelligence component built on the infrastructure
substrate (``nexus_infra``). Planning converts a validated **Goal** into a
complete, immutable, deterministic execution structure: a **Plan**, its **Work
Packages**, an **Execution Graph**, an **Execution Strategy**, and a **Capability
requirement set**.

Planning **prepares** work; it never performs it. Per the architectural
invariants it never executes, supervises, validates, selects a runtime, allocates
a provider, or performs recovery (INV-03, INV-37). Those belong to later phases.

Determinism is a hard requirement: identical Goals with identical planning inputs
produce byte-identical Plans, Work Packages, and Execution Graphs. There is no AI
reasoning, prompt engineering, or LLM call here — the decomposition arrives as
explicit structured input and Planning assembles it mechanically. The seam for a
future intelligent decomposer is :class:`~nexus_planning.decomposition.DecompositionStrategy`.

Dependency direction is one-way: ``nexus_planning → {nexus_infra, nexus_core}``.
"""

from __future__ import annotations

from nexus_planning.capability_resolver import (
    CapabilityResolver,
    InMemoryCapabilityRegistry,
)
from nexus_planning.composition import PlanningContext, build_planning
from nexus_planning.decomposition import (
    DecompositionStrategy,
    ExplicitDecompositionStrategy,
)
from nexus_planning.events import (
    FixedTimestampSource,
    SystemTimestampSource,
    TimestampSource,
)
from nexus_planning.execution_graph_builder import ExecutionGraphBuilder
from nexus_planning.plan_builder import PlanBuilder
from nexus_planning.planner import PlanningRepositories, PlanningService
from nexus_planning.requests import (
    CapabilityRequirementSet,
    PlanningRequest,
    PlanningResult,
    WorkItemSpec,
)
from nexus_planning.strategy_assigner import StrategyAssigner
from nexus_planning.strategy_binding import bind_strategy, strategy_hints
from nexus_planning.validators import (
    CyclicGraphError,
    DanglingReferenceError,
    GoalNotPlannableError,
    InvalidDecompositionError,
    PlanningError,
    validate_acyclic,
    validate_goal,
    validate_outputs,
    validate_request,
)
from nexus_planning.work_package_generator import WorkPackageGenerator

__version__ = "2.5.0"

__all__ = [
    "CapabilityRequirementSet",
    "CapabilityResolver",
    "CyclicGraphError",
    "DanglingReferenceError",
    "DecompositionStrategy",
    "ExecutionGraphBuilder",
    "ExplicitDecompositionStrategy",
    "FixedTimestampSource",
    "GoalNotPlannableError",
    "InMemoryCapabilityRegistry",
    "InvalidDecompositionError",
    "PlanBuilder",
    "PlanningContext",
    "PlanningError",
    "PlanningRepositories",
    "PlanningRequest",
    "PlanningResult",
    "PlanningService",
    "StrategyAssigner",
    "SystemTimestampSource",
    "TimestampSource",
    "WorkItemSpec",
    "WorkPackageGenerator",
    "bind_strategy",
    "build_planning",
    "strategy_hints",
    "validate_acyclic",
    "validate_goal",
    "validate_outputs",
    "validate_request",
]
