"""A reference in-memory Harness Registry (implements the frozen Protocol).

The frozen ``nexus_core`` ``HarnessRegistry`` Protocol (ADR-002) is the sole owner
of provider availability/health (INV-36); ``discover_by_capability`` returns the
harnesses that advertise a capability — **candidates only**, never a selection
(INV-37). No registry phase exists yet, so this deterministic, in-memory reference
implementation ships here; the Runtime Request Builder depends only on the Protocol
(dependency inversion), so it is swappable.
"""

from __future__ import annotations

from nexus_core.contracts.enums import ResourceAvailability
from nexus_core.registries.interfaces import HarnessDescriptor


class InMemoryHarnessRegistry:
    """A deterministic in-memory ``HarnessRegistry`` (reference implementation)."""

    def __init__(self) -> None:
        self._by_identity: dict[str, HarnessDescriptor] = {}

    def register(self, descriptor: HarnessDescriptor) -> None:
        self._by_identity[descriptor.identity] = descriptor

    def get(self, identity: str) -> HarnessDescriptor | None:
        return self._by_identity.get(identity)

    def discover_by_capability(self, capability_identifier: str) -> tuple[HarnessDescriptor, ...]:
        """Candidates that advertise the capability — sorted, candidates only (INV-37)."""
        matches = [
            descriptor
            for descriptor in self._by_identity.values()
            if any(
                ref.identifier == capability_identifier
                for ref in descriptor.advertised_capabilities
            )
        ]
        return tuple(sorted(matches, key=lambda descriptor: descriptor.identity))

    def availability(self, identity: str) -> ResourceAvailability | None:
        descriptor = self._by_identity.get(identity)
        return descriptor.availability if descriptor is not None else None

    def list_all(self) -> tuple[HarnessDescriptor, ...]:
        return tuple(sorted(self._by_identity.values(), key=lambda descriptor: descriptor.identity))
