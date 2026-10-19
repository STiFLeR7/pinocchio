"""Skill — a reusable, runtime-independent operational procedure.

Contract: ``contracts/skill.md``. Owned by the Skill Registry. Binding: ADR-002,
ADR-004. Invariants: INV-33 (a Skill describes operational capability, never
runtime implementation — the same Skill runs on any runtime unchanged; it carries
no runtime/provider field), INV-07, INV-15.

Per ADR-004 §3.4 a Skill only *declares* default Validation/Recovery strategies;
those defaults are **overridable by the Execution Strategy** and are never the
Skill's authority — Validation owns verdicts and Recovery owns strategy selection
(declaration ≠ evaluation).
"""

from __future__ import annotations

from typing import ClassVar

from nexus_core.contracts.base import Constraint, DomainObject, Reference, Struct
from nexus_core.contracts.enums import SkillCategory
from nexus_core.contracts.status import SkillStatus


class Skill(DomainObject):
    """A reusable operational procedure (contract: skill.md). It binds to no runtime."""

    LIFECYCLE_NAME: ClassVar[str] = "skill"

    # --- required ---------------------------------------------------------- #
    identity: str
    """Stable identifier; participates in correlation/trace lineage."""
    name: str
    """Human-readable name of the procedure."""
    version: str
    """Definition version; Skills version independently as procedures (ADR-002 §D)."""
    purpose: str
    """The operational capability this Skill provides — what work it knows how to perform."""
    inputs: tuple[Struct, ...]
    """Required information to perform the procedure (logical roles, not wire schemas)."""
    outputs: tuple[Struct, ...]
    """Expected deliverables (logical roles)."""
    procedure: Struct
    """The methodology: phases, checkpoints, and expected transitions, bound to no runtime (INV-33)."""

    # --- optional ---------------------------------------------------------- #
    status: SkillStatus | None = None
    """Execution-lifecycle state of a selected Skill — a projection of the log; optional until projected."""
    required_context: Struct | None = None
    """What Context Engineering must provide before execution; drives assembly during Prepared."""
    constraints: tuple[Constraint, ...] = ()
    """Operational boundaries inherent to the procedure; declarative, enforced by Governance/Orchestration."""
    validation_strategy_default: Struct | None = None
    """Default approach to verifying completion — overridable by Execution Strategy (ADR-004 §3.4)."""
    recovery_strategy_default: Struct | None = None
    """Default expected behavior on failure — overridable by Execution Strategy (ADR-004 §3.4)."""
    category: SkillCategory | None = None
    """Logical grouping (taxonomy only)."""
    composition_references: tuple[Reference, ...] = ()
    """Other Skills this Skill composes with (by Skill identity/version)."""
    required_capabilities: tuple[Reference, ...] = ()
    """The Capabilities this Skill needs to be satisfiable (references into capability.md)."""
    metadata: Struct | None = None
    """Non-authoritative descriptive attributes (tags, compatibility notes, documentation links)."""
