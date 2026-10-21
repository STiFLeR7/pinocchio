"""Grounded planning value models — the immutable inputs and the assembled ExecutionPlan.

:class:`PlanningInputs` is the read-only bundle of the three canonical inputs (Goal +
EngineeringStrategy + ContextPackage, all consumed by value). :class:`ExecutionPlan` is the P10
output: the frozen ``Plan`` (which references its sibling Execution Graph by id and owns its Work
Packages — INV-10) bundled with the Execution Strategy, resolved capabilities, a deterministic
:class:`CoordinationView`, and the context references, as a frozen **value** — not a second Plan
schema (INV-07). It serializes into a ``planning.execution_plan_assembled`` fact so replay
reconstructs it without re-planning.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from nexus_core.contracts.base import Reference, ValueObject
from nexus_core.domain.context_package import ContextPackage
from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_core.domain.goal import Goal
from nexus_core.domain.plan import Plan
from nexus_core.domain.work_package import WorkPackage
from nexus_engineering.model import EngineeringStrategy
from nexus_planning.requests import CapabilityRequirementSet, WorkItemSpec


@dataclass(frozen=True, slots=True)
class PlanningInputs:
    """The immutable, read-only bundle Planning consumes (Goal + Strategy + Context, by value).

    Only ``goal`` is required; ``engineering_strategy`` and ``context_package`` are absence-tolerant
    (an un-reasoned or un-grounded goal still plans, using the incumbent's derivations). ``work_items``
    is the declared work decomposition; when empty, Planning produces the atomic single-package plan
    for the Goal's objective — it never *invents* sub-tasks (that would be reasoning).
    """

    goal: Goal
    engineering_strategy: EngineeringStrategy | None = None
    context_package: ContextPackage | None = None
    work_items: tuple[WorkItemSpec, ...] = field(default_factory=tuple)
    operator_steps: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    operator_step_template: WorkItemSpec | None = None
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    repository_profile_ref: Reference | None = None


class CoordinationView(ValueObject):
    """A deterministic coordination analysis of the Execution Graph (facts only, no reasoning).

    Every field is a pure function of the frozen Execution Graph's nodes/edges plus the Execution
    Strategy — the authoritative topology stays in the graph's edges (INV-10); this view *reads* them.
    ``dependency_edges`` is the "Dependency Graph" as edges (source → target); ``parallel_groups`` are
    the topological levels with more than one node (fan-out concurrency); ``sequential_levels`` is the
    full ordered level sequence (the dependency barriers between them); ``merge_boundaries`` are fan-in
    nodes; ``checkpoint``/``approval``/``recovery`` boundaries are the governed points on the graph.
    """

    coordination_model: str
    dependency_edges: tuple[tuple[str, str], ...]
    parallel_groups: tuple[tuple[str, ...], ...]
    sequential_levels: tuple[tuple[str, ...], ...]
    fan_out_points: tuple[str, ...]
    merge_boundaries: tuple[str, ...]
    checkpoint_boundaries: tuple[str, ...]
    approval_boundaries: tuple[str, ...]
    recovery_boundaries: tuple[str, ...]


class ExecutionPlan(ValueObject):
    """The one immutable P10 artifact: the frozen Plan + its executable topology, bundled by value.

    Not a new domain object — a frozen value bundling the frozen ``Plan`` (INV-07), its sibling
    ``ExecutionGraph`` (referenced by the Plan, never nested — INV-10), the owned ``WorkPackage`` set,
    the governing ``ExecutionStrategy``, resolved capabilities, the deterministic coordination view,
    and the context references. ``identity`` is the Plan's identity, so the ExecutionPlan is addressable
    and correlatable.
    """

    identity: str
    goal_ref: Reference
    plan: Plan
    work_packages: tuple[WorkPackage, ...]
    execution_graph: ExecutionGraph
    execution_strategy: ExecutionStrategy
    capabilities: CapabilityRequirementSet
    coordination: CoordinationView
    context_references: tuple[Reference, ...]
    correlation_identifier: str = ""
