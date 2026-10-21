"""The four registry interfaces (ADR-002) and the Harness descriptor.

Interfaces only. Every method is read-or-register; none performs execution,
planning, resolution-as-selection, or evaluation (those belong to other layers
and later phases). The ``HarnessDescriptor`` captures the registry-relevant
subset of the Harness common contract (doc 11) — notably the provider
``availability`` and ``health`` that the Harness Registry alone owns (INV-36).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from nexus_core.contracts.base import Reference, Struct, ValueObject
from nexus_core.contracts.enums import (
    CapabilityCategory,
    PolicyCategory,
    ResourceAvailability,
    SkillCategory,
)
from nexus_core.domain.capability import Capability
from nexus_core.domain.policy import Policy
from nexus_core.domain.skill import Skill


class HarnessCategory(StrEnum):
    """Harness categories (doc 11). A Runtime is a Harness of category ``RUNTIME``."""

    RUNTIME = "runtime"
    CONTEXT = "context"
    KNOWLEDGE = "knowledge"
    VALIDATION = "validation"
    COMMUNICATION = "communication"
    GOVERNANCE = "governance"
    OBSERVABILITY = "observability"


class HarnessDescriptor(ValueObject):
    """The registry-facing descriptor of an integration boundary (doc 11).

    Holds the provider ``availability`` and ``health`` that, per INV-36, live
    only in the Harness Registry — never duplicated on Capability or Resource.
    Advertised capabilities are *references* to abstract Capability definitions.
    """

    identity: str
    category: HarnessCategory
    version: str
    advertised_capabilities: tuple[Reference, ...] = ()
    availability: ResourceAvailability = ResourceAvailability.UNKNOWN
    health: ResourceAvailability = ResourceAvailability.UNKNOWN
    configuration: Struct | None = None
    metadata: Struct | None = None


@runtime_checkable
class CapabilityRegistry(Protocol):
    """Registry of abstract Capability definitions (no provider/health state)."""

    def register(self, capability: Capability) -> None: ...

    def get(self, identifier: str, version: str | None = None) -> Capability | None: ...

    def find_by_category(self, category: CapabilityCategory) -> tuple[Capability, ...]: ...

    def list_all(self) -> tuple[Capability, ...]: ...


@runtime_checkable
class HarnessRegistry(Protocol):
    """Registry of integration boundaries; sole owner of availability/health (INV-36).

    ``discover_by_capability`` returns the harnesses that advertise a capability —
    *candidates only*. Selection/allocation is Orchestration's, never the
    registry's (INV-37).
    """

    def register(self, descriptor: HarnessDescriptor) -> None: ...

    def get(self, identity: str) -> HarnessDescriptor | None: ...

    def discover_by_capability(
        self, capability_identifier: str
    ) -> tuple[HarnessDescriptor, ...]: ...

    def availability(self, identity: str) -> ResourceAvailability | None: ...

    def list_all(self) -> tuple[HarnessDescriptor, ...]: ...


@runtime_checkable
class SkillRegistry(Protocol):
    """Registry of reusable operational procedures (runtime-independent)."""

    def register(self, skill: Skill) -> None: ...

    def get(self, identity: str, version: str | None = None) -> Skill | None: ...

    def find_by_category(self, category: SkillCategory) -> tuple[Skill, ...]: ...

    def list_all(self) -> tuple[Skill, ...]: ...


@runtime_checkable
class PolicyRegistry(Protocol):
    """Registry of governance/operational policies (evaluated only by the Policy Engine)."""

    def register(self, policy: Policy) -> None: ...

    def get(self, identity: str, version: str | None = None) -> Policy | None: ...

    def find_by_category(self, category: PolicyCategory) -> tuple[Policy, ...]: ...

    def enabled(self) -> tuple[Policy, ...]: ...

    def list_all(self) -> tuple[Policy, ...]: ...
