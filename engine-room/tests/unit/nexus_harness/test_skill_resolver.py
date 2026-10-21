"""Unit tests for nexus_harness.skill_resolver.

Covers SkillResolver.resolve():
- Resolves skill-typed refs from request.required_skill_refs against the registry.
- Output is sorted by skill identity; each ResolvedSkill carries the correct fields.
- Capability-typed refs in required_skill_refs are silently ignored.
- A missing skill raises UnresolvedReferenceError (fail-closed).
- Empty skill refs produce an empty ResolvedSkills.
- Determinism: resolving twice yields equal results; input order does not affect output.
- ResolvedSkill and ResolvedSkills are frozen (mutations are rejected).
"""

from __future__ import annotations

import pytest

from nexus_harness import (
    InMemorySkillRegistry,
    ResolvedSkills,
    SkillResolver,
    UnresolvedReferenceError,
)
from tests.unit.nexus_harness.helpers import hrequest, ref, skill

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolver(*skills_to_register: str, capabilities: tuple[str, ...] = ()) -> SkillResolver:
    """Return a SkillResolver pre-loaded with the given skill identities."""
    reg = InMemorySkillRegistry()
    for identity in skills_to_register:
        reg.register(skill(identity, capabilities=capabilities))
    return SkillResolver(reg)


# ---------------------------------------------------------------------------
# Empty request
# ---------------------------------------------------------------------------


def test_no_skill_refs_returns_empty_resolved_skills() -> None:
    """A request with no skill refs resolves to an empty ResolvedSkills."""
    resolver = _resolver("skill-a")
    request = hrequest("node-1")
    result = resolver.resolve(request)
    assert result == ResolvedSkills()
    assert result.skills == ()


# ---------------------------------------------------------------------------
# Single skill
# ---------------------------------------------------------------------------


def test_resolves_single_skill_ref() -> None:
    """A request with one skill ref resolves to exactly one ResolvedSkill."""
    resolver = _resolver("skill-alpha")
    request = hrequest("node-1", skills=(ref("skill", "skill-alpha"),))
    result = resolver.resolve(request)
    assert len(result.skills) == 1


def test_resolved_skill_reference_target_type_is_skill() -> None:
    """ResolvedSkill.reference.target_type is always 'skill'."""
    resolver = _resolver("skill-alpha")
    request = hrequest("node-1", skills=(ref("skill", "skill-alpha"),))
    resolved = resolver.resolve(request).skills[0]
    assert resolved.reference.target_type == "skill"


def test_resolved_skill_reference_identifier_matches_identity() -> None:
    """ResolvedSkill.reference.identifier echoes the skill's identity."""
    resolver = _resolver("skill-alpha")
    request = hrequest("node-1", skills=(ref("skill", "skill-alpha"),))
    resolved = resolver.resolve(request).skills[0]
    assert resolved.reference.identifier == "skill-alpha"


def test_resolved_skill_identity_matches_registry() -> None:
    """ResolvedSkill.identity equals the identity stored in the registry."""
    resolver = _resolver("skill-alpha")
    request = hrequest("node-1", skills=(ref("skill", "skill-alpha"),))
    resolved = resolver.resolve(request).skills[0]
    assert resolved.identity == "skill-alpha"


def test_resolved_skill_name_derived_from_identity() -> None:
    """ResolvedSkill.name is populated from the registry entry (title-cased)."""
    resolver = _resolver("skill-alpha")
    request = hrequest("node-1", skills=(ref("skill", "skill-alpha"),))
    resolved = resolver.resolve(request).skills[0]
    assert resolved.name == "Skill Alpha"


def test_resolved_skill_version_defaults_to_one() -> None:
    """ResolvedSkill.version is '1' when built with the default helper version."""
    resolver = _resolver("skill-alpha")
    request = hrequest("node-1", skills=(ref("skill", "skill-alpha"),))
    resolved = resolver.resolve(request).skills[0]
    assert resolved.version == "1"


