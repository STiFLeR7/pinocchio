"""Unit tests for nexus_runtime.composition — build_runtime dependency-injection wiring.

Covers:
- build_runtime default wiring: returns a RuntimeContext with all non-None fields
- Default harness_registry is an InMemoryHarnessRegistry
- Default registry is a RuntimeRegistry wrapping the default harness_registry
- Default repositories are RuntimeRepositories (sessions + allocations stores)
- Default manager is a RuntimeManager wired over the infrastructure
- Custom harness_registry override: the injected registry is on the context
- Custom repositories override: the injected repositories are on the context
- Custom timestamps override: the injected timestamps reach the manager
- infrastructure field is the passed InfrastructureContext
"""

from __future__ import annotations

from nexus_infra import build_infrastructure
from nexus_runtime import (
    FixedTimestampSource,
    RuntimeManager,
)
from nexus_runtime.composition import RuntimeContext, build_runtime
from nexus_runtime.persistence import build_runtime_repositories
from nexus_runtime.runtime_registry import InMemoryHarnessRegistry, RuntimeRegistry
from tests.unit.nexus_runtime.helpers import (
    descriptor,
    intake,
    preparation_request,
    runtime_env,
)

# ===========================================================================
# Return type and field presence
# ===========================================================================


def test_build_runtime_returns_runtime_context() -> None:
    """build_runtime returns a RuntimeContext instance."""
    infra = build_infrastructure()

    ctx = build_runtime(infra)

    assert isinstance(ctx, RuntimeContext)


def test_build_runtime_context_infrastructure_is_passed_infra() -> None:
    """The infrastructure field is the exact InfrastructureContext passed in."""
    infra = build_infrastructure()

    ctx = build_runtime(infra)

    assert ctx.infrastructure is infra


def test_build_runtime_context_has_harness_registry() -> None:
    """The returned context has a non-None harness_registry."""
    infra = build_infrastructure()

    ctx = build_runtime(infra)

    assert ctx.harness_registry is not None


def test_build_runtime_context_harness_registry_is_in_memory() -> None:
    """Default harness_registry is an InMemoryHarnessRegistry."""
    infra = build_infrastructure()

    ctx = build_runtime(infra)

    assert isinstance(ctx.harness_registry, InMemoryHarnessRegistry)


def test_build_runtime_context_has_registry() -> None:
    """The returned context has a non-None registry."""
    infra = build_infrastructure()

    ctx = build_runtime(infra)

    assert ctx.registry is not None


def test_build_runtime_context_registry_is_runtime_registry() -> None:
    """Default registry is a RuntimeRegistry."""
    infra = build_infrastructure()

    ctx = build_runtime(infra)

    assert isinstance(ctx.registry, RuntimeRegistry)


def test_build_runtime_context_has_repositories() -> None:
    """The returned context has a non-None repositories field."""
    infra = build_infrastructure()

    ctx = build_runtime(infra)

    assert ctx.repositories is not None


def test_build_runtime_context_repositories_has_sessions() -> None:
    """The default repositories have a sessions store."""
    infra = build_infrastructure()

    ctx = build_runtime(infra)

    assert ctx.repositories.sessions is not None


def test_build_runtime_context_repositories_has_allocations() -> None:
    """The default repositories have an allocations store."""
    infra = build_infrastructure()

    ctx = build_runtime(infra)

    assert ctx.repositories.allocations is not None


def test_build_runtime_context_has_manager() -> None:
    """The returned context has a non-None manager."""
    infra = build_infrastructure()

    ctx = build_runtime(infra)

    assert ctx.manager is not None


def test_build_runtime_context_manager_is_runtime_manager() -> None:
    """The default manager is a RuntimeManager."""
    infra = build_infrastructure()

    ctx = build_runtime(infra)

    assert isinstance(ctx.manager, RuntimeManager)


# ===========================================================================
# Default registry wires to the same backing store
# ===========================================================================


def test_build_runtime_registry_wraps_default_harness_registry() -> None:
    """A runtime registered in harness_registry is visible through registry.list_runtimes()."""
    infra = build_infrastructure()
    ctx = build_runtime(infra)

    d = descriptor("rt-wired")
    ctx.harness_registry.register(d)

    assert any(d.identity == "rt-wired" for d in ctx.registry.list_runtimes())


