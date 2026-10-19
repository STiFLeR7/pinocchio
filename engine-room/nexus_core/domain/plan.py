"""Plan — the abstract operational approach for achieving a single Goal.

Contract: ``contracts/plan.md``. Produced by Planning. Binding: ADR-003 (§3.3
Plan/Execution Graph separation), ADR-001 (state is projection). Invariants:
INV-03/INV-08 (approach, never procedure-as-execution nor outcome redefinition),
INV-07, INV-10 (the Execution Graph is a sibling artifact referenced, never
nested; ``dependency_summary`` is a summary, not an authoritative graph),
INV-13/14/15.

The Plan records milestones, priorities, a dependency summary, and rationale,
and points to the concrete topology (Execution Graph) and executable units (Work
Packages) without containing their stateful machinery.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from nexus_core.contracts.base import Correlation, DomainObject, Reference, Struct, ValueObject
from nexus_core.contracts.status import PlanStatus


class Milestone(ValueObject):
    """A measurable progress marker: its identity, meaning, and completion condition."""

    identifier: str
    """Stable identifier of this milestone within the Plan."""
    meaning: str
    """What reaching this milestone signifies operationally."""
    completion_condition: str
    """The observable condition that marks this milestone reached."""


class Plan(DomainObject):
    """The strategic approach for one Goal (contract: plan.md). Never a procedure."""

    LIFECYCLE_NAME: ClassVar[str] = "plan"

    # --- required ---------------------------------------------------------- #
    identity: str = Field(min_length=1)
    """Stable, unique identifier; participates in correlation/trace lineage."""
    parent_goal: Reference
    """Reference (by id) to the Goal this Plan serves (exactly one Goal per Plan)."""
    version: str
    """Monotonic version of the approach for this Goal (supports supersession)."""
    approach_summary: str
    """Declarative description of the chosen strategic approach and why it was selected."""
    milestones: tuple[Milestone, ...]
    """Ordered set of measurable progress markers."""
    priorities: Struct
    """Relative priority ordering Planning assigned across the work; never selects runtimes."""
    dependency_summary: str
    """Abstract summary of principal dependencies; authoritative ordering is graph edges (INV-10)."""
    work_package_refs: tuple[Reference, ...]
    """References (by id) to the Work Packages composing this Plan; the Plan owns them."""
    execution_graph_ref: Reference
    """Reference (by id) to this Plan's Execution Graph — a sibling artifact (INV-10)."""
    rationale: str
    """Explainable basis: why this work, why this order, why these dependencies/capabilities."""

    # --- optional ---------------------------------------------------------- #
    status: PlanStatus | None = None
    """Current lifecycle state — a projection of the event log (ADR-001); optional until projected."""
    operational_risks: tuple[Struct, ...] = ()
    """Risks Planning identified (missing info, unavailable resources, …); advisory only."""
    complexity_estimates: Struct | None = None
    """Estimated operational complexity, effort, coordination effort, duration, resource usage."""
    constraints_summary: Struct | None = None
    """Plan-level summary of constraints that shaped the approach (authoritative ones live elsewhere)."""
    assumptions: tuple[str, ...] = ()
    """Explicit planning assumptions whose violation would invalidate the approach."""
    supersedes: Reference | None = None
    """Reference to the prior Plan version this Plan replaces (set on replanning)."""
    correlation: Correlation | None = None
    """Correlation/trace identifiers tying this Plan to its Intent/Goal lineage."""
    source: Struct | None = None
    """Provenance metadata (e.g. planning cycle, planner identity) for audit."""