def test_resolved_skill_required_capability_refs_empty_when_none() -> None:
    """required_capability_refs is an empty tuple when the skill needs no capabilities."""
    resolver = _resolver("skill-alpha")
    request = hrequest("node-1", skills=(ref("skill", "skill-alpha"),))
    resolved = resolver.resolve(request).skills[0]
    assert resolved.required_capability_refs == ()


def test_resolved_skill_required_capability_refs_copied_from_skill() -> None:
    """required_capability_refs on ResolvedSkill mirrors the registry skill's refs."""
    reg = InMemorySkillRegistry()
    reg.register(skill("skill-b", capabilities=("cap-x", "cap-y")))
    resolver = SkillResolver(reg)
    request = hrequest("node-1", skills=(ref("skill", "skill-b"),))
    resolved = resolver.resolve(request).skills[0]
    identifiers = {r.identifier for r in resolved.required_capability_refs}
    assert identifiers == {"cap-x", "cap-y"}


# ---------------------------------------------------------------------------
# Capability refs in required_skill_refs are ignored
# ---------------------------------------------------------------------------


def test_capability_typed_ref_in_skill_refs_is_ignored() -> None:
    """A capability-typed ref in required_skill_refs must not be resolved as a skill."""
    reg = InMemorySkillRegistry()
    reg.register(skill("skill-a"))
    resolver = SkillResolver(reg)
    request = hrequest(
        "node-1",
        skills=(
            ref("skill", "skill-a"),
            ref("capability", "cap-x"),  # must be ignored
        ),
    )
    result = resolver.resolve(request)
    assert len(result.skills) == 1
    assert result.skills[0].identity == "skill-a"


def test_only_capability_typed_refs_yields_empty_skills() -> None:
    """When all refs in required_skill_refs are capability-typed, result is empty."""
    resolver = _resolver()
    request = hrequest(
        "node-1",
        skills=(ref("capability", "cap-x"), ref("capability", "cap-y")),
    )
    result = resolver.resolve(request)
    assert result.skills == ()


# ---------------------------------------------------------------------------
# Missing skill — fail-closed
# ---------------------------------------------------------------------------


def test_missing_skill_raises_unresolved_reference_error() -> None:
    """A skill ref whose identifier has no registry entry raises UnresolvedReferenceError."""
    resolver = _resolver()  # empty registry
    request = hrequest("node-1", skills=(ref("skill", "skill-missing"),))
    with pytest.raises(UnresolvedReferenceError):
        resolver.resolve(request)


def test_error_message_contains_missing_identifier() -> None:
    """The UnresolvedReferenceError message names the unresolvable skill."""
    resolver = _resolver()
    request = hrequest("node-1", skills=(ref("skill", "skill-ghost"),))
    with pytest.raises(UnresolvedReferenceError, match="skill-ghost"):
        resolver.resolve(request)


def test_partial_miss_raises_error() -> None:
    """One resolvable + one missing skill ref still raises UnresolvedReferenceError."""
    resolver = _resolver("skill-present")
    request = hrequest(
        "node-1",
        skills=(ref("skill", "skill-present"), ref("skill", "skill-absent")),
    )
    with pytest.raises(UnresolvedReferenceError):
        resolver.resolve(request)


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


def test_output_sorted_by_identity_ascending() -> None:
    """ResolvedSkills.skills is always sorted by skill identity, ascending."""
    reg = InMemorySkillRegistry()
    reg.register(skill("skill-z"))
    reg.register(skill("skill-a"))
    reg.register(skill("skill-m"))
    resolver = SkillResolver(reg)
    request = hrequest(
        "node-1",
        skills=(
            ref("skill", "skill-z"),
            ref("skill", "skill-a"),
            ref("skill", "skill-m"),
        ),
    )
    result = resolver.resolve(request)
    identities = [s.identity for s in result.skills]
    assert identities == sorted(identities)


