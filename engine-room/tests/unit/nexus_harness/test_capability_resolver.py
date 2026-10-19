"""Unit tests for nexus_harness.capability_resolver.

Covers CapabilityResolver.resolve(request, resolved_skills):
- Resolves the UNION of direct request capability refs AND capability refs implied
  by every resolved skill's required_capability_refs.
- Output is deduplicated by identifier and sorted alphabetically.
- Each ResolvedCapability carries reference(target_type="capability"), identifier,
  name, version, and category (string).
- A missing capability raises UnresolvedReferenceError (fail-closed).
- Empty inputs (no direct caps, no skill caps) produce empty ResolvedCapabilities.
- Dedup: a capability appearing on both the request and a skill appears exactly once.
- Determinism: resolving twice yields equal results.
- ResolvedCapability and ResolvedCapabilities are frozen (mutations are rejected).
"""

from __future__ import annotations

import pytest

from nexus_harness import (
    CapabilityResolver,
    InMemoryCapabilityRegistry,
    InMemorySkillRegistry,
    ResolvedCapabilities,
    ResolvedSkill,
    ResolvedSkills,
    SkillResolver,
    UnresolvedReferenceError,
)
from tests.unit.nexus_harness.helpers import capability, hrequest, ref, skill

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cap_resolver(*cap_ids: str) -> CapabilityResolver:
    """Return a CapabilityResolver pre-loaded with the given capability identifiers."""
    reg = InMemoryCapabilityRegistry()
    for cid in cap_ids:
        reg.register(capability(cid))
    return CapabilityResolver(reg)


def _no_skills() -> ResolvedSkills:
    """Empty ResolvedSkills — no skill-implied capabilities."""
    return ResolvedSkills()


def _resolve_skills(
    skill_names: tuple[str, ...],
    caps: tuple[str, ...],
    node: str = "node-1",
) -> ResolvedSkills:
    """Build a ResolvedSkills by running the real SkillResolver."""
    skill_reg = InMemorySkillRegistry()
    for name in skill_names:
        skill_reg.register(skill(name, capabilities=caps))
    resolver = SkillResolver(skill_reg)
    refs = tuple(ref("skill", name) for name in skill_names)
    request = hrequest(node, skills=refs)
    return resolver.resolve(request)


# ---------------------------------------------------------------------------
# Empty inputs
# ---------------------------------------------------------------------------


def test_no_caps_anywhere_returns_empty() -> None:
    """No direct cap refs and no skill-implied caps yield empty ResolvedCapabilities."""
    resolver = _cap_resolver()
    result = resolver.resolve(hrequest("node-1"), _no_skills())
    assert result == ResolvedCapabilities()
    assert result.capabilities == ()


def test_empty_skills_and_no_direct_caps() -> None:
    """ResolvedSkills with no skills + request with no cap refs yields empty result."""
    resolver = _cap_resolver("cap-x")
    result = resolver.resolve(hrequest("node-1"), _no_skills())
    assert result.capabilities == ()


# ---------------------------------------------------------------------------
# Direct capability refs on the request
# ---------------------------------------------------------------------------


def test_direct_cap_ref_resolved() -> None:
    """A capability referenced directly on the request is resolved."""
    resolver = _cap_resolver("cap-alpha")
    request = hrequest("node-1", capabilities=(ref("capability", "cap-alpha"),))
    result = resolver.resolve(request, _no_skills())
    assert len(result.capabilities) == 1


def test_resolved_capability_reference_target_type_is_capability() -> None:
    """ResolvedCapability.reference.target_type is always 'capability'."""
    resolver = _cap_resolver("cap-alpha")
    request = hrequest("node-1", capabilities=(ref("capability", "cap-alpha"),))
    cap = resolver.resolve(request, _no_skills()).capabilities[0]
    assert cap.reference.target_type == "capability"


def test_resolved_capability_reference_identifier_echoes_registry() -> None:
    """ResolvedCapability.reference.identifier matches the registered identifier."""
    resolver = _cap_resolver("cap-alpha")
    request = hrequest("node-1", capabilities=(ref("capability", "cap-alpha"),))
    cap = resolver.resolve(request, _no_skills()).capabilities[0]
    assert cap.reference.identifier == "cap-alpha"


