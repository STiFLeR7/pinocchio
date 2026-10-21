"""Resource — an allocatable operational instance plus its allocation projection.

Contract: ``contracts/resource.md``. Allocation state owned by Orchestration (the
sole allocator). Binding: ADR-001, ADR-002. Invariants: INV-36 (provider
availability/health is owned by the Harness Registry; the Resource *references* it
and never duplicates it), INV-32, INV-13/14/15, INV-03 (Planning never allocates),
INV-07.

``allocation_state`` is the Resource's lifecycle status — an Orchestration-owned
**projection** of allocation events in the unified State Model (ADR-001 §3.4), not
a separate independent machine. For harness-backed Resources, ``availability`` is
*read from* the Harness Registry, never authored here.
"""

from __future__ import annotations

from typing import ClassVar

from nexus_core.contracts.base import DomainObject, Reference, Struct
from nexus_core.contracts.enums import (
    ResourceAllocationState,
    ResourceAvailability,
    ResourceType,
)


class Resource(DomainObject):
    """An allocatable operational instance (contract: resource.md). It references, never duplicates."""

    LIFECYCLE_NAME: ClassVar[str] = "resource"

    # --- required ---------------------------------------------------------- #
    identity: str
    """Stable, unique identity of the instance; participates in correlation/trace lineage."""
    type_category: ResourceType
    """Logical class of asset (Human, Runtime, Workspace, …) — for allocation reasoning."""
    allocation_state: ResourceAllocationState
    """Lifecycle status: the Orchestration-owned allocation projection (ADR-001), never authoritative."""
    capability_reference: Reference
    """Reference to advertised Capabilities in the Harness Registry; never duplicates definitions (INV-32)."""
    backing_reference: Reference
    """What backs the instance: a Harness, or an Infrastructure catalog entry — exactly one applies."""

    # --- optional ---------------------------------------------------------- #
    availability: ResourceAvailability | None = None
    """Availability projection *read from* the Harness Registry (INV-36); never owned here."""
    owner: str | None = None
    """The accountable owner/holder of the instance (operational ownership, not allocation holder)."""
    constraints: Struct | None = None
    """Allocation-influencing boundaries (concurrency, security, budget, time windows, …)."""
    operational_limits: Struct | None = None
    """Quota/capacity figures relevant to allocation accounting (esp. Infrastructure Resources)."""
    utilization: Struct | None = None
    """Allocation-relevant utilization/accounting; live harness utilization is read from the Registry."""
    relationships: tuple[Reference, ...] = ()
    """Explicit dependencies on other Resources (by Resource identity)."""
    allocation_holder: Reference | None = None
    """When Allocated/Reserved: the Work Package (and correlation) currently holding the instance."""
    metadata: Struct | None = None
    """Non-authoritative descriptive attributes (tags, notes, documentation links)."""
