"""S-2 — Default-secure, fail-closed sandbox provider resolution (v1.1.0 Track S).

These tests pin the resolution contract:
  * Unknown provider names must FAIL CLOSED (raise), never fall back to host.
  * A real, isolation-disabled production config must FAIL CLOSED (no silent host execution).
  * Explicit, recognized providers (docker/mock/local) continue to resolve.
  * The non-production construction path (settings is not NexusSettings) is intentionally
    preserved as Local to keep runtime-adapter/e2e construction contracts intact.

Evidence basis: A-006 sandbox-safety-review (R-01 default host exec, R-02 fail-open resolution);
S-1-provider-resolution-design.md.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.config import NexusSettings, SandboxConfig
from nexus.core.exceptions import SandboxResolutionError
from nexus.execution.sandbox import (
    DockerSandboxProvider,
    LocalSandboxProvider,
    MockSandboxProvider,
    SandboxManager,
)

# --------------------------------------------------------------------------- #
# Fail-closed: unknown provider (R-02)                                         #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_unknown_provider_fails_closed(db_session: AsyncSession) -> None:
    """An unrecognized provider name must raise — never silently return a host provider."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=True, provider="bogus-provider")
    with pytest.raises(SandboxResolutionError):
        SandboxManager(db_session, settings=settings)


@pytest.mark.asyncio
async def test_unknown_provider_cannot_execute(db_session: AsyncSession) -> None:
    """Explicit proof: an unknown provider cannot reach execution — construction itself fails closed."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=True, provider="dcoker")  # typo
    with pytest.raises(SandboxResolutionError):
        # Resolution happens in __init__; execute() is never reachable.
        manager = SandboxManager(db_session, settings=settings)
        await manager.execute(command="echo pwn", cwd=".", timeout=5)


# --------------------------------------------------------------------------- #
# Default-secure: isolation disabled must fail closed (R-01)                   #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_disabled_sandbox_fails_closed(db_session: AsyncSession) -> None:
    """A real config with sandbox disabled must not silently execute on the host."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=False, provider="local")
    with pytest.raises(SandboxResolutionError):
        SandboxManager(db_session, settings=settings)


@pytest.mark.asyncio
async def test_default_production_settings_fail_closed(db_session: AsyncSession) -> None:
    """The shipped default (SandboxConfig.enabled is False) must fail closed under real settings."""
    settings = NexusSettings()  # sandbox defaults to enabled=False
    assert settings.sandbox.enabled is False  # guard: defaults unchanged (no schema change)
    with pytest.raises(SandboxResolutionError):
        SandboxManager(db_session, settings=settings)


# --------------------------------------------------------------------------- #
# Recognized providers continue to resolve                                     #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_docker_provider_resolves(db_session: AsyncSession) -> None:
    """Approved Docker path: enabled + docker resolves to the Docker provider."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=True, provider="docker")
    manager = SandboxManager(db_session, settings=settings)
    assert isinstance(manager.provider, DockerSandboxProvider)


@pytest.mark.asyncio
async def test_mock_provider_resolves(db_session: AsyncSession) -> None:
    """Test provider: enabled + mock resolves to the Mock provider."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=True, provider="mock")
    manager = SandboxManager(db_session, settings=settings)
    assert isinstance(manager.provider, MockSandboxProvider)


@pytest.mark.asyncio
async def test_explicit_local_provider_resolves(db_session: AsyncSession) -> None:
    """Host execution remains available, but only as a deliberate, recognized choice."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=True, provider="local")
    manager = SandboxManager(db_session, settings=settings)
    assert isinstance(manager.provider, LocalSandboxProvider)


@pytest.mark.asyncio
async def test_provider_name_normalized(db_session: AsyncSession) -> None:
    """Recognized provider names are matched case-insensitively (no fail-open on case)."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=True, provider="DOCKER")
    manager = SandboxManager(db_session, settings=settings)
    assert isinstance(manager.provider, DockerSandboxProvider)


# --------------------------------------------------------------------------- #
# Preserved non-production construction path                                   #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_non_nexussettings_preserves_local(db_session: AsyncSession) -> None:
    """settings=None (non-production construction, e.g. adapter unit tests) stays Local.

    This path never occurs in production (the orchestrator always supplies NexusSettings);
    it is intentionally retained to preserve runtime-adapter/e2e construction contracts.
    """
    manager = SandboxManager(db_session, settings=None)
    assert isinstance(manager.provider, LocalSandboxProvider)
