"""Artifact — the common, immutable-by-default record of a produced operational output.

Contract: ``contracts/artifact.md``. Produced by the producing layer (most often
Execution); status transitions advanced by the responsible layer (Validation
grants Validated). Binding: ADR-003 (§3.7 one status vocabulary; Evidence by
reference), ADR-001 (event-sourced state). Invariants: INV-12 (the Artifact
references Evidence **by id** and never embeds it), INV-27, INV-13/14/15, INV-20.

The Artifact is **immutable by default**: a revision is a new version in the
immutable version chain, never an overwrite. Unlike other domain objects, its
``status`` is **required** — there is exactly one status vocabulary (ADR-003 §3.7).
"""

from __future__ import annotations

from typing import ClassVar

from nexus_core.contracts.base import DomainObject, Reference, Struct
from nexus_core.contracts.enums import ArtifactStatus, ArtifactType


class Artifact(DomainObject):
    """The durable, traceable record of a produced output (contract: artifact.md)."""

    LIFECYCLE_NAME: ClassVar[str] = "artifact"

    # --- required ---------------------------------------------------------- #
    identity: str
    """Stable, unique identifier; addressable for discovery, reference, and lineage."""
    type: ArtifactType
    """The artifact category/kind (source, documentation, research, …)."""
    owner: str
    """The layer/operator that owns this Artifact throughout its lifecycle (distinct from producer)."""
    producer: str
    """The layer/runtime/operator that originally produced it."""
    created_time: str
    """When the Artifact was first created; recorded as data so replay stays deterministic (INV-17)."""
    updated_time: str
    """When this version was last advanced."""
    version: str
    """This Artifact's version within its immutable version chain."""
    status: ArtifactStatus
    """The single canonical status (ADR-003 §3.7) — REQUIRED. A derived projection, never authoritative."""
    lineage: Struct
    """The operational provenance chain Goal → Plan → Work Package → Execution → Artifact → Knowledge."""
    correlation_identifier: str
    """Correlation/trace lineage shared with the producing operation's Events; auditable end to end."""

    # --- optional ---------------------------------------------------------- #
    workspace: str | None = None
    """The operational workspace/context the Artifact belongs to."""
    metadata: Struct | None = None
    """Descriptive attributes and tags supporting discovery and reuse."""
    evidence_ref: tuple[Reference, ...] = ()
    """Reference(s) **by id** to Evidence (owned by Validation); never embeds Evidence (INV-12)."""
    references: tuple[Reference, ...] = ()
    """References to related objects (goal, plan, work package, skill, knowledge, policy, …)."""
    parent_version: Reference | None = None
    """Reference to the prior version in the immutable version chain."""
    change_summary: Struct | None = None
    """For a new version: what changed, with creator, timestamp, and originating execution."""
    source: Struct | None = None
    """Provenance when the Artifact originates outside Execution (human operator, external system)."""
