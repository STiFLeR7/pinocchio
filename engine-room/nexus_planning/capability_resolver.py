"""Step 6 — Capability Resolution (INV-37, ADR-002).

Resolution answers *what abstract capabilities the work requires* and which are
known to the Capability Registry. It returns a requirement set — required
identifiers, resolved references, and missing identifiers — and **nothing more**.
It never discovers harnesses, selects a provider, or allocates a runtime; that is
Orchestration's job. Resolution is deterministic: outputs are sorted and
de-duplicated.

The bundled :class:`InMemoryCapabilityRegistry` is a reference implementation of
the frozen ``nexus_core`` :class:`CapabilityRegistry` Protocol; the resolver
depends only on that Protocol (dependency inversion), so any registry works.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import CapabilityCategory
from nexus_core.domain.capability import Capability
from nexus_core.registries.interfaces import CapabilityRegistry
from nexus_planning.requests import CapabilityRequirementSet, PlanningRequest

CAPABILITY_TARGET_TYPE = "capability"


class InMemoryCapabilityRegistry:
    """A local reference registry of abstract Capability definitions (ADR-002)."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], Capability] = {}
        self._latest: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        """Register (or replace) a capability definition by identifier+version."""
        self._by_key[(capability.identifier, capability.version)] = capability
        self._latest[capability.identifier] = capability

    def get(self, identifier: str, version: str | None = None) -> Capability | None:
        """Fetch a capability by identifier, optionally pinned to a version."""
        if version is not None:
            return self._by_key.get((identifier, version))
        return self._latest.get(identifier)

    def find_by_category(self, category: CapabilityCategory) -> tuple[Capability, ...]:
        """All latest-version capabilities in a category, sorted by identifier."""
        found = [c for c in self._latest.values() if c.category is category]
        return tuple(sorted(found, key=lambda c: c.identifier))

    def list_all(self) -> tuple[Capability, ...]:
        """Every latest-version capability, sorted by identifier."""
        return tuple(sorted(self._latest.values(), key=lambda c: c.identifier))


class CapabilityResolver:
    """Resolves a request's required capabilities against the registry (candidates only)."""

    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry

    def resolve(self, request: PlanningRequest) -> CapabilityRequirementSet:
        """Produce the deterministic capability requirement set for the request."""
        required = sorted(
            {
                capability
                for item in request.work_items
                for capability in item.capability_requirements
            }
        )
        resolved: list[Reference] = []
        missing: list[str] = []
        for identifier in required:
            if self._registry.get(identifier) is not None:
                resolved.append(
                    Reference(target_type=CAPABILITY_TARGET_TYPE, identifier=identifier)
                )
            else:
                missing.append(identifier)
        return CapabilityRequirementSet(
            required=tuple(required),
            resolved=tuple(resolved),
            missing=tuple(missing),
        )
