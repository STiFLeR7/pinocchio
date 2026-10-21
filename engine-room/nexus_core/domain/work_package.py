"""Work Package — the smallest complete, independently executable unit of work.

Contract: ``contracts/work_package.md``. Produced by Planning. Binding: ADR-003
(§3.2 the single authoritative Work Package schema; §7 Context embed-or-reference),
ADR-001 (state is projection), ADR-004 (approval/validation/recovery policy lives
on Execution Strategy, by reference, not duplicated here).

Key invariants:
- INV-09: runtimes receive Work Packages — never Goals nor raw operator requests.
- INV-20: completion is determined from independently verifiable Evidence, never
  runtime self-report.
- INV-12: Execution produces Evidence Candidates; Validation produces Evidence —
  the package references Evidence by id and never embeds it.
- INV-04/INV-21: a Work Package never plans, never selects its runtime, and never
  declares its own completion.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from nexus_core.contracts.base import Constraint, Correlation, DomainObject, Reference, Struct
from nexus_core.contracts.enums import Priority
from nexus_core.contracts.status import WorkPackageStatus


class WorkPackage(DomainObject):
    """The single unit of execution (contract: work_package.md). One objective only."""

    LIFECYCLE_NAME: ClassVar[str] = "work_package"

    # --- required ---------------------------------------------------------- #
    identifier: str = Field(min_length=1)
    """Stable unique id; participates in correlation/trace lineage."""
    parent_goal: Reference
    """Reference (by id) to the originating Goal."""
    parent_plan: Reference
    """Reference (by id) to the owning Plan; Plans own Work Packages, never the inverse."""
    priority: Priority
    """Relative execution priority assigned by Planning."""
    objective: str
    """The single desired outcome and purpose; self-describing; one objective only (atomicity)."""
    context: Reference
    """The operational context for execution. ADR-003 §7 embed-or-reference: the foundation
    carries Context **by reference** (to ``context_package.md``) to avoid Work Package bloat."""
    constraints: tuple[Constraint, ...]
    """Governance, approvals, deadlines, budgets, quality requirements; override preferences."""
    resources: tuple[Reference, ...]
    """Declares *available* resources/capabilities; describes availability, not selection (INV-37)."""
    skills: tuple[Reference, ...]
    """References to required Skills plus capability references; runtime-independent (INV-33)."""
    inputs: tuple[Reference, ...]
    """The required information/artifacts the work consumes."""
    outputs: tuple[Struct, ...]
    """The expected deliverables; declares what should be produced, not the artifacts themselves."""
    evidence: Struct
    """How completion is verified: the evidence requirements the work must satisfy (INV-12)."""
    completion_criteria: Struct
    """The conditions that define success; completion derives from Evidence, never self-report (INV-20)."""

    # --- optional ---------------------------------------------------------- #
    status: WorkPackageStatus | None = None
    """Current lifecycle state — a projection of the event log (ADR-001); optional until projected."""
    checkpoints: tuple[Reference, ...] = ()
    """References to checkpoints created during the package's life; enables recovery (INV-18)."""
    observability: Struct | None = None
    """What the package exposes for supervision (state, progress, elapsed time, …) (INV-38)."""
    dependencies: tuple[Reference, ...] = ()
    """References to depended-on Work Packages; authoritative ordering is graph edges (INV-10)."""
    execution_strategy_ref: Reference | None = None
    """Reference to the governing Execution Strategy; policy by reference, not duplication (ADR-004)."""
    evidence_refs: tuple[Reference, ...] = ()
    """References (by id) to promoted Evidence produced for this package."""
    correlation: Correlation | None = None
    """Correlation/trace identifiers tying the package to its Goal/Plan lineage."""
    estimates: Struct | None = None
    """Per-package complexity/effort/duration estimates carried from Planning."""
