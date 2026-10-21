"""Resolution sources — the read-only providers the Harness resolves against.

The Harness *resolves* references into the concrete definitions a runtime needs. It
never executes those definitions; it only reads them. The providers are injected
(dependency inversion): the three registry Protocols (``SkillRegistry`` /
``CapabilityRegistry`` / ``PolicyRegistry``, ADR-002) and four
:class:`~nexus_core.persistence.interfaces.Repository` seams (Work Package, Context
Package, Execution Strategy, Artifact) reuse the **Phase 2** persistence mechanism —
no new persistence layer is invented.

No registry phase exists yet, so deterministic in-memory *reference* implementations
of the three registry Protocols ship here (mirroring how the
``InMemoryHarnessRegistry`` shipped in Orchestration). Every resolver depends only on
the Protocol, so the references are swappable.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.contracts.enums import (
    CapabilityCategory,
    PolicyCategory,
    SkillCategory,
)
from nexus_core.domain.capability import Capability
from nexus_core.domain.context_package import ContextPackage
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_core.domain.policy import Policy
from nexus_core.domain.skill import Skill
from nexus_core.domain.work_package import WorkPackage
from nexus_core.persistence.interfaces import Repository
from nexus_core.registries.interfaces import (
    CapabilityRegistry,
    PolicyRegistry,
    SkillRegistry,
)
from nexus_infra import ArtifactRepository


class InMemorySkillRegistry:
    """A deterministic in-memory ``SkillRegistry`` (reference implementation)."""

    def __init__(self) -> None:
        self._by_identity: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._by_identity[skill.identity] = skill

    def get(self, identifier: str, version: str | None = None) -> Skill | None:
        skill = self._by_identity.get(identifier)
        if skill is None or (version is not None and skill.version != version):
            return None
        return skill

    def find_by_category(self, category: SkillCategory) -> tuple[Skill, ...]:
        return tuple(
            sorted(
                (s for s in self._by_identity.values() if s.category == category),
                key=lambda s: s.identity,
            )
        )

    def list_all(self) -> tuple[Skill, ...]:
        return tuple(sorted(self._by_identity.values(), key=lambda s: s.identity))


class InMemoryCapabilityRegistry:
    """A deterministic in-memory ``CapabilityRegistry`` (reference implementation)."""

    def __init__(self) -> None:
        self._by_identifier: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        self._by_identifier[capability.identifier] = capability

    def get(self, identifier: str, version: str | None = None) -> Capability | None:
        capability = self._by_identifier.get(identifier)
        if capability is None or (version is not None and capability.version != version):
            return None
        return capability

    def find_by_category(self, category: CapabilityCategory) -> tuple[Capability, ...]:
        return tuple(
            sorted(
                (c for c in self._by_identifier.values() if c.category == category),
                key=lambda c: c.identifier,
            )
        )

    def list_all(self) -> tuple[Capability, ...]:
        return tuple(sorted(self._by_identifier.values(), key=lambda c: c.identifier))


class InMemoryPolicyRegistry:
    """A deterministic in-memory ``PolicyRegistry`` (reference implementation).

    Every registered policy is considered enabled; ``enabled`` returns the full set
    sorted by ``(identity, version)``. Evaluation (matching conditions to a decision)
    is the Policy Engine's, never the registry's nor the Harness's.
    """

    def __init__(self) -> None:
        self._by_identity: dict[str, Policy] = {}

    def register(self, policy: Policy) -> None:
        self._by_identity[policy.identity] = policy

    def get(self, identifier: str, version: str | None = None) -> Policy | None:
        policy = self._by_identity.get(identifier)
        if policy is None or (version is not None and policy.version != version):
            return None
        return policy

    def find_by_category(self, category: PolicyCategory) -> tuple[Policy, ...]:
        return tuple(
            sorted(
                (p for p in self._by_identity.values() if p.category == category),
                key=lambda p: (p.identity, p.version),
            )
        )

    def enabled(self) -> tuple[Policy, ...]:
        return self.list_all()

    def list_all(self) -> tuple[Policy, ...]:
        return tuple(sorted(self._by_identity.values(), key=lambda p: (p.identity, p.version)))


@dataclass(frozen=True, slots=True)
class HarnessSources:
    """The read-only resolution providers the Harness compiles against (DI bundle)."""

    skills: SkillRegistry
    capabilities: CapabilityRegistry
    policies: PolicyRegistry
    work_packages: Repository[WorkPackage]
    context_packages: Repository[ContextPackage]
    strategies: Repository[ExecutionStrategy]
    artifacts: ArtifactRepository
