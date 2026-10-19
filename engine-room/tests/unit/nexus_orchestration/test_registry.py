"""Unit tests for the in-memory Harness Registry (ADR-002, INV-36, INV-37).

These tests cover the register/get round-trip, capability discovery
(candidates only, sorted by identity), availability projection, the sorted
``list_all`` listing, and runtime-checkable conformance to the frozen
``HarnessRegistry`` Protocol.
"""

from __future__ import annotations

from nexus_core.contracts.enums import ResourceAvailability
from nexus_core.registries.interfaces import HarnessRegistry
from nexus_orchestration import InMemoryHarnessRegistry
from tests.unit.nexus_orchestration.helpers import harness


def test_register_then_get_round_trip() -> None:
    registry = InMemoryHarnessRegistry()
    descriptor = harness("h-1", capabilities=("cap-x",))
    registry.register(descriptor)
    assert registry.get("h-1") == descriptor


def test_get_unknown_returns_none() -> None:
    registry = InMemoryHarnessRegistry()
    assert registry.get("missing") is None


def test_discover_by_capability_returns_advertisers_sorted() -> None:
    registry = InMemoryHarnessRegistry()
    second = harness("h-2", capabilities=("cap-x",))
    first = harness("h-1", capabilities=("cap-x",))
    other = harness("h-3", capabilities=("cap-y",))
    registry.register(second)
    registry.register(first)
    registry.register(other)

    matches = registry.discover_by_capability("cap-x")

    assert matches == (first, second)
    assert [d.identity for d in matches] == ["h-1", "h-2"]
    assert other not in matches


def test_discover_by_capability_excludes_non_advertisers() -> None:
    registry = InMemoryHarnessRegistry()
    registry.register(harness("h-1", capabilities=("cap-y",)))
    assert registry.discover_by_capability("cap-x") == ()


def test_availability_returns_descriptor_default_unknown() -> None:
    registry = InMemoryHarnessRegistry()
    registry.register(harness("h-1", capabilities=("cap-x",)))
    assert registry.availability("h-1") == ResourceAvailability.UNKNOWN


def test_availability_unknown_identity_returns_none() -> None:
    registry = InMemoryHarnessRegistry()
    assert registry.availability("missing") is None


def test_list_all_sorted_by_identity() -> None:
    registry = InMemoryHarnessRegistry()
    registry.register(harness("h-3"))
    registry.register(harness("h-1"))
    registry.register(harness("h-2"))

    listed = registry.list_all()

    assert [d.identity for d in listed] == ["h-1", "h-2", "h-3"]


def test_list_all_empty_registry() -> None:
    registry = InMemoryHarnessRegistry()
    assert registry.list_all() == ()


def test_is_instance_of_harness_registry_protocol() -> None:
    assert isinstance(InMemoryHarnessRegistry(), HarnessRegistry)