def test_build_runtime_default_harness_registry_shared_with_registry() -> None:
    """The harness_registry on the context is exactly the one the RuntimeRegistry wraps."""
    infra = build_infrastructure()
    ctx = build_runtime(infra)

    # Register through the registry's register() method, then verify via harness_registry
    d = descriptor("rt-via-registry")
    ctx.registry.register(d)

    assert ctx.harness_registry.get("rt-via-registry") is not None


# ===========================================================================
# Custom harness_registry override
# ===========================================================================


def test_build_runtime_custom_harness_registry_is_used() -> None:
    """When harness_registry is provided, the context's harness_registry is that instance."""
    infra = build_infrastructure()
    custom_registry = InMemoryHarnessRegistry()

    ctx = build_runtime(infra, harness_registry=custom_registry)

    assert ctx.harness_registry is custom_registry


def test_build_runtime_custom_harness_registry_registry_wraps_it() -> None:
    """The RuntimeRegistry wraps the custom harness_registry (registration is visible)."""
    infra = build_infrastructure()
    custom_registry = InMemoryHarnessRegistry()
    ctx = build_runtime(infra, harness_registry=custom_registry)

    d = descriptor("rt-custom")
    custom_registry.register(d)

    assert ctx.registry.get("rt-custom") is not None


# ===========================================================================
# Custom repositories override
# ===========================================================================


def test_build_runtime_custom_repositories_is_used() -> None:
    """When repositories is provided, the context's repositories is that instance."""
    from nexus_infra import InMemoryObservability

    infra = build_infrastructure()
    obs = InMemoryObservability()
    custom_repos = build_runtime_repositories(obs)

    ctx = build_runtime(infra, repositories=custom_repos)

    assert ctx.repositories is custom_repos


def test_build_runtime_custom_repositories_manager_uses_them() -> None:
    """The manager persists to the injected custom repositories (not default ones)."""
    from nexus_infra import InMemoryObservability

    infra = build_infrastructure()
    obs = InMemoryObservability()
    custom_repos = build_runtime_repositories(obs)
    ctx = build_runtime(infra, repositories=custom_repos, timestamps=FixedTimestampSource())

    d = descriptor("rt-repos")
    ctx.manager.register_runtime(d)
    i = intake(candidates=("rt-repos",))
    request = preparation_request(i)
    ctx.manager.prepare(request)

    assert custom_repos.sessions.count == 1
    assert custom_repos.allocations.count == 1


# ===========================================================================
# Custom timestamps override
# ===========================================================================


def test_build_runtime_custom_timestamps_used_by_manager() -> None:
    """When timestamps is provided, emitted events carry the custom timestamp value."""
    infra = build_infrastructure()
    fixed_ts = FixedTimestampSource("2099-01-01T00:00:00+00:00")
    ctx = build_runtime(infra, timestamps=fixed_ts)

    d = descriptor("rt-ts")
    ctx.manager.register_runtime(d)

    events = list(infra.event_store.read_all())
    assert len(events) == 1
    assert events[0].timestamp == "2099-01-01T00:00:00+00:00"


def test_build_runtime_no_timestamps_uses_system_source() -> None:
    """Without a custom timestamp, manager still works (SystemTimestampSource is used)."""
    infra = build_infrastructure()
    ctx = build_runtime(infra)

    d = descriptor("rt-system-ts")
    ctx.manager.register_runtime(d)

    events = list(infra.event_store.read_all())
    assert len(events) == 1
    # Should be a non-empty ISO-8601 timestamp
    assert events[0].timestamp
    assert "T" in events[0].timestamp


# ===========================================================================
# Full wiring via runtime_env helper (smoke test of composition end-to-end)
# ===========================================================================


def test_runtime_env_helper_build_runtime_is_functional() -> None:
    """The runtime_env() helper produces a working env backed by build_runtime."""
    env = runtime_env()

    request = preparation_request(intake())
    result = env.manager.prepare(request)

    assert result.sessions[0].lifecycle_state.value == "ready"


def test_build_runtime_all_combinations_do_not_raise() -> None:
    """build_runtime with all overrides provided constructs without raising."""
    from nexus_infra import InMemoryObservability

    infra = build_infrastructure()
    custom_registry = InMemoryHarnessRegistry()
    obs = InMemoryObservability()
    custom_repos = build_runtime_repositories(obs)
    fixed_ts = FixedTimestampSource()

    ctx = build_runtime(
        infra,
        harness_registry=custom_registry,
        repositories=custom_repos,
        timestamps=fixed_ts,
    )

    assert ctx.infrastructure is infra
    assert ctx.harness_registry is custom_registry
    assert ctx.repositories is custom_repos