def test_resolved_capability_identifier_field() -> None:
    """ResolvedCapability.identifier matches the registry entry."""
    resolver = _cap_resolver("cap-alpha")
    request = hrequest("node-1", capabilities=(ref("capability", "cap-alpha"),))
    cap = resolver.resolve(request, _no_skills()).capabilities[0]
    assert cap.identifier == "cap-alpha"


def test_resolved_capability_name_derived_from_identifier() -> None:
    """ResolvedCapability.name is the title-cased form of the identifier."""
    resolver = _cap_resolver("cap-alpha")
    request = hrequest("node-1", capabilities=(ref("capability", "cap-alpha"),))
    cap = resolver.resolve(request, _no_skills()).capabilities[0]
    assert cap.name == "Cap Alpha"


def test_resolved_capability_version_defaults_to_one() -> None:
    """ResolvedCapability.version is '1' for capabilities built with the helper default."""
    resolver = _cap_resolver("cap-alpha")
    request = hrequest("node-1", capabilities=(ref("capability", "cap-alpha"),))
    cap = resolver.resolve(request, _no_skills()).capabilities[0]
    assert cap.version == "1"


def test_resolved_capability_category_is_string() -> None:
    """ResolvedCapability.category is a plain string (the enum's value)."""
    resolver = _cap_resolver("cap-alpha")
    request = hrequest("node-1", capabilities=(ref("capability", "cap-alpha"),))
    cap = resolver.resolve(request, _no_skills()).capabilities[0]
    assert isinstance(cap.category, str)


# ---------------------------------------------------------------------------
# Skill-implied capabilities
# ---------------------------------------------------------------------------


def test_skill_implied_capability_appears_without_direct_ref() -> None:
    """A capability required by a resolved skill appears even if absent from the request."""
    cap_reg = InMemoryCapabilityRegistry()
    cap_reg.register(capability("cap-implied"))
    resolver = CapabilityResolver(cap_reg)

    resolved_skills = _resolve_skills(("skill-a",), caps=("cap-implied",))
    request = hrequest("node-1", skills=(ref("skill", "skill-a"),))

    result = resolver.resolve(request, resolved_skills)
    identifiers = {c.identifier for c in result.capabilities}
    assert "cap-implied" in identifiers


def test_skill_implied_capability_not_on_request_direct_refs() -> None:
    """The request carries no direct cap refs; the cap comes purely from the skill."""
    cap_reg = InMemoryCapabilityRegistry()
    cap_reg.register(capability("cap-from-skill"))
    resolver = CapabilityResolver(cap_reg)

    resolved_skills = _resolve_skills(("skill-x",), caps=("cap-from-skill",))
    request = hrequest("node-1")  # no capabilities= kwarg

    result = resolver.resolve(request, resolved_skills)
    assert len(result.capabilities) == 1
    assert result.capabilities[0].identifier == "cap-from-skill"


def test_multiple_skills_implied_caps_all_appear() -> None:
    """All capabilities implied by multiple resolved skills appear in the output."""
    cap_reg = InMemoryCapabilityRegistry()
    for cid in ("cap-1", "cap-2"):
        cap_reg.register(capability(cid))
    resolver = CapabilityResolver(cap_reg)

    skill_reg = InMemorySkillRegistry()
    skill_reg.register(skill("skill-a", capabilities=("cap-1",)))
    skill_reg.register(skill("skill-b", capabilities=("cap-2",)))
    skill_resolver = SkillResolver(skill_reg)
    request = hrequest(
        "node-1",
        skills=(ref("skill", "skill-a"), ref("skill", "skill-b")),
    )
    resolved_skills = skill_resolver.resolve(request)

    result = resolver.resolve(request, resolved_skills)
    identifiers = {c.identifier for c in result.capabilities}
    assert identifiers == {"cap-1", "cap-2"}


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def test_cap_on_request_and_skill_appears_once() -> None:
    """A capability present on both the request and a resolved skill is deduplicated."""
    cap_reg = InMemoryCapabilityRegistry()
    cap_reg.register(capability("cap-shared"))
    resolver = CapabilityResolver(cap_reg)

    resolved_skills = _resolve_skills(("skill-a",), caps=("cap-shared",))
    request = hrequest(
        "node-1",
        skills=(ref("skill", "skill-a"),),
        capabilities=(ref("capability", "cap-shared"),),
    )

    result = resolver.resolve(request, resolved_skills)
    identifiers = [c.identifier for c in result.capabilities]
    assert identifiers.count("cap-shared") == 1


