"""Unit tests for nexus_runtime.runtime_registry.

Covers InMemoryHarnessRegistry and RuntimeRegistry (the RUNTIME-category view)
including all register/get/discover/availability/list branches and the full
resolve_candidates + is_reachable paths.
"""

from __future__ import annotations

import pytest

from nexus_core.contracts.enums import ResourceAvailability
from nexus_core.registries.interfaces import HarnessCategory
from nexus_runtime.runtime_registry import InMemoryHarnessRegistry, RuntimeRegistry
from tests.unit.nexus_runtime.helpers import (
    descriptor,
    ref,
    standard_runtimes,
)

# --------------------------------------------------------------------------- #
# InMemoryHarnessRegistry                                                       #
# --------------------------------------------------------------------------- #


class TestInMemoryHarnessRegistryRegisterAndGet:
    def test_get_returns_descriptor_after_register(self) -> None:
        registry = InMemoryHarnessRegistry()
        d = descriptor("claude-code")
        registry.register(d)

        result = registry.get("claude-code")

        assert result is d

    def test_get_returns_none_for_unknown_identity(self) -> None:
        registry = InMemoryHarnessRegistry()

        result = registry.get("nonexistent")

        assert result is None

    def test_register_overwrites_previous_entry(self) -> None:
        registry = InMemoryHarnessRegistry()
        first = descriptor("rt-a", version="1")
        second = descriptor("rt-a", version="2")
        registry.register(first)
        registry.register(second)

        result = registry.get("rt-a")

        assert result is second


class TestInMemoryHarnessRegistryDiscoverByCapability:
    def test_returns_descriptors_advertising_the_capability(self) -> None:
        registry = InMemoryHarnessRegistry()
        a = descriptor("alpha", capabilities=("code_generation",))
        b = descriptor("beta", capabilities=("code_generation", "file_write"))
        c = descriptor("gamma", capabilities=("shell_exec",))
        registry.register(a)
        registry.register(b)
        registry.register(c)

        results = registry.discover_by_capability("code_generation")

        assert {d.identity for d in results} == {"alpha", "beta"}

    def test_result_is_sorted_by_identity(self) -> None:
        registry = InMemoryHarnessRegistry()
        registry.register(descriptor("z-last", capabilities=("cap-x",)))
        registry.register(descriptor("a-first", capabilities=("cap-x",)))
        registry.register(descriptor("m-mid", capabilities=("cap-x",)))

        results = registry.discover_by_capability("cap-x")

        identities = [d.identity for d in results]
        assert identities == sorted(identities)

    def test_returns_empty_tuple_when_no_match(self) -> None:
        registry = InMemoryHarnessRegistry()
        registry.register(descriptor("rt", capabilities=("shell_exec",)))

        results = registry.discover_by_capability("code_generation")

        assert results == ()

    def test_returns_empty_tuple_when_registry_is_empty(self) -> None:
        registry = InMemoryHarnessRegistry()

        results = registry.discover_by_capability("anything")

        assert results == ()


class TestInMemoryHarnessRegistryAvailability:
    def test_returns_descriptor_availability_for_known_identity(self) -> None:
        registry = InMemoryHarnessRegistry()
        d = descriptor("rt-a", availability=ResourceAvailability.BUSY)
        registry.register(d)

        result = registry.availability("rt-a")

        assert result is ResourceAvailability.BUSY

    def test_returns_none_for_unknown_identity(self) -> None:
        registry = InMemoryHarnessRegistry()

        result = registry.availability("ghost")

        assert result is None


class TestInMemoryHarnessRegistryListAll:
    def test_returns_all_registered_descriptors(self) -> None:
        registry = InMemoryHarnessRegistry()
        runtimes = standard_runtimes()
        for d in runtimes:
            registry.register(d)

        results = registry.list_all()

        assert {d.identity for d in results} == {d.identity for d in runtimes}

    def test_result_is_sorted_by_identity(self) -> None:
        registry = InMemoryHarnessRegistry()
        registry.register(descriptor("z-rt"))
        registry.register(descriptor("a-rt"))
        registry.register(descriptor("m-rt"))

        results = registry.list_all()

        identities = [d.identity for d in results]
        assert identities == sorted(identities)

    def test_returns_empty_tuple_when_empty(self) -> None:
        registry = InMemoryHarnessRegistry()

        assert registry.list_all() == ()


# --------------------------------------------------------------------------- #
# RuntimeRegistry.register                                                      #
# --------------------------------------------------------------------------- #


