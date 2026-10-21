"""Unit tests for nexus_harness.sources — in-memory registry implementations.

Verifies that each registry registers/gets/lists deterministically, satisfies its
nexus_core Protocol via runtime-checkable isinstance, and that HarnessSources is
a frozen dataclass.
"""

from __future__ import annotations

import pytest

from nexus_core.contracts.enums import (
    CapabilityCategory,
    PolicyCategory,
    SkillCategory,
)
from nexus_core.registries.interfaces import (
    CapabilityRegistry,
    PolicyRegistry,
    SkillRegistry,
)
from nexus_harness.sources import (
    InMemoryCapabilityRegistry,
    InMemoryPolicyRegistry,
    InMemorySkillRegistry,
)
from tests.unit.nexus_harness.helpers import (
    HarnessEnv,
    capability,
    harness_env,
    policy,
    skill,
    standard_env,
)

# --------------------------------------------------------------------------- #
# Protocol conformance                                                          #
# --------------------------------------------------------------------------- #


def test_in_memory_skill_registry_satisfies_protocol() -> None:
    reg = InMemorySkillRegistry()

    assert isinstance(reg, SkillRegistry)


def test_in_memory_capability_registry_satisfies_protocol() -> None:
    reg = InMemoryCapabilityRegistry()

    assert isinstance(reg, CapabilityRegistry)


def test_in_memory_policy_registry_satisfies_protocol() -> None:
    reg = InMemoryPolicyRegistry()

    assert isinstance(reg, PolicyRegistry)


# --------------------------------------------------------------------------- #
# HarnessSources is a frozen dataclass                                         #
# --------------------------------------------------------------------------- #


def test_harness_sources_is_frozen() -> None:
    env: HarnessEnv = standard_env()
    sources = env.harness.sources

    with pytest.raises((TypeError, AttributeError)):
        sources.skills = InMemorySkillRegistry()  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# InMemorySkillRegistry                                                         #
# --------------------------------------------------------------------------- #


def test_skill_registry_get_returns_registered_skill() -> None:
    reg = InMemorySkillRegistry()
    s = skill("skill-a")
    reg.register(s)

    assert reg.get("skill-a") is s


def test_skill_registry_get_returns_none_for_missing() -> None:
    reg = InMemorySkillRegistry()

    assert reg.get("does-not-exist") is None


def test_skill_registry_get_returns_none_on_version_mismatch() -> None:
    reg = InMemorySkillRegistry()
    reg.register(skill("skill-a", version="1"))

    assert reg.get("skill-a", version="99") is None


def test_skill_registry_get_returns_skill_on_version_match() -> None:
    reg = InMemorySkillRegistry()
    s = skill("skill-a", version="2")
    reg.register(s)

    assert reg.get("skill-a", version="2") is s


def test_skill_registry_list_all_is_sorted_by_identity() -> None:
    reg = InMemorySkillRegistry()
    reg.register(skill("skill-zebra"))
    reg.register(skill("skill-alpha"))
    reg.register(skill("skill-middle"))

    result = reg.list_all()

    identities = [s.identity for s in result]
    assert identities == sorted(identities)


def test_skill_registry_list_all_empty_returns_empty_tuple() -> None:
    reg = InMemorySkillRegistry()

    assert reg.list_all() == ()


def test_skill_registry_find_by_category_filters_and_sorts() -> None:
    reg = InMemorySkillRegistry()
    reg.register(skill("skill-dev-b", category=SkillCategory.DEVELOPMENT))
    reg.register(skill("skill-analysis", category=SkillCategory.ANALYSIS))
    reg.register(skill("skill-dev-a", category=SkillCategory.DEVELOPMENT))

    result = reg.find_by_category(SkillCategory.DEVELOPMENT)

    assert all(s.category == SkillCategory.DEVELOPMENT for s in result)
    identities = [s.identity for s in result]
    assert identities == sorted(identities)


def test_skill_registry_find_by_category_returns_empty_for_no_match() -> None:
    reg = InMemorySkillRegistry()
    reg.register(skill("skill-analysis", category=SkillCategory.ANALYSIS))

    result = reg.find_by_category(SkillCategory.OPERATIONS)

    assert result == ()


def test_skill_registry_keys_by_identity() -> None:
    """A second register with the same identity overwrites the first."""
    reg = InMemorySkillRegistry()
    first = skill("skill-a", version="1")
    second = skill("skill-a", version="2")
    reg.register(first)
    reg.register(second)

    assert reg.get("skill-a") is second
    assert len(reg.list_all()) == 1


# --------------------------------------------------------------------------- #
# InMemoryCapabilityRegistry                                                    #
# --------------------------------------------------------------------------- #


def test_capability_registry_get_returns_registered_capability() -> None:
    reg = InMemoryCapabilityRegistry()
    cap = capability("cap-a")
    reg.register(cap)

    assert reg.get("cap-a") is cap


def test_capability_registry_get_returns_none_for_missing() -> None:
    reg = InMemoryCapabilityRegistry()

    assert reg.get("does-not-exist") is None


def test_capability_registry_get_returns_none_on_version_mismatch() -> None:
    reg = InMemoryCapabilityRegistry()
    reg.register(capability("cap-a", version="1"))

    assert reg.get("cap-a", version="99") is None


def test_capability_registry_get_returns_capability_on_version_match() -> None:
    reg = InMemoryCapabilityRegistry()
    cap = capability("cap-a", version="3")
    reg.register(cap)

    assert reg.get("cap-a", version="3") is cap


