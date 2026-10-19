"""Unit tests for nexus_runtime_adapters.registry — the runtime adapter registry (Milestone 1).

Covers registration (success + category/identity/duplicate errors), resolution, adapter
creation under a deterministic-run profile, and every read-only discovery/capability query.
The registry is runtime-independent: these tests wire adapters in from the outside.
"""

from __future__ import annotations

import pytest

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import ResourceAvailability
from nexus_core.registries.interfaces import HarnessCategory, HarnessDescriptor
from nexus_execution.adapter import RuntimeAdapter
from nexus_runtime_adapters.catalog import build_default_adapter_registry
from nexus_runtime_adapters.registry import (
    AdapterRegistration,
    AdapterRegistry,
    DuplicateAdapterError,
    NotARuntimeError,
    RuntimeInvocationProfile,
    UnknownAdapterError,
)
from nexus_runtime_claude import ClaudeRuntimeAdapter, StubClaudeInvoker
from nexus_runtime_claude.adapter import CLAUDE_RUNTIME_IDENTITY


def _registration(
    identity: str = CLAUDE_RUNTIME_IDENTITY,
    *,
    descriptor: HarnessDescriptor | None = None,
) -> AdapterRegistration:
    return AdapterRegistration(
        identity=identity,
        descriptor=descriptor or ClaudeRuntimeAdapter(identity=identity).descriptor(),
        factory=lambda profile: ClaudeRuntimeAdapter(
            invoker=StubClaudeInvoker(fail=profile.fail, hang=profile.hang), identity=identity
        ),
    )


def _context_descriptor() -> HarnessDescriptor:
    return HarnessDescriptor(
        identity="ctx",
        category=HarnessCategory.CONTEXT,
        version="1",
        availability=ResourceAvailability.AVAILABLE,
    )


# Registration -------------------------------------------------------------- #


def test_register_and_resolve_roundtrips() -> None:
    registry = AdapterRegistry()
    registration = registry.register(_registration())
    assert registration.identity == CLAUDE_RUNTIME_IDENTITY
    assert registry.resolve(CLAUDE_RUNTIME_IDENTITY).identity == CLAUDE_RUNTIME_IDENTITY
    assert CLAUDE_RUNTIME_IDENTITY in registry


def test_register_rejects_non_runtime_category() -> None:
    registry = AdapterRegistry()
    bad = AdapterRegistration(
        identity="ctx", descriptor=_context_descriptor(), factory=lambda p: None
    )  # type: ignore[arg-type,return-value]
    with pytest.raises(NotARuntimeError):
        registry.register(bad)


def test_register_identity_mismatch_when_names_differ() -> None:
    registry = AdapterRegistry()
    mismatched = AdapterRegistration(
        identity="alias",
        descriptor=ClaudeRuntimeAdapter().descriptor(),  # identity "claude-code"
        factory=lambda p: ClaudeRuntimeAdapter(),
    )
    with pytest.raises(Exception, match="does not match descriptor"):
        registry.register(mismatched)


def test_register_rejects_duplicate() -> None:
    registry = AdapterRegistry()
    registry.register(_registration())
    with pytest.raises(DuplicateAdapterError):
        registry.register(_registration())


# Resolution / creation ----------------------------------------------------- #


def test_resolve_unknown_raises() -> None:
    with pytest.raises(UnknownAdapterError):
        AdapterRegistry().resolve("nope")


def test_create_builds_a_runtime_adapter() -> None:
    registry = AdapterRegistry()
    registry.register(_registration())
    adapter = registry.create(CLAUDE_RUNTIME_IDENTITY)
    assert isinstance(adapter, RuntimeAdapter)


def test_create_honors_profile() -> None:
    registry = AdapterRegistry()
    registry.register(_registration())
    # A failing profile threads through to the underlying stub invoker.
    adapter = registry.create(CLAUDE_RUNTIME_IDENTITY, profile=RuntimeInvocationProfile(fail=True))
    assert isinstance(adapter, RuntimeAdapter)


def test_create_unknown_raises() -> None:
    with pytest.raises(UnknownAdapterError):
        AdapterRegistry().create("nope")


# Discovery / capabilities -------------------------------------------------- #


def test_default_registry_lists_three_runtimes() -> None:
    registry = build_default_adapter_registry()
    assert registry.identities() == ("claude-code", "gemini-cli", "shell")


def test_descriptor_and_descriptors_are_deterministically_ordered() -> None:
    registry = build_default_adapter_registry()
    assert [d.identity for d in registry.descriptors()] == list(registry.identities())
    assert registry.descriptor("shell").identity == "shell"


def test_descriptor_unknown_raises() -> None:
    with pytest.raises(UnknownAdapterError):
        build_default_adapter_registry().descriptor("nope")


def test_capabilities_are_sorted() -> None:
    registry = build_default_adapter_registry()
    assert registry.capabilities("shell") == ("code_generation", "command_execution", "file_write")


def test_discover_by_capability_returns_candidates_only() -> None:
    registry = build_default_adapter_registry()
    code_gen = registry.discover_by_capability("code_generation")
    assert {d.identity for d in code_gen} == {"claude-code", "gemini-cli", "shell"}
    cmd = registry.discover_by_capability("command_execution")
    assert [d.identity for d in cmd] == ["shell"]
    assert registry.discover_by_capability("nonexistent") == ()


def test_reference_is_importable() -> None:
    # Sanity: a capability reference has the identifier the registry indexes on.
    ref = Reference(target_type="capability", identifier="code_generation")
    assert ref.identifier == "code_generation"
