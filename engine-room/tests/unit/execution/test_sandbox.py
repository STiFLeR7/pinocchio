"""Unit tests for the AP-503 Runtime Sandboxing layer."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.config import NexusSettings, SandboxConfig
from nexus.execution.sandbox import (
    LocalSandboxProvider,
    MockSandboxProvider,
    SandboxArtifactCollector,
    SandboxLifecycleService,
    SandboxManager,
    SandboxPolicy,
)
from nexus.memory.models import AuditLogRecord


@pytest.mark.asyncio
async def test_sandbox_policy_defaults() -> None:
    """Verify default policy values map correctly."""
    policy = SandboxPolicy()
    assert policy.cpu_limit == 1.0
    assert policy.memory_limit == "512m"
    assert policy.timeout == 300
    assert policy.network_policy == "none"
    assert policy.filesystem_policy == "restricted"


@pytest.mark.asyncio
async def test_resolve_provider_fallback(db_session: AsyncSession) -> None:
    """Ensure LocalSandboxProvider is returned if sandboxing is disabled or unconfigured."""
    manager = SandboxManager(db_session, settings=None)
    assert isinstance(manager.provider, LocalSandboxProvider)


@pytest.mark.asyncio
async def test_resolve_provider_mock(db_session: AsyncSession) -> None:
    """Ensure MockSandboxProvider resolves correctly from settings."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=True, provider="mock")
    manager = SandboxManager(db_session, settings=settings)
    assert isinstance(manager.provider, MockSandboxProvider)


@pytest.mark.asyncio
async def test_mock_sandbox_success_execution(db_session: AsyncSession) -> None:
    """Verify that MockSandboxProvider executes commands successfully and writes audits."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=True, provider="mock")
    manager = SandboxManager(db_session, settings=settings)

    correlation_id = uuid.uuid4()
    process = await manager.execute(
        command="echo 'Success Output'",
        cwd=".",
        timeout=10,
        correlation_id=correlation_id,
    )

    stdout, _stderr = await process.communicate()
    assert b"Mock sandbox run success" in stdout
    assert process.returncode == 0

    # Verify audit events written to database
    stmt = select(AuditLogRecord).where(AuditLogRecord.correlation_id == correlation_id)
    res = await db_session.execute(stmt)
    audits = res.scalars().all()

    # We expect: sandbox.created, sandbox.started, sandbox.terminated
    event_types = [a.event_type for a in audits]
    assert "sandbox.created" in event_types
    assert "sandbox.started" in event_types
    assert "sandbox.terminated" in event_types


@pytest.mark.asyncio
async def test_mock_sandbox_failure_execution(db_session: AsyncSession) -> None:
    """Verify that MockSandboxProvider logs failure events when processes fail/crash."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=True, provider="mock")
    manager = SandboxManager(db_session, settings=settings)

    correlation_id = uuid.uuid4()
    process = await manager.execute(
        command="crash the sandbox",
        cwd=".",
        timeout=10,
        correlation_id=correlation_id,
    )

    _stdout, stderr = await process.communicate()
    assert b"Segmentation fault" in stderr
    assert process.returncode == 139

    # Verify audit events
    stmt = select(AuditLogRecord).where(AuditLogRecord.correlation_id == correlation_id)
    res = await db_session.execute(stmt)
    audits = res.scalars().all()

    event_types = [a.event_type for a in audits]
    assert "sandbox.failure" in event_types


@pytest.mark.asyncio
async def test_mock_sandbox_timeout_execution(db_session: AsyncSession) -> None:
    """Verify that MockSandboxProvider handles and records timeout events."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=True, provider="mock")
    manager = SandboxManager(db_session, settings=settings)

    correlation_id = uuid.uuid4()
    process = await manager.execute(
        command="timeout after sleep",
        cwd=".",
        timeout=1,
        correlation_id=correlation_id,
    )

    _stdout, stderr = await process.communicate()
    assert b"Timeout" in stderr
    assert process.returncode == -1

    # Verify audit events
    stmt = select(AuditLogRecord).where(AuditLogRecord.correlation_id == correlation_id)
    res = await db_session.execute(stmt)
    audits = res.scalars().all()

    event_types = [a.event_type for a in audits]
    assert "sandbox.timeout" in event_types


@pytest.mark.asyncio
async def test_docker_sandbox_command_construction(db_session: AsyncSession) -> None:
    """Ensure DockerSandboxProvider correctly translates policy options to docker run arguments."""
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(
        enabled=True,
        provider="docker",
        cpu_limit=2.5,
        memory_limit="1g",
        network_policy="none",
        filesystem_policy="readonly",
        image="custom-runner:test",
    )

    manager = SandboxManager(db_session, settings=settings)

    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(return_value=(b"out", b"err"))
    mock_process.returncode = 0
    mock_process.pid = 12345

    # Mock asyncio subprocess exec to verify arguments
    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        process = await manager.execute(
            command="python run.py",
            cwd="D:/test/repo",
            timeout=120,
            correlation_id=uuid.uuid4(),
        )
        await process.communicate()

        assert mock_exec.called
        args = mock_exec.call_args[0]
        # First arg should be "docker"
        assert args[0] == "docker"
        # Verify subsequent options are mapped correctly
        assert "run" in args
        assert "--cpus" in args
        assert "2.5" in args
        assert "--memory" in args
        assert "1g" in args
        assert "--network" in args
        assert "none" in args
        assert "custom-runner:test" in args
        # Check volume mount formatting
        assert any("D:/test/repo:/workspace:ro" in a for a in args)


@pytest.mark.asyncio
async def test_sandbox_lifecycle_orphan_cleanup() -> None:
    """Verify that lifecycle service executes docker ps and stops matching orphan containers."""
    mock_ps = AsyncMock()
    mock_ps.communicate = AsyncMock(return_value=(b"nexus_sandbox_abc\nnexus_sandbox_123\nother_container\n", b""))
    mock_ps.returncode = 0

    mock_rm = AsyncMock()
    mock_rm.wait = AsyncMock()

    # Intercept command execution to avoid host reliance
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        # First call is docker ps, then two docker rm calls
        mock_exec.side_effect = [mock_ps, mock_rm, mock_rm]

        count = await SandboxLifecycleService.cleanup_orphaned_sandboxes()
        assert count == 2
        assert mock_exec.call_count == 3


@pytest.mark.asyncio
async def test_sandbox_artifact_collector() -> None:
    """Verify that collector invokes docker cp correctly."""
    mock_cp = AsyncMock()
    mock_cp.wait = AsyncMock()
    mock_cp.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_cp) as mock_exec:
        res = await SandboxArtifactCollector.collect_file(
            sandbox_id="test-id",
            container_path="/workspace/outputs/metrics.csv",
            host_path="D:/local/metrics.csv",
        )
        assert res is True
        assert mock_exec.called
        args = mock_exec.call_args[0]
        assert args[0] == "docker"
        assert "cp" in args
        assert "nexus_sandbox_test-id:/workspace/outputs/metrics.csv" in args
        assert "D:/local/metrics.csv" in args
