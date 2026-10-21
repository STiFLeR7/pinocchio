"""Unit tests for nexus_harness.composition.

Covers build_harness() and HarnessContext:
- Returns a HarnessContext with .infrastructure, .sources, .repositories, .service.
- HarnessContext is a frozen dataclass (mutations are rejected).
- .sources is a HarnessSources with the 3 in-memory registries and 4 repos.
- .sources.artifacts is infrastructure.artifacts (same object, not a copy).
- .repositories holds InMemoryRepository instances for execution_packages and
  execution_manifests.
- .service is a HarnessService.
- build_harness(infra, sources=custom) uses the injected sources instead of defaults.
- No module-level singletons: two build_harness(build_infrastructure()) calls yield
  independent contexts (different objects; mutations in one do not affect the other).
"""

from __future__ import annotations

import dataclasses

import pytest

from nexus_harness import (
    FixedTimestampSource,
    HarnessContext,
    HarnessService,
    HarnessSources,
    InMemoryCapabilityRegistry,
    InMemoryPolicyRegistry,
    InMemorySkillRegistry,
    build_harness,
)
from nexus_infra import InMemoryRepository, build_infrastructure

# ---------------------------------------------------------------------------
# HarnessContext structure
# ---------------------------------------------------------------------------


def test_build_harness_returns_harness_context() -> None:
    """build_harness returns a HarnessContext instance."""
    infra = build_infrastructure()
    ctx = build_harness(infra)
    assert isinstance(ctx, HarnessContext)


def test_harness_context_infrastructure_attribute() -> None:
    """HarnessContext.infrastructure is the InfrastructureContext passed in."""
    infra = build_infrastructure()
    ctx = build_harness(infra)
    assert ctx.infrastructure is infra


def test_harness_context_sources_is_harness_sources() -> None:
    """HarnessContext.sources is a HarnessSources instance."""
    infra = build_infrastructure()
    ctx = build_harness(infra)
    assert isinstance(ctx.sources, HarnessSources)


def test_harness_context_service_is_harness_service() -> None:
    """HarnessContext.service is a HarnessService instance."""
    infra = build_infrastructure()
    ctx = build_harness(infra)
    assert isinstance(ctx.service, HarnessService)


# ---------------------------------------------------------------------------
# HarnessContext is frozen
# ---------------------------------------------------------------------------


def test_harness_context_rejects_mutation_of_infrastructure() -> None:
    """HarnessContext is a frozen dataclass — assigning infrastructure raises FrozenInstanceError."""
    infra = build_infrastructure()
    ctx = build_harness(infra)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.infrastructure = build_infrastructure()  # type: ignore[misc]


def test_harness_context_rejects_mutation_of_sources() -> None:
    """HarnessContext is a frozen dataclass — assigning sources raises FrozenInstanceError."""
    infra = build_infrastructure()
    ctx = build_harness(infra)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.sources = ctx.sources  # type: ignore[misc]


def test_harness_context_rejects_mutation_of_service() -> None:
    """HarnessContext is a frozen dataclass — assigning service raises FrozenInstanceError."""
    infra = build_infrastructure()
    ctx = build_harness(infra)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.service = ctx.service  # type: ignore[misc]


# ---------------------------------------------------------------------------
# HarnessSources — in-memory registries
# ---------------------------------------------------------------------------


def test_sources_skills_is_in_memory_skill_registry() -> None:
    """sources.skills is an InMemorySkillRegistry (default)."""
    infra = build_infrastructure()
    ctx = build_harness(infra)
    assert isinstance(ctx.sources.skills, InMemorySkillRegistry)


def test_sources_capabilities_is_in_memory_capability_registry() -> None:
    """sources.capabilities is an InMemoryCapabilityRegistry (default)."""
    infra = build_infrastructure()
    ctx = build_harness(infra)
    assert isinstance(ctx.sources.capabilities, InMemoryCapabilityRegistry)


def test_sources_policies_is_in_memory_policy_registry() -> None:
    """sources.policies is an InMemoryPolicyRegistry (default)."""
    infra = build_infrastructure()
    ctx = build_harness(infra)
    assert isinstance(ctx.sources.policies, InMemoryPolicyRegistry)


# ---------------------------------------------------------------------------
# HarnessSources — repositories
# ---------------------------------------------------------------------------


def test_sources_work_packages_is_repository() -> None:
    """sources.work_packages is an InMemoryRepository."""
    infra = build_infrastructure()
    ctx = build_harness(infra)
    assert isinstance(ctx.sources.work_packages, InMemoryRepository)


def test_sources_context_packages_is_repository() -> None:
    """sources.context_packages is an InMemoryRepository."""
    infra = build_infrastructure()
    ctx = build_harness(infra)
    assert isinstance(ctx.sources.context_packages, InMemoryRepository)


def test_sources_strategies_is_repository() -> None:
    """sources.strategies is an InMemoryRepository."""
    infra = build_infrastructure()
    ctx = build_harness(infra)
    assert isinstance(ctx.sources.strategies, InMemoryRepository)


def test_sources_artifacts_is_infrastructure_artifacts() -> None:
    """sources.artifacts is the same object as infrastructure.artifacts (reused)."""
    infra = build_infrastructure()
    ctx = build_harness(infra)
    assert ctx.sources.artifacts is infra.artifacts


