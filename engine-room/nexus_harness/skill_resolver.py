"""Step 2 — Skill Resolver (resolve required Skills; never execute them).

Resolves each Skill reference a Harness Request carries against the Skill Registry,
producing resolved Skill *references* plus the registry-relevant metadata a runtime
needs to locate the procedure. A Skill reference that does not resolve is a
fail-closed error. Skills are runtime-independent (INV-33); resolving one neither
binds it to a runtime nor runs it.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, ValueObject
from nexus_core.registries.interfaces import SkillRegistry
from nexus_harness.validators import UnresolvedReferenceError
from nexus_harness.vocabulary import CAPABILITY_TARGET_TYPE, SKILL_TARGET_TYPE
from nexus_orchestration.harness_requests import HarnessRequest


class ResolvedSkill(ValueObject):
    """One resolved Skill — its reference plus the metadata needed to locate it."""

    reference: Reference
    identity: str
    name: str
    version: str
    required_capability_refs: tuple[Reference, ...] = ()


class ResolvedSkills(ValueObject):
    """The complete, deterministic set of Skills resolved for one Harness Request."""

    skills: tuple[ResolvedSkill, ...] = ()


class SkillResolver:
    """Resolves a Harness Request's Skill references against the Skill Registry."""

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry

    def resolve(self, request: HarnessRequest) -> ResolvedSkills:
        """Resolve every Skill reference (sorted by identity); fail closed on a miss."""
        references = sorted(
            (
                ref
                for ref in request.required_skill_refs
                if ref.target_type != CAPABILITY_TARGET_TYPE
            ),
            key=lambda ref: ref.identifier,
        )
        return ResolvedSkills(skills=tuple(self._resolve(request, ref) for ref in references))

    def _resolve(self, request: HarnessRequest, reference: Reference) -> ResolvedSkill:
        skill = self._registry.get(reference.identifier)
        if skill is None:
            raise UnresolvedReferenceError(
                f"skill {reference.identifier!r} for harness request {request.identity!r} "
                f"is not resolvable"
            )
        return ResolvedSkill(
            reference=Reference(target_type=SKILL_TARGET_TYPE, identifier=skill.identity),
            identity=skill.identity,
            name=skill.name,
            version=skill.version,
            required_capability_refs=skill.required_capabilities,
        )