def test_same_cap_from_two_skills_deduplicated() -> None:
    """The same capability required by two different skills appears only once."""
    cap_reg = InMemoryCapabilityRegistry()
    cap_reg.register(capability("cap-common"))
    resolver = CapabilityResolver(cap_reg)

    skill_reg = InMemorySkillRegistry()
    skill_reg.register(skill("skill-a", capabilities=("cap-common",)))
    skill_reg.register(skill("skill-b", capabilities=("cap-common",)))
    skill_resolver = SkillResolver(skill_reg)
    request = hrequest(
        "node-1",
        skills=(ref("skill", "skill-a"), ref("skill", "skill-b")),
    )
    resolved_skills = skill_resolver.resolve(request)

    result = resolver.resolve(request, resolved_skills)
    identifiers = [c.identifier for c in result.capabilities]
    assert identifiers.count("cap-common") == 1


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


def test_output_sorted_by_identifier_ascending() -> None:
    """ResolvedCapabilities.capabilities is sorted alphabetically by identifier."""
    resolver = _cap_resolver("cap-z", "cap-a", "cap-m")
    request = hrequest(
        "node-1",
        capabilities=(
            ref("capability", "cap-z"),
            ref("capability", "cap-a"),
            ref("capability", "cap-m"),
        ),
    )
    result = resolver.resolve(request, _no_skills())
    identifiers = [c.identifier for c in result.capabilities]
    assert identifiers == sorted(identifiers)


def test_sorting_spans_request_and_skill_sources() -> None:
    """Sorting is applied across the union of direct and skill-implied caps."""
    cap_reg = InMemoryCapabilityRegistry()
    for cid in ("cap-z", "cap-a"):
        cap_reg.register(capability(cid))
    resolver = CapabilityResolver(cap_reg)

    resolved_skills = _resolve_skills(("skill-s",), caps=("cap-z",))
    request = hrequest(
        "node-1",
        capabilities=(ref("capability", "cap-a"),),
    )

    result = resolver.resolve(request, resolved_skills)
    identifiers = [c.identifier for c in result.capabilities]
    assert identifiers == sorted(identifiers)


# ---------------------------------------------------------------------------
# Missing capability — fail-closed
# ---------------------------------------------------------------------------


def test_missing_direct_cap_raises_error() -> None:
    """A direct capability ref whose identifier is absent raises UnresolvedReferenceError."""
    resolver = _cap_resolver()  # empty registry
    request = hrequest("node-1", capabilities=(ref("capability", "cap-ghost"),))
    with pytest.raises(UnresolvedReferenceError):
        resolver.resolve(request, _no_skills())


def test_error_message_contains_missing_cap_identifier() -> None:
    """The UnresolvedReferenceError message names the unresolvable capability."""
    resolver = _cap_resolver()
    request = hrequest("node-1", capabilities=(ref("capability", "cap-phantom"),))
    with pytest.raises(UnresolvedReferenceError, match="cap-phantom"):
        resolver.resolve(request, _no_skills())


def test_missing_skill_implied_cap_raises_error() -> None:
    """A skill-implied cap that is absent from the registry raises UnresolvedReferenceError."""
    cap_reg = InMemoryCapabilityRegistry()  # cap-missing NOT registered
    resolver = CapabilityResolver(cap_reg)

    resolved_skills = _resolve_skills(("skill-a",), caps=("cap-missing",))
    request = hrequest("node-1", skills=(ref("skill", "skill-a"),))

    with pytest.raises(UnresolvedReferenceError):
        resolver.resolve(request, resolved_skills)


