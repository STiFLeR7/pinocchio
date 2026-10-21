"""Context Package — the complete operational understanding required to act on a Goal.

Contract: ``contracts/context_package.md``. Owned by Context Engineering.
Binding: ADR-003 (canonical object model; §7 Context-by-reference), ADR-001
(event-sourced state). Invariants: exactly one Context Package per Goal, INV-06
(consumes Knowledge read-only), INV-07, INV-12 (references Evidence/artifacts by
id, never embeds), INV-13/14/15, INV-17.

It turns incomplete operator intent (a Goal) into minimal, complete, validated
context that Planning can consume. It never plans, selects runtimes, executes,
validates execution, or performs recovery.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from nexus_core.contracts.base import (
    Constraint,
    Correlation,
    DomainObject,
    Reference,
    Struct,
    ValueObject,
)
from nexus_core.contracts.enums import InterpretationConfidence
from nexus_core.contracts.status import ContextPackageStatus


class ContextCategories(ValueObject):
    """The eight canonical Context Categories (contract §4), each a logical section."""

    goal_context: Struct = Field(default_factory=dict)
    """Objective, desired outcome, success definition."""
    domain_context: Struct = Field(default_factory=dict)
    """Operational domain, terminology, knowledge requirements, standards."""
    workspace_context: Struct = Field(default_factory=dict)
    """Operational environment: repositories, files, documents, communication channels."""
    historical_context: Struct = Field(default_factory=dict)
    """Previous work, failures, executions, decisions."""
    operational_context: Struct = Field(default_factory=dict)
    """Current state, running workflows, open tasks, priorities, dependencies."""
    constraint_context: Struct = Field(default_factory=dict)
    """Governance, security, deadlines, approvals, quality expectations, budgets."""
    resource_context: Struct = Field(default_factory=dict)
    """Available runtimes, tools, knowledge, skills (described, not live provider state)."""
    execution_context: Struct = Field(default_factory=dict)
    """Validation requirements, expected outputs, execution assumptions, dependencies."""


class ContextPackage(DomainObject):
    """Minimal, complete, validated context for a Goal (contract: context_package.md)."""

    LIFECYCLE_NAME: ClassVar[str] = "context_package"

    # --- required ---------------------------------------------------------- #
    identity: str = Field(min_length=1)
    """Stable, unique identifier; addressable, correlatable, replayable."""
    goal_ref: Reference
    """Reference (by id) to the single Goal this package serves (one Goal per package)."""
    correlation: Correlation
    """Correlation / trace lineage shared with the Goal and downstream objects."""
    context_categories: ContextCategories
    """The eight Context Categories — the stable canonical set."""
    constraints: tuple[Constraint, ...]
    """The operative constraints governing work on this Goal; override execution preferences."""
    resources: tuple[Reference, ...]
    """Available resources by reference; described capability, not live provider state (ADR-002)."""
    confidence: InterpretationConfidence
    """Confidence that the assembled context is sufficient and correct."""
    validation_status: Struct
    """Outcome of context validation; indicates whether the package is fit for Planning."""

    # --- optional ---------------------------------------------------------- #
    status: ContextPackageStatus | None = None
    """Current lifecycle state — a projection of the event log (ADR-001); optional until projected."""
    supporting_artifacts: tuple[Reference, ...] = ()
    """References to artifacts informing the work; referenced by id, not embedded (INV-12)."""
    references: tuple[str, ...] = ()
    """Links/pointers to sources used to build the context (provenance trail)."""
    known_unknowns: tuple[str, ...] = ()
    """Explicitly identified gaps: missing information, open assumptions, unresolved dependencies."""
    enrichment_history: tuple[Struct, ...] = ()
    """Record of enrichment passes applied, for explainability and freshness reasoning."""
    freshness: Struct | None = None
    """Recency indicators for time-sensitive context elements."""
    source: Struct | None = None
    """Provenance summary of where the context was gathered."""