def test_reverse_input_order_same_output_order() -> None:
    """Input order of refs does not affect the sorted output order."""
    reg = InMemorySkillRegistry()
    reg.register(skill("skill-a"))
    reg.register(skill("skill-b"))
    resolver = SkillResolver(reg)

    request_fwd = hrequest(
        "node-1",
        skills=(ref("skill", "skill-a"), ref("skill", "skill-b")),
    )
    request_rev = hrequest(
        "node-1",
        skills=(ref("skill", "skill-b"), ref("skill", "skill-a")),
    )

    result_fwd = resolver.resolve(request_fwd)
    result_rev = resolver.resolve(request_rev)
    assert [s.identity for s in result_fwd.skills] == [s.identity for s in result_rev.skills]


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_resolving_twice_yields_equal_results() -> None:
    """Calling resolve twice on the same request produces identical ResolvedSkills."""
    resolver = _resolver("skill-a", "skill-b")
    request = hrequest(
        "node-1",
        skills=(ref("skill", "skill-a"), ref("skill", "skill-b")),
    )
    assert resolver.resolve(request) == resolver.resolve(request)


def test_determinism_with_multiple_skills() -> None:
    """Repeated resolution of a multi-skill request yields structurally equal objects."""
    reg = InMemorySkillRegistry()
    for name in ("skill-c", "skill-a", "skill-b"):
        reg.register(skill(name, capabilities=("cap-x",)))
    resolver = SkillResolver(reg)
    request = hrequest(
        "node-1",
        skills=(
            ref("skill", "skill-c"),
            ref("skill", "skill-a"),
            ref("skill", "skill-b"),
        ),
    )
    first = resolver.resolve(request)
    second = resolver.resolve(request)
    assert first == second
    assert [s.identity for s in first.skills] == [s.identity for s in second.skills]


# ---------------------------------------------------------------------------
# Multiple skills — field correctness
# ---------------------------------------------------------------------------


def test_multiple_skills_all_resolved() -> None:
    """Every skill ref in the request produces a ResolvedSkill entry."""
    resolver = _resolver("skill-alpha", "skill-beta", "skill-gamma")
    request = hrequest(
        "node-1",
        skills=(
            ref("skill", "skill-alpha"),
            ref("skill", "skill-beta"),
            ref("skill", "skill-gamma"),
        ),
    )
    result = resolver.resolve(request)
    assert len(result.skills) == 3


def test_each_resolved_skill_carries_correct_identity() -> None:
    """Each ResolvedSkill holds the identity from the registry."""
    reg = InMemorySkillRegistry()
    reg.register(skill("skill-one"))
    reg.register(skill("skill-two"))
    resolver = SkillResolver(reg)
    request = hrequest(
        "node-1",
        skills=(ref("skill", "skill-two"), ref("skill", "skill-one")),
    )
    result = resolver.resolve(request)
    identities = {s.identity for s in result.skills}
    assert identities == {"skill-one", "skill-two"}


# ---------------------------------------------------------------------------
# Frozen / immutability
# ---------------------------------------------------------------------------


def test_resolved_skill_is_frozen() -> None:
    """ResolvedSkill must reject attribute mutation (Pydantic frozen model)."""
    resolver = _resolver("skill-alpha")
    request = hrequest("node-1", skills=(ref("skill", "skill-alpha"),))
    resolved = resolver.resolve(request).skills[0]
    with pytest.raises(ValueError):
        resolved.identity = "tampered"  # type: ignore[misc]


def test_resolved_skills_is_frozen() -> None:
    """ResolvedSkills must reject attribute mutation (Pydantic frozen model)."""
    resolver = _resolver("skill-alpha")
    request = hrequest("node-1", skills=(ref("skill", "skill-alpha"),))
    result = resolver.resolve(request)
    with pytest.raises(ValueError):
        result.skills = ()  # type: ignore[misc]
