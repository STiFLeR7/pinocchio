"""Unit tests for the four registry Protocols and ``HarnessDescriptor``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import (
    CapabilityCategory,
    PolicyCategory,
    PolicyDecision,
    ResourceAvailability,
    SkillCategory,
)
from nexus_core.domain.capability import Capability
from nexus_core.domain.policy import Policy
from nexus_core.domain.skill import Skill
from nexus_core.registries.interfaces import (
    CapabilityRegistry,
    HarnessCategory,
    HarnessDescriptor,
    HarnessRegistry,
    PolicyRegistry,
    SkillRegistry,
)

# --------------------------------------------------------------------------- #
# Builders                                                                     #
# --------------------------------------------------------------------------- #


def _build_capability() -> Capability:
    return Capability(
        identifier="cap-1",
        name="Repository Analysis",
        version="1.0.0",
        category=CapabilityCategory.ANALYSIS,
        description="Analyze a repository.",
        inputs=({"role": "repository"},),
        outputs=({"role": "analysis"},),
    )


def _build_skill() -> Skill:
    return Skill(
        identity="skill-1",
        name="Run Tests",
        version="1.0.0",
        purpose="Execute the project's test suite.",
        inputs=({"role": "repository"},),
        outputs=({"role": "report"},),
        procedure={"phases": ["setup", "run"]},
        category=SkillCategory.DEVELOPMENT,
    )


def _build_policy() -> Policy:
    return Policy(
        identity="pol-1",
        version="1.0.0",
        purpose="Require approval for production deploys.",
        conditions={"action": "deploy"},
        decision=PolicyDecision.REQUIRE_APPROVAL,
        priority=10,
        owner="governance",
        category=PolicyCategory.GOVERNANCE,
    )


def _build_descriptor() -> HarnessDescriptor:
    return HarnessDescriptor(
        identity="harness-1",
        category=HarnessCategory.RUNTIME,
        version="1.0.0",
        advertised_capabilities=(Reference(target_type="capability", identifier="cap-1"),),
    )


# --------------------------------------------------------------------------- #
# In-memory fakes                                                             #
# --------------------------------------------------------------------------- #


class FakeCapabilityRegistry:
    def __init__(self) -> None:
        self._items: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        self._items[capability.identifier] = capability

    def get(self, identifier: str, version: str | None = None) -> Capability | None:
        cap = self._items.get(identifier)
        if cap is not None and version is not None and cap.version != version:
            return None
        return cap

    def find_by_category(self, category: CapabilityCategory) -> tuple[Capability, ...]:
        return tuple(c for c in self._items.values() if c.category == category)

    def list_all(self) -> tuple[Capability, ...]:
        return tuple(self._items.values())


class FakeHarnessRegistry:
    def __init__(self) -> None:
        self._items: dict[str, HarnessDescriptor] = {}

    def register(self, descriptor: HarnessDescriptor) -> None:
        self._items[descriptor.identity] = descriptor

    def get(self, identity: str) -> HarnessDescriptor | None:
        return self._items.get(identity)

    def discover_by_capability(self, capability_identifier: str) -> tuple[HarnessDescriptor, ...]:
        return tuple(
            d
            for d in self._items.values()
            if any(ref.identifier == capability_identifier for ref in d.advertised_capabilities)
        )

    def availability(self, identity: str) -> ResourceAvailability | None:
        descriptor = self._items.get(identity)
        return descriptor.availability if descriptor is not None else None

    def list_all(self) -> tuple[HarnessDescriptor, ...]:
        return tuple(self._items.values())


class FakeSkillRegistry:
    def __init__(self) -> None:
        self._items: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._items[skill.identity] = skill

    def get(self, identity: str, version: str | None = None) -> Skill | None:
        skill = self._items.get(identity)
        if skill is not None and version is not None and skill.version != version:
            return None
        return skill

    def find_by_category(self, category: SkillCategory) -> tuple[Skill, ...]:
        return tuple(s for s in self._items.values() if s.category == category)

    def list_all(self) -> tuple[Skill, ...]:
        return tuple(self._items.values())


class FakePolicyRegistry:
    def __init__(self) -> None:
        self._items: dict[str, Policy] = {}

    def register(self, policy: Policy) -> None:
        self._items[policy.identity] = policy

    def get(self, identity: str, version: str | None = None) -> Policy | None:
        policy = self._items.get(identity)
        if policy is not None and version is not None and policy.version != version:
            return None
        return policy

    def find_by_category(self, category: PolicyCategory) -> tuple[Policy, ...]:
        return tuple(p for p in self._items.values() if p.category == category)

    def enabled(self) -> tuple[Policy, ...]:
        return tuple(self._items.values())

    def list_all(self) -> tuple[Policy, ...]:
        return tuple(self._items.values())


# --------------------------------------------------------------------------- #
# Protocol conformance                                                        #
# --------------------------------------------------------------------------- #


def test_fakes_satisfy_runtime_checkable_protocols() -> None:
    assert isinstance(FakeCapabilityRegistry(), CapabilityRegistry)
    assert isinstance(FakeHarnessRegistry(), HarnessRegistry)
    assert isinstance(FakeSkillRegistry(), SkillRegistry)
    assert isinstance(FakePolicyRegistry(), PolicyRegistry)


# --------------------------------------------------------------------------- #
# Round trips                                                                  #
# --------------------------------------------------------------------------- #


def test_capability_registry_round_trip() -> None:
    registry = FakeCapabilityRegistry()
    cap = _build_capability()
    registry.register(cap)
    assert registry.get("cap-1") == cap
    assert registry.get("cap-1", "1.0.0") == cap
    assert registry.get("cap-1", "9.9.9") is None
    assert registry.find_by_category(CapabilityCategory.ANALYSIS) == (cap,)
    assert registry.find_by_category(CapabilityCategory.OPERATIONS) == ()
    assert registry.list_all() == (cap,)


def test_harness_registry_round_trip() -> None:
    registry = FakeHarnessRegistry()
    descriptor = _build_descriptor()
    registry.register(descriptor)
    assert registry.get("harness-1") == descriptor
    assert registry.get("absent") is None
    assert registry.discover_by_capability("cap-1") == (descriptor,)
    assert registry.discover_by_capability("cap-absent") == ()
    assert registry.availability("harness-1") is ResourceAvailability.UNKNOWN
    assert registry.availability("absent") is None
    assert registry.list_all() == (descriptor,)


def test_skill_registry_round_trip() -> None:
    registry = FakeSkillRegistry()
    skill = _build_skill()
    registry.register(skill)
    assert registry.get("skill-1") == skill
    assert registry.get("skill-1", "9.9.9") is None
    assert registry.find_by_category(SkillCategory.DEVELOPMENT) == (skill,)
    assert registry.list_all() == (skill,)


def test_policy_registry_round_trip() -> None:
    registry = FakePolicyRegistry()
    policy = _build_policy()
    registry.register(policy)
    assert registry.get("pol-1") == policy
    assert registry.get("pol-1", "9.9.9") is None
    assert registry.find_by_category(PolicyCategory.GOVERNANCE) == (policy,)
    assert registry.enabled() == (policy,)
    assert registry.list_all() == (policy,)


# --------------------------------------------------------------------------- #
# HarnessDescriptor                                                           #
# --------------------------------------------------------------------------- #


def test_harness_descriptor_defaults_availability_and_health_to_unknown() -> None:
    descriptor = _build_descriptor()
    assert descriptor.availability is ResourceAvailability.UNKNOWN
    assert descriptor.health is ResourceAvailability.UNKNOWN
    assert descriptor.configuration is None
    assert descriptor.metadata is None


def test_harness_descriptor_is_immutable() -> None:
    descriptor = _build_descriptor()
    with pytest.raises(ValidationError):
        descriptor.version = "2.0.0"  # type: ignore[misc]


def test_harness_descriptor_explicit_availability() -> None:
    descriptor = HarnessDescriptor(
        identity="harness-2",
        category=HarnessCategory.RUNTIME,
        version="1.0.0",
        availability=ResourceAvailability.AVAILABLE,
        health=ResourceAvailability.BUSY,
    )
    assert descriptor.availability is ResourceAvailability.AVAILABLE
    assert descriptor.health is ResourceAvailability.BUSY
