"""Step 3 — Capability Resolver (resolve Capability metadata; never select a provider).

Resolves the Capability *requirements* of one Harness Request — both the capabilities
the request names directly and the capabilities its resolved Skills require — against
the Capability Registry, producing provider-independent Capability metadata. It
selects no provider and allocates no runtime (INV-32/37): a Capability answers "what
can be done", never "which provider does it". A capability reference that does not
resolve is a fail-closed error.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, ValueObject
from nexus_core.registries.interfaces import CapabilityRegistry
from nexus_harness.skill_resolver import ResolvedSkills
from nexus_harness.validators import UnresolvedReferenceError
from nexus_harness.vocabulary import CAPABILITY_TARGET_TYPE
from nexus_orchestration.harness_requests import HarnessRequest


class ResolvedCapability(ValueObject):
    """One resolved Capability requirement — its reference plus abstract metadata."""

    reference: Reference
    identifier: str
    name: str
    version: str
    category: str


class ResolvedCapabilities(ValueObject):
    """The complete, deterministic set of Capability requirements for one request."""

    capabilities: tuple[ResolvedCapability, ...] = ()


class CapabilityResolver:
    """Resolves the request's (and its Skills') Capability requirements."""

    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry

    def resolve(self, request: HarnessRequest, skills: ResolvedSkills) -> ResolvedCapabilities:
        """Resolve the union of direct and Skill-implied capabilities (deduped, sorted)."""
        identifiers = {ref.identifier for ref in request.required_capability_refs}
        for skill in skills.skills:
            identifiers.update(ref.identifier for ref in skill.required_capability_refs)
        return ResolvedCapabilities(
            capabilities=tuple(
                self._resolve(request, identifier) for identifier in sorted(identifiers)
            )
        )

    def _resolve(self, request: HarnessRequest, identifier: str) -> ResolvedCapability:
        capability = self._registry.get(identifier)
        if capability is None:
            raise UnresolvedReferenceError(
                f"capability {identifier!r} for harness request {request.identity!r} "
                f"is not resolvable"
            )
        return ResolvedCapability(
            reference=Reference(
                target_type=CAPABILITY_TARGET_TYPE, identifier=capability.identifier
            ),
            identifier=capability.identifier,
            name=capability.name,
            version=capability.version,
            category=capability.category.value,
        )