def test_partial_miss_on_direct_caps_raises_error() -> None:
    """One resolvable + one missing direct cap still raises UnresolvedReferenceError."""
    resolver = _cap_resolver("cap-present")
    request = hrequest(
        "node-1",
        capabilities=(
            ref("capability", "cap-present"),
            ref("capability", "cap-absent"),
        ),
    )
    with pytest.raises(UnresolvedReferenceError):
        resolver.resolve(request, _no_skills())


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_resolving_twice_yields_equal_results() -> None:
    """Calling resolve twice on the same inputs produces identical ResolvedCapabilities."""
    resolver = _cap_resolver("cap-a", "cap-b")
    request = hrequest(
        "node-1",
        capabilities=(ref("capability", "cap-b"), ref("capability", "cap-a")),
    )
    first = resolver.resolve(request, _no_skills())
    second = resolver.resolve(request, _no_skills())
    assert first == second


def test_determinism_with_skill_implied_caps() -> None:
    """Determinism holds when capabilities come from both direct refs and skills."""
    cap_reg = InMemoryCapabilityRegistry()
    for cid in ("cap-direct", "cap-from-skill"):
        cap_reg.register(capability(cid))
    resolver = CapabilityResolver(cap_reg)

    resolved_skills = _resolve_skills(("skill-a",), caps=("cap-from-skill",))
    request = hrequest(
        "node-1",
        capabilities=(ref("capability", "cap-direct"),),
    )

    first = resolver.resolve(request, resolved_skills)
    second = resolver.resolve(request, resolved_skills)
    assert first == second
    assert [c.identifier for c in first.capabilities] == [c.identifier for c in second.capabilities]


# ---------------------------------------------------------------------------
# Direct construction of ResolvedSkills (without SkillResolver)
# ---------------------------------------------------------------------------


def test_manually_constructed_resolved_skills_feeds_capability_resolver() -> None:
    """CapabilityResolver accepts a manually constructed ResolvedSkills."""
    cap_reg = InMemoryCapabilityRegistry()
    cap_reg.register(capability("cap-hand-built"))
    cap_resolver = CapabilityResolver(cap_reg)

    manual_skill = ResolvedSkill(
        reference=ref("skill", "skill-manual"),
        identity="skill-manual",
        name="Skill Manual",
        version="1",
        required_capability_refs=(ref("capability", "cap-hand-built"),),
    )
    manual_skills = ResolvedSkills(skills=(manual_skill,))
    request = hrequest("node-1")

    result = cap_resolver.resolve(request, manual_skills)
    assert len(result.capabilities) == 1
    assert result.capabilities[0].identifier == "cap-hand-built"


# ---------------------------------------------------------------------------
# Union semantics — comprehensive
# ---------------------------------------------------------------------------


def test_union_of_direct_and_skill_implied_caps() -> None:
    """The output is the full union of direct request caps and skill-implied caps."""
    cap_reg = InMemoryCapabilityRegistry()
    for cid in ("cap-direct", "cap-skill", "cap-shared"):
        cap_reg.register(capability(cid))
    resolver = CapabilityResolver(cap_reg)

    resolved_skills = _resolve_skills(("skill-a",), caps=("cap-skill", "cap-shared"))
    request = hrequest(
        "node-1",
        capabilities=(
            ref("capability", "cap-direct"),
            ref("capability", "cap-shared"),
        ),
    )

    result = resolver.resolve(request, resolved_skills)
    identifiers = {c.identifier for c in result.capabilities}
    assert identifiers == {"cap-direct", "cap-skill", "cap-shared"}
    # and deduplicated
    assert len(result.capabilities) == 3


# ---------------------------------------------------------------------------
# Frozen / immutability
# ---------------------------------------------------------------------------


def test_resolved_capability_is_frozen() -> None:
    """ResolvedCapability must reject attribute mutation (Pydantic frozen model)."""
    resolver = _cap_resolver("cap-alpha")
    request = hrequest("node-1", capabilities=(ref("capability", "cap-alpha"),))
    cap = resolver.resolve(request, _no_skills()).capabilities[0]
    with pytest.raises(ValueError):
        cap.identifier = "tampered"  # type: ignore[misc]


def test_resolved_capabilities_is_frozen() -> None:
    """ResolvedCapabilities must reject attribute mutation (Pydantic frozen model)."""
    resolver = _cap_resolver("cap-alpha")
    request = hrequest("node-1", capabilities=(ref("capability", "cap-alpha"),))
    result = resolver.resolve(request, _no_skills())
    with pytest.raises(ValueError):
        result.capabilities = ()  # type: ignore[misc]