class TestRuntimeRegistryRegister:
    def test_register_accepts_runtime_descriptor(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        d = descriptor("claude-code", category=HarnessCategory.RUNTIME)

        returned = view.register(d)

        assert returned is d
        assert backing.get("claude-code") is d

    def test_register_raises_value_error_for_non_runtime_category(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        non_runtime = descriptor("ctx-harness", category=HarnessCategory.CONTEXT)

        with pytest.raises(ValueError, match="RUNTIME"):
            view.register(non_runtime)

    def test_register_raises_and_does_not_persist_non_runtime(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        non_runtime = descriptor("ctx-harness", category=HarnessCategory.CONTEXT)

        with pytest.raises(ValueError):
            view.register(non_runtime)

        assert backing.get("ctx-harness") is None

    def test_register_error_message_contains_identity(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        non_runtime = descriptor("my-context-harness", category=HarnessCategory.CONTEXT)

        with pytest.raises(ValueError, match="my-context-harness"):
            view.register(non_runtime)


# --------------------------------------------------------------------------- #
# RuntimeRegistry.get                                                           #
# --------------------------------------------------------------------------- #


class TestRuntimeRegistryGet:
    def test_returns_runtime_descriptor_for_known_runtime(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        d = descriptor("claude-code", category=HarnessCategory.RUNTIME)
        view.register(d)

        result = view.get("claude-code")

        assert result is d

    def test_returns_none_for_missing_identity(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)

        result = view.get("does-not-exist")

        assert result is None

    def test_returns_none_for_non_runtime_registered_in_backing_store(self) -> None:
        # Register a non-RUNTIME descriptor directly in the backing store, bypassing
        # the RuntimeRegistry view, then verify the view filters it out.
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        non_runtime = descriptor("ctx-harness", category=HarnessCategory.CONTEXT)
        backing.register(non_runtime)  # bypass the view intentionally

        result = view.get("ctx-harness")

        assert result is None


# --------------------------------------------------------------------------- #
# RuntimeRegistry.list_runtimes                                                 #
# --------------------------------------------------------------------------- #


class TestRuntimeRegistryListRuntimes:
    def test_returns_only_runtime_category_descriptors(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        rt = descriptor("rt-a", category=HarnessCategory.RUNTIME)
        ctx = descriptor("ctx-b", category=HarnessCategory.CONTEXT)
        backing.register(rt)
        backing.register(ctx)

        results = view.list_runtimes()

        assert len(results) == 1
        assert results[0].identity == "rt-a"

    def test_returns_empty_when_no_runtimes_registered(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        backing.register(descriptor("ctx-only", category=HarnessCategory.CONTEXT))

        assert view.list_runtimes() == ()

    def test_result_is_deterministic_and_sorted_by_identity(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        for name in ("z-rt", "a-rt", "m-rt"):
            view.register(descriptor(name))

        results = view.list_runtimes()

        identities = [d.identity for d in results]
        assert identities == sorted(identities)

    def test_all_standard_runtimes_appear(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        runtimes = standard_runtimes()
        for d in runtimes:
            view.register(d)

        results = view.list_runtimes()

        assert len(results) == len(runtimes)


# --------------------------------------------------------------------------- #
# RuntimeRegistry.resolve_candidates                                            #
# --------------------------------------------------------------------------- #


class TestRuntimeRegistryResolveCandidates:
    def test_resolves_known_runtime_refs_to_descriptors(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        d = descriptor("claude-code")
        view.register(d)
        refs = (ref("harness", "claude-code"),)

        results = view.resolve_candidates(refs)

        assert len(results) == 1
        assert results[0].identity == "claude-code"

    def test_skips_refs_that_do_not_resolve(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        view.register(descriptor("rt-a"))
        refs = (ref("harness", "rt-a"), ref("harness", "ghost"))

        results = view.resolve_candidates(refs)

        assert len(results) == 1
        assert results[0].identity == "rt-a"

    def test_skips_refs_that_resolve_to_non_runtime(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        # Register a non-RUNTIME directly in the backing to simulate a scenario
        # where the ref exists in the store but is not a RUNTIME.
        non_runtime = descriptor("ctx-harness", category=HarnessCategory.CONTEXT)
        backing.register(non_runtime)
        refs = (ref("harness", "ctx-harness"),)

        results = view.resolve_candidates(refs)

        assert results == ()

    def test_returns_empty_for_empty_refs(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)

        results = view.resolve_candidates(())

        assert results == ()

    def test_result_is_sorted_by_identity(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        for name in ("z-rt", "a-rt", "m-rt"):
            view.register(descriptor(name))
        refs = tuple(ref("harness", n) for n in ("z-rt", "m-rt", "a-rt"))

        results = view.resolve_candidates(refs)

        identities = [d.identity for d in results]
        assert identities == sorted(identities)

    def test_deduplicates_repeated_refs(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        view.register(descriptor("rt-a"))
        # Same ref repeated three times.
        refs = (ref("harness", "rt-a"), ref("harness", "rt-a"), ref("harness", "rt-a"))

        results = view.resolve_candidates(refs)

        assert len(results) == 1

    def test_resolves_multiple_valid_refs(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        runtimes = standard_runtimes()
        for d in runtimes:
            view.register(d)
        refs = tuple(ref("harness", d.identity) for d in runtimes)

        results = view.resolve_candidates(refs)

        assert len(results) == len(runtimes)


# --------------------------------------------------------------------------- #
# RuntimeRegistry.is_reachable                                                  #
# --------------------------------------------------------------------------- #


class TestRuntimeRegistryIsReachable:
    def test_available_descriptor_is_reachable(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        d = descriptor("rt-a", availability=ResourceAvailability.AVAILABLE)

        assert view.is_reachable(d) is True

    def test_busy_descriptor_is_not_reachable(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        d = descriptor("rt-a", availability=ResourceAvailability.BUSY)

        assert view.is_reachable(d) is False

    def test_offline_descriptor_is_not_reachable(self) -> None:
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        d = descriptor("rt-a", availability=ResourceAvailability.OFFLINE)

        assert view.is_reachable(d) is False

    def test_unknown_descriptor_is_not_reachable(self) -> None:
        # UNKNOWN is resolved conservatively as not reachable (no silent optimistic assumption).
        backing = InMemoryHarnessRegistry()
        view = RuntimeRegistry(backing)
        d = descriptor("rt-a", availability=ResourceAvailability.UNKNOWN)

        assert view.is_reachable(d) is False