def test_capability_registry_list_all_is_sorted_by_identifier() -> None:
    reg = InMemoryCapabilityRegistry()
    reg.register(capability("cap-z"))
    reg.register(capability("cap-a"))
    reg.register(capability("cap-m"))

    result = reg.list_all()

    identifiers = [c.identifier for c in result]
    assert identifiers == sorted(identifiers)


def test_capability_registry_list_all_empty_returns_empty_tuple() -> None:
    reg = InMemoryCapabilityRegistry()

    assert reg.list_all() == ()


def test_capability_registry_find_by_category_filters_and_sorts() -> None:
    reg = InMemoryCapabilityRegistry()
    reg.register(capability("cap-dev-b", category=CapabilityCategory.DEVELOPMENT))
    reg.register(capability("cap-analysis", category=CapabilityCategory.ANALYSIS))
    reg.register(capability("cap-dev-a", category=CapabilityCategory.DEVELOPMENT))

    result = reg.find_by_category(CapabilityCategory.DEVELOPMENT)

    assert all(c.category == CapabilityCategory.DEVELOPMENT for c in result)
    identifiers = [c.identifier for c in result]
    assert identifiers == sorted(identifiers)


def test_capability_registry_find_by_category_returns_empty_for_no_match() -> None:
    reg = InMemoryCapabilityRegistry()
    reg.register(capability("cap-analysis", category=CapabilityCategory.ANALYSIS))

    result = reg.find_by_category(CapabilityCategory.OPERATIONS)

    assert result == ()


def test_capability_registry_keys_by_identifier() -> None:
    """A second register with the same identifier overwrites the first."""
    reg = InMemoryCapabilityRegistry()
    first = capability("cap-a", version="1")
    second = capability("cap-a", version="2")
    reg.register(first)
    reg.register(second)

    assert reg.get("cap-a") is second
    assert len(reg.list_all()) == 1


# --------------------------------------------------------------------------- #
# InMemoryPolicyRegistry                                                        #
# --------------------------------------------------------------------------- #


def test_policy_registry_get_returns_registered_policy() -> None:
    reg = InMemoryPolicyRegistry()
    p = policy("policy-a")
    reg.register(p)

    assert reg.get("policy-a") is p


def test_policy_registry_get_returns_none_for_missing() -> None:
    reg = InMemoryPolicyRegistry()

    assert reg.get("does-not-exist") is None


def test_policy_registry_get_returns_none_on_version_mismatch() -> None:
    reg = InMemoryPolicyRegistry()
    reg.register(policy("policy-a", version="1"))

    assert reg.get("policy-a", version="99") is None


def test_policy_registry_get_returns_policy_on_version_match() -> None:
    reg = InMemoryPolicyRegistry()
    p = policy("policy-a", version="5")
    reg.register(p)

    assert reg.get("policy-a", version="5") is p


def test_policy_registry_list_all_is_sorted_by_identity_then_version() -> None:
    reg = InMemoryPolicyRegistry()
    reg.register(policy("policy-z", version="1"))
    reg.register(policy("policy-a", version="2"))
    reg.register(policy("policy-m", version="1"))

    result = reg.list_all()

    keys = [(p.identity, p.version) for p in result]
    assert keys == sorted(keys)


def test_policy_registry_list_all_empty_returns_empty_tuple() -> None:
    reg = InMemoryPolicyRegistry()

    assert reg.list_all() == ()


def test_policy_registry_enabled_returns_all_registered_policies() -> None:
    reg = InMemoryPolicyRegistry()
    p1 = policy("policy-a")
    p2 = policy("policy-b")
    reg.register(p1)
    reg.register(p2)

    enabled = reg.enabled()

    assert sorted(e.identity for e in enabled) == [p1.identity, p2.identity]


def test_policy_registry_enabled_sorted_by_identity_and_version() -> None:
    reg = InMemoryPolicyRegistry()
    reg.register(policy("policy-z", version="1"))
    reg.register(policy("policy-a", version="1"))

    enabled = reg.enabled()

    keys = [(p.identity, p.version) for p in enabled]
    assert keys == sorted(keys)


def test_policy_registry_find_by_category_filters_and_sorts() -> None:
    reg = InMemoryPolicyRegistry()
    reg.register(policy("policy-gov-b", category=PolicyCategory.GOVERNANCE))
    reg.register(policy("policy-exec", category=PolicyCategory.EXECUTION))
    reg.register(policy("policy-gov-a", category=PolicyCategory.GOVERNANCE))

    result = reg.find_by_category(PolicyCategory.GOVERNANCE)

    assert all(p.category == PolicyCategory.GOVERNANCE for p in result)
    keys = [(p.identity, p.version) for p in result]
    assert keys == sorted(keys)


def test_policy_registry_find_by_category_returns_empty_for_no_match() -> None:
    reg = InMemoryPolicyRegistry()
    reg.register(policy("policy-gov", category=PolicyCategory.GOVERNANCE))

    result = reg.find_by_category(PolicyCategory.VALIDATION)

    assert result == ()


# --------------------------------------------------------------------------- #
# HarnessSources integration with harness_env                                  #
# --------------------------------------------------------------------------- #


def test_harness_sources_exposes_populated_registries() -> None:
    env = harness_env(
        skills=(skill("skill-a"),),
        capabilities=(capability("cap-a"),),
        policies=(policy("policy-a"),),
    )
    sources = env.harness.sources

    assert sources.skills.get("skill-a") is not None
    assert sources.capabilities.get("cap-a") is not None
    assert sources.policies.get("policy-a") is not None
