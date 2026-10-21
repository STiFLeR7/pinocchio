"""S-3 — Sandbox enforcement & startup validation (v1.1.0 Track S).

Pins three behaviors on top of the S-2 fail-closed resolution:
  * Startup validation refuses unsafe/incoherent sandbox configuration (fail fast, no delayed
    runtime discovery).
  * Provider availability is verified before any runtime execution (Docker probe at startup).
  * Policy enforcement is honest: the enforcing provider (Docker) must be available or we refuse;
    a non-enforcing provider (local/host) is declared, never pretended.

Evidence basis: A-006 sandbox-safety-review (R-03 decorative policy, R-06 no Docker validation,
R-07 no startup validation); S-1-security-policy-design.md, S-1-provider-resolution-design.md.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.config import NexusSettings, SandboxConfig
from nexus.core.exceptions import (
    ConfigurationError,
    SandboxResolutionError,
    SandboxUnavailableError,
)
from nexus.execution.sandbox import (
    DockerSandboxProvider,
    LocalSandboxProvider,
    MockSandboxProvider,
    SandboxManager,
    validate_sandbox_startup,
)
from nexus.memory.models import AuditLogRecord

# --------------------------------------------------------------------------- #
# Startup validation (R-07): fail fast, no delayed discovery                   #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_startup_disabled_sandbox_does_not_abort() -> None:
    """Disabled sandbox is a safe (fail-closed-at-runtime) state; startup warns, does not abort."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=False)
    await validate_sandbox_startup(settings)  # must not raise


@pytest.mark.asyncio
async def test_startup_unknown_provider_aborts() -> None:
    """An unrecognized provider must abort startup (coherence)."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=True, provider="bogus")
    with pytest.raises(ConfigurationError):
        await validate_sandbox_startup(settings)


@pytest.mark.asyncio
async def test_startup_docker_unavailable_aborts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Docker configured but unavailable must abort startup (eliminate delayed discovery / R-06)."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=True, provider="docker")

    async def _unavailable(self: object) -> None:
        raise SandboxUnavailableError("docker daemon not reachable")

    monkeypatch.setattr(DockerSandboxProvider, "ensure_available", _unavailable)
    with pytest.raises(ConfigurationError):
        await validate_sandbox_startup(settings)


@pytest.mark.asyncio
async def test_startup_docker_available_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Docker available must pass startup validation without raising."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=True, provider="docker")
    monkeypatch.setattr(DockerSandboxProvider, "ensure_available", AsyncMock())
    await validate_sandbox_startup(settings)  # must not raise


@pytest.mark.asyncio
async def test_startup_local_host_unsafe_passes() -> None:
    """Explicit host (local) provider is allowed at startup (deliberate, declared non-isolation)."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=True, provider="local")
    await validate_sandbox_startup(settings)  # must not raise (warns)


@pytest.mark.asyncio
async def test_startup_mock_passes() -> None:
    """Mock provider passes startup validation (test provider)."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=True, provider="mock")
    await validate_sandbox_startup(settings)  # must not raise


# --------------------------------------------------------------------------- #
# Provider availability (R-06)                                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_docker_ensure_available_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """DockerSandboxProvider.ensure_available raises SandboxUnavailableError if docker is missing."""

    async def _boom(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("docker")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _boom)
    with pytest.raises(SandboxUnavailableError):
        await DockerSandboxProvider().ensure_available()


@pytest.mark.asyncio
async def test_docker_ensure_available_raises_on_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    """Docker present but daemon unreachable (non-zero exit) must fail closed."""

    class _Proc:
        async def wait(self) -> int:
            return 1

    async def _exec(*args: object, **kwargs: object) -> _Proc:
        return _Proc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", _exec)
    with pytest.raises(SandboxUnavailableError):
        await DockerSandboxProvider().ensure_available()


@pytest.mark.asyncio
async def test_local_provider_always_available() -> None:
    """Local/host provider is always available (no-op probe)."""
    await LocalSandboxProvider().ensure_available()  # must not raise


# --------------------------------------------------------------------------- #
# Policy enforcement honesty (R-03)                                            #
# --------------------------------------------------------------------------- #


def test_docker_enforces_policy_flag() -> None:
    assert DockerSandboxProvider.enforces_policy is True


def test_local_does_not_enforce_policy_flag() -> None:
    assert LocalSandboxProvider.enforces_policy is False


def test_mock_does_not_enforce_policy_flag() -> None:
    assert MockSandboxProvider.enforces_policy is False


@pytest.mark.asyncio
async def test_execute_audit_declares_policy_enforcement(db_session: AsyncSession) -> None:
    """The sandbox.created audit must honestly declare whether policy is enforced (not pretend)."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=True, provider="mock")  # non-enforcing
    manager = SandboxManager(db_session, settings=settings)

    correlation_id = uuid.uuid4()
    process = await manager.execute(command="echo hi", cwd=".", timeout=5, correlation_id=correlation_id)
    await process.communicate()

    stmt = select(AuditLogRecord).where(AuditLogRecord.correlation_id == correlation_id)
    res = await db_session.execute(stmt)
    created = next(a for a in res.scalars().all() if a.event_type == "sandbox.created")
    assert created.data is not None
    assert created.data.get("policy_enforced") is False  # mock provider does not enforce


# --------------------------------------------------------------------------- #
# S-2 guarantees preserved                                                     #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_s2_failclosed_preserved(db_session: AsyncSession) -> None:
    """S-3 must not weaken S-2: disabled and unknown providers still fail closed at resolution."""
    disabled = NexusSettings()
    disabled.sandbox = SandboxConfig(enabled=False, provider="local")
    with pytest.raises(SandboxResolutionError):
        SandboxManager(db_session, settings=disabled)

    unknown = NexusSettings()
    unknown.sandbox = SandboxConfig(enabled=True, provider="bogus")
    with pytest.raises(SandboxResolutionError):
        SandboxManager(db_session, settings=unknown)