# ---------------------------------------------------------------------------
# HarnessRepositories
# ---------------------------------------------------------------------------


def test_repositories_execution_packages_is_repository() -> None:
    """repositories.execution_packages is an InMemoryRepository."""
    infra = build_infrastructure()
    ctx = build_harness(infra)
    assert isinstance(ctx.repositories.execution_packages, InMemoryRepository)


def test_repositories_execution_manifests_is_repository() -> None:
    """repositories.execution_manifests is an InMemoryRepository."""
    infra = build_infrastructure()
    ctx = build_harness(infra)
    assert isinstance(ctx.repositories.execution_manifests, InMemoryRepository)


# ---------------------------------------------------------------------------
# Custom sources injection
# ---------------------------------------------------------------------------


def test_injected_sources_are_used_instead_of_defaults() -> None:
    """build_harness(infra, sources=custom) uses the injected HarnessSources."""
    from nexus_harness.sources import HarnessSources

    infra = build_infrastructure()
    custom_skills = InMemorySkillRegistry()
    custom_capabilities = InMemoryCapabilityRegistry()
    custom_policies = InMemoryPolicyRegistry()
    custom_sources = HarnessSources(
        skills=custom_skills,
        capabilities=custom_capabilities,
        policies=custom_policies,
        work_packages=InMemoryRepository(
            "work_package", lambda w: w.identifier, infra.observability
        ),
        context_packages=InMemoryRepository(
            "context_package", lambda c: c.identity, infra.observability
        ),
        strategies=InMemoryRepository(
            "execution_strategy", lambda s: s.identity, infra.observability
        ),
        artifacts=infra.artifacts,
    )
    ctx = build_harness(infra, sources=custom_sources)
    assert ctx.sources is custom_sources


def test_injected_sources_skills_is_the_custom_registry() -> None:
    """When custom sources are injected, ctx.sources.skills is the custom registry."""
    from nexus_harness.sources import HarnessSources

    infra = build_infrastructure()
    custom_skills = InMemorySkillRegistry()
    custom_sources = HarnessSources(
        skills=custom_skills,
        capabilities=InMemoryCapabilityRegistry(),
        policies=InMemoryPolicyRegistry(),
        work_packages=InMemoryRepository(
            "work_package", lambda w: w.identifier, infra.observability
        ),
        context_packages=InMemoryRepository(
            "context_package", lambda c: c.identity, infra.observability
        ),
        strategies=InMemoryRepository(
            "execution_strategy", lambda s: s.identity, infra.observability
        ),
        artifacts=infra.artifacts,
    )
    ctx = build_harness(infra, sources=custom_sources)
    assert ctx.sources.skills is custom_skills


# ---------------------------------------------------------------------------
# No module-level singletons — independence
# ---------------------------------------------------------------------------


def test_two_build_calls_return_different_contexts() -> None:
    """Two build_harness(build_infrastructure()) calls yield distinct HarnessContext objects."""
    ctx1 = build_harness(build_infrastructure())
    ctx2 = build_harness(build_infrastructure())
    assert ctx1 is not ctx2


def test_two_build_calls_have_independent_infrastructures() -> None:
    """Each call to build_harness gets its own InfrastructureContext."""
    ctx1 = build_harness(build_infrastructure())
    ctx2 = build_harness(build_infrastructure())
    assert ctx1.infrastructure is not ctx2.infrastructure


def test_two_build_calls_have_independent_sources() -> None:
    """Each call to build_harness creates independent HarnessSources (no shared registries)."""
    ctx1 = build_harness(build_infrastructure())
    ctx2 = build_harness(build_infrastructure())
    assert ctx1.sources is not ctx2.sources


def test_two_build_calls_have_independent_skill_registries() -> None:
    """Registering a skill in one context does not affect the other context's registry."""
    from tests.unit.nexus_harness.helpers import skill

    ctx1 = build_harness(build_infrastructure())
    ctx2 = build_harness(build_infrastructure())
    ctx1.sources.skills.register(skill("skill-only-in-ctx1"))
    assert ctx2.sources.skills.get("skill-only-in-ctx1") is None


def test_two_build_calls_have_independent_repositories() -> None:
    """Each call to build_harness creates independent harness repositories."""
    ctx1 = build_harness(build_infrastructure())
    ctx2 = build_harness(build_infrastructure())
    assert ctx1.repositories is not ctx2.repositories


def test_two_build_calls_have_independent_execution_package_repos() -> None:
    """execution_packages repos are independent across two build_harness calls."""
    ctx1 = build_harness(build_infrastructure())
    ctx2 = build_harness(build_infrastructure())
    assert ctx1.repositories.execution_packages is not ctx2.repositories.execution_packages


# ---------------------------------------------------------------------------
# Optional timestamps parameter
# ---------------------------------------------------------------------------


def test_build_harness_accepts_timestamp_source() -> None:
    """build_harness accepts an optional timestamps argument without error."""
    infra = build_infrastructure()
    ctx = build_harness(infra, timestamps=FixedTimestampSource())
    assert isinstance(ctx, HarnessContext)
