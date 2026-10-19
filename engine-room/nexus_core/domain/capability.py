"""Capability — the abstract definition of *what* operational outcome can be produced.

Contract: ``contracts/capability.md``. Owned by the Capability Registry. Binding:
ADR-002. Invariants: INV-32 (Capabilities are provider-independent), INV-36,
INV-37, INV-07, INV-03.

Per INV-32 a Capability carries **no provider, availability, or health** field:
those live solely in the **Harness Registry** (ADR-002 field-ownership table), and
a Capability never embeds or duplicates provider state. A Capability answers "what
can be done", never "which provider does it".
"""

from __future__ import annotations

from typing import ClassVar

from nexus_core.contracts.base import DomainObject, Reference, Struct
from nexus_core.contracts.enums import CapabilityCategory
from nexus_core.contracts.status import CapabilityStatus


class Capability(DomainObject):
    """An abstract, provider-independent unit of functionality (contract: capability.md)."""

    LIFECYCLE_NAME: ClassVar[str] = "capability"

    # --- required ---------------------------------------------------------- #
    identifier: str
    """Stable, globally unique identity, independent of any provider; participates in lineage."""
    name: str
    """Human-readable operational name (e.g. "Repository Analysis", "Code Generation")."""
    version: str
    """Definition version; Capabilities evolve independently and references are version-aware."""
    category: CapabilityCategory
    """Logical grouping of the functionality — taxonomy only, no provider meaning."""
    description: str
    """What operational outcome the Capability produces; the one functional job it names."""
    inputs: tuple[Struct, ...]
    """Logical declaration of the information the Capability requires (logical shape only)."""
    outputs: tuple[Struct, ...]
    """Logical declaration of the operational outcome(s) produced (logical shape only)."""

    # --- optional ---------------------------------------------------------- #
    status: CapabilityStatus | None = None
    """Definitional registry state — a projection of registry events; optional until projected."""
    constraints: Struct | None = None
    """Abstract operational boundaries inherent to the capability; declarative, provider-independent."""
    dependencies: tuple[Reference, ...] = ()
    """Other Capabilities this one logically requires/composes with (by Capability identifier/version)."""
    metadata: Struct | None = None
    """Non-authoritative descriptive attributes; carries no operational truth."""

    # NOTE (INV-32): provider, availability, and health are deliberately ABSENT.
    # They are owned solely by the Harness Registry (ADR-002); a Capability
    # references that state, it never declares or duplicates it.
