"""Planning inputs and outputs — the deterministic request/result models.

Phase 3 Planning contains no AI: the *decomposition* (which work items exist, how
they depend, what capabilities they need) arrives as an explicit, immutable
:class:`PlanningRequest`. Planning validates and assembles it into domain objects.
Because the request is a frozen value object, the same request always yields the
same Plan.
"""

from __future__ import annotations

from pydantic import Field

from nexus_core.contracts.base import Constraint, Reference, Struct, ValueObject
from nexus_core.contracts.enums import ApprovalTaxonomy, CoordinationModel, Priority, RetryBehavior
from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_core.domain.plan import Milestone, Plan
from nexus_core.domain.work_package import WorkPackage


class WorkItemSpec(ValueObject):
    """One declared unit of work the Goal decomposes into (the planning input atom).

    A spec is *what* the work is and *what it depends on* — never how/where it
    runs. ``key`` is a stable handle unique within the request; ``depends_on``
    references other items' keys (the authoritative ordering becomes graph edges,
    INV-10). Capabilities are abstract identifiers, resolved against the registry.
    """

    key: str
    objective: str
    capability_requirements: tuple[str, ...] = ()
    skill_refs: tuple[Reference, ...] = ()
    depends_on: tuple[str, ...] = ()
    inputs: tuple[Reference, ...] = ()
    outputs: tuple[Struct, ...] = ()
    constraints: tuple[Constraint, ...] = ()
    evidence: Struct = Field(default_factory=dict)
    completion_criteria: Struct = Field(default_factory=dict)
    priority: Priority | None = None
    requires_approval: bool = False
    is_checkpoint: bool = False
    condition: str | None = None
    """A deterministic predicate gating this item's inbound edges (conditional flow)."""


class PlanningRequest(ValueObject):
    """The complete, immutable input to one planning cycle for a Goal."""

    work_items: tuple[WorkItemSpec, ...]
    approach_summary: str = "Decompose the goal into independently executable work."
    rationale: str = "Derived deterministically from the declared work decomposition."
    dependency_summary: str = "Dependencies are expressed as Execution Graph edges (INV-10)."
    milestones: tuple[Milestone, ...] = ()
    coordination_hint: CoordinationModel | None = None
    """Optional explicit coordination model; otherwise derived from the topology."""
    context_ref: Reference | None = None
    """By-reference pointer to the operational context (ADR-003 §7); Planning never builds it."""
    correlation_identifier: str | None = None
    plan_version: str = "1"
    assumptions: tuple[str, ...] = ()
    operational_risks: tuple[Struct, ...] = ()

    # --- constitutional postures supplied by Engineering Intelligence (P6) --- #
    # When present these are *consumed* (never derived): EI owns the engineering decision, Planning
    # decomposes within it. Absent (operator-authored path), the existing derivation applies as a
    # backward-compatible fallback. See ``nexus_planning.strategy_binding``.
    approval_hint: ApprovalTaxonomy | None = None
    """Approval posture from EI's autonomy level (else derived from the work items)."""
    retry_hint: RetryBehavior | None = None
    """Retry/recovery bias from EI's recovery posture (else NEVER_RETRY)."""
    validation_policy: Struct | None = None
    """Validation rigor + mandatory evidence classes from EI (else empty)."""
    recovery_policy: Struct | None = None
    """Recovery posture detail from EI (else empty)."""
    runtime_policy: Struct | None = None
    """Runtime capability preferences from EI (capabilities, not providers — INV-37; else empty)."""
    engineering_strategy_ref: Reference | None = None
    """Provenance: the EngineeringStrategy this request consumed (by id)."""


class CapabilityRequirementSet(ValueObject):
    """The result of capability resolution — requirements/candidates only (INV-37).

    Planning declares *what* capabilities the work requires and which are known to
    the registry; it never selects a provider or runtime. ``missing`` names
    required capabilities the registry could not resolve (an operational risk).
    """

    required: tuple[str, ...]
    resolved: tuple[Reference, ...]
    missing: tuple[str, ...]


class PlanningResult(ValueObject):
    """The complete output of a planning cycle — immutable, ready for Orchestration."""

    plan: Plan
    work_packages: tuple[WorkPackage, ...]
    execution_graph: ExecutionGraph
    execution_strategy: ExecutionStrategy
    capabilities: CapabilityRequirementSet
