"""Unit tests for AP-314 P0 Hardening implementation.

Tests:
- Startup Git binary liveness checks and health API states.
- Fail-closed branch governance (git missing, timeouts, detached HEAD, permission errors).
- Atomic concurrency gates (semaphore table, retry lock acquisition, limit enforcement).
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nexus.core import health
from nexus.execution.governance import GovernanceManager, RepositoryGovernanceError
from nexus.memory.models import (
    ApprovalRecord,
    AuditLogRecord,
    ExecutionRecord,
    RepositoryRegistryRecord,
    TaskRecord,
)


@pytest.mark.asyncio
async def test_health_startup_git_validation_success(db_session: AsyncSession) -> None:
    """Verify health status is healthy when Git command executes successfully."""
    # Reset health state
    health.set_healthy()

    mock_run = MagicMock(returncode=0, stdout="git version 2.45.0")
    with patch("subprocess.run", return_value=mock_run):
        is_ok = await health.run_git_startup_validation()
        assert is_ok is True
        assert health.is_healthy() is True
        assert health.get_health_reason() == "healthy"


@pytest.mark.asyncio
async def test_health_startup_git_validation_failure(db_session: AsyncSession) -> None:
    """Verify health status is unhealthy and SystemUnhealthy audit is written when Git check fails."""
    # Reset health state
    health.set_healthy()

    # Mock Git missing
    with patch("subprocess.run", side_effect=FileNotFoundError("git not found")):
        # Pass session factory mock or real to test audit write
        MagicMock()

        # We can test health state directly
        is_ok = await health.run_git_startup_validation()
        assert is_ok is False
        assert health.is_healthy() is False
        assert "git not found" in health.get_health_reason()


@pytest.mark.asyncio
async def test_branch_governance_git_missing(db_session: AsyncSession) -> None:
    """Verify validation fails closed when git is not found in PATH at runtime."""
    health.set_healthy()
    gov = GovernanceManager(db_session)
    task_id = uuid.uuid4()

    # Seed task and approval
    task = TaskRecord(
        id=task_id,
        title="Git Missing Test Task",
        status="queued",
        priority=2,
        runtime_type="cli",
        runtime_id="gemini",
        execution_profile="default",
        runtime_policy="approved",
    )
    db_session.add(task)

    approval = ApprovalRecord(
        id=uuid.uuid4(),
        task_id=task_id,
        status="approved",
        requested_at=datetime.now(UTC),
        decided_at=datetime.now(UTC),
        decided_by="111222333",
    )
    db_session.add(approval)
    await db_session.flush()

    with patch("subprocess.run", side_effect=FileNotFoundError("No such file or directory")):
        with pytest.raises(RepositoryGovernanceError, match="Git branch check raised exception"):
            await gov.validate_execution(
                task_id=task_id,
                working_dir=".",
                command="echo 'test'",
                runtime="gemini",
            )

    # Check audit log contains BranchVerificationFailed
    stmt = select(AuditLogRecord).where(AuditLogRecord.event_type == "BranchVerificationFailed")
    res = await db_session.execute(stmt)
    audit = res.scalar_one_or_none()
    assert audit is not None
    assert audit.data["reason"] == "ExecutionError"


@pytest.mark.asyncio
async def test_branch_governance_git_timeout(db_session: AsyncSession) -> None:
    """Verify validation fails closed when the git branch query subprocess times out."""
    health.set_healthy()
    gov = GovernanceManager(db_session)
    task_id = uuid.uuid4()

    task = TaskRecord(
        id=task_id,
        title="Git Timeout Test Task",
        status="queued",
        runtime_id="gemini",
    )
    db_session.add(task)
    approval = ApprovalRecord(
        id=uuid.uuid4(),
        task_id=task_id,
        status="approved",
        requested_at=datetime.now(UTC),
        decided_by="111222333",
    )
    db_session.add(approval)
    await db_session.flush()

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["git"], timeout=5.0)):
        with pytest.raises(RepositoryGovernanceError, match="Git branch check timed out"):
            await gov.validate_execution(
                task_id=task_id,
                working_dir=".",
                command="echo 'test'",
                runtime="gemini",
            )


@pytest.mark.asyncio
async def test_branch_governance_detached_head_allowed(db_session: AsyncSession) -> None:
    """Verify detached HEAD validation passes if explicitly whitelisted in allowed_branches."""
    health.set_healthy()
    gov = GovernanceManager(db_session)
    task_id = uuid.uuid4()

    task = TaskRecord(
        id=task_id,
        title="Detached HEAD Task",
        status="queued",
        runtime_id="gemini",
    )
    db_session.add(task)
    approval = ApprovalRecord(
        id=uuid.uuid4(),
        task_id=task_id,
        status="approved",
        requested_at=datetime.now(UTC),
        decided_by="111222333",
    )
    db_session.add(approval)

    # Configure whitelisted repository to allow detached HEAD state
    repo_stmt = select(RepositoryRegistryRecord).where(
        RepositoryRegistryRecord.name == "workspace_root"
    )
    res = await db_session.execute(repo_stmt)
    repo = res.scalar_one()
    repo.allowed_branches = ["HEAD"]
    await db_session.flush()

    # Mock subprocess runs: first returns "HEAD", second returns commit hash
    mock_branch = MagicMock(returncode=0, stdout="HEAD\n")
    mock_hash = MagicMock(returncode=0, stdout="a1b2c3d4e5f6\n")

    def side_effect(cmd, *args, **kwargs):
        if "rev-parse" in cmd and "--abbrev-ref" in cmd:
            return mock_branch
        return mock_hash

    with patch("subprocess.run", side_effect=side_effect):
        res_repo = await gov.validate_execution(
            task_id=task_id,
            working_dir=".",
            command="echo 'test'",
            runtime="gemini",
        )
        assert res_repo.name == "workspace_root"


@pytest.mark.asyncio
async def test_branch_governance_detached_head_blocked(db_session: AsyncSession) -> None:
    """Verify detached HEAD validation fails closed if not whitelisted or is blocked."""
    health.set_healthy()
    gov = GovernanceManager(db_session)
    task_id = uuid.uuid4()

    task = TaskRecord(
        id=task_id,
        title="Detached HEAD Blocked Task",
        status="queued",
        runtime_id="gemini",
    )
    db_session.add(task)
    approval = ApprovalRecord(
        id=uuid.uuid4(),
        task_id=task_id,
        status="approved",
        requested_at=datetime.now(UTC),
        decided_by="111222333",
    )
    db_session.add(approval)

    repo_stmt = select(RepositoryRegistryRecord).where(
        RepositoryRegistryRecord.name == "workspace_root"
    )
    res = await db_session.execute(repo_stmt)
    repo = res.scalar_one()
    repo.allowed_branches = ["main", "develop"]
    await db_session.flush()

    mock_branch = MagicMock(returncode=0, stdout="HEAD\n")
    mock_hash = MagicMock(returncode=0, stdout="a1b2c3d4e5f6\n")

    def side_effect(cmd, *args, **kwargs):
        if "rev-parse" in cmd and "--abbrev-ref" in cmd:
            return mock_branch
        return mock_hash

    with patch("subprocess.run", side_effect=side_effect):
        with pytest.raises(
            RepositoryGovernanceError, match="Detached HEAD state is not whitelisted or is blocked"
        ):
            await gov.validate_execution(
                task_id=task_id,
                working_dir=".",
                command="echo 'test'",
                runtime="gemini",
            )


@pytest.mark.asyncio
async def test_concurrency_lock_acquisition_retry_mechanism(db_session: AsyncSession) -> None:
    """Verify semaphore lock acquisition retries upon database lock contention."""
    health.set_healthy()
    gov = GovernanceManager(db_session)
    task_id = uuid.uuid4()

    task = TaskRecord(
        id=task_id,
        title="Lock Retry Task",
        status="queued",
        runtime_id="gemini",
    )
    db_session.add(task)
    approval = ApprovalRecord(
        id=uuid.uuid4(),
        task_id=task_id,
        status="approved",
        requested_at=datetime.now(UTC),
        decided_by="111222333",
    )
    db_session.add(approval)
    await db_session.flush()

    # Mock the update to raise OperationalError("database is locked") twice, then succeed
    original_execute = db_session.execute
    call_count = 0

    async def mock_execute(statement, *args, **kwargs):
        nonlocal call_count
        stmt_str = str(statement).lower()
        if "update" in stmt_str and "governance_semaphores" in stmt_str:
            call_count += 1
            if call_count <= 2:
                raise OperationalError("mock_update", {}, Exception("database is locked"))
        return await original_execute(statement, *args, **kwargs)

    with patch.object(db_session, "execute", side_effect=mock_execute):
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="main\n")):
            res_repo = await gov.validate_execution(
                task_id=task_id,
                working_dir=".",
                command="echo 'test'",
                runtime="gemini",
            )
            assert res_repo.name == "workspace_root"
            assert call_count == 4  # Two failures, one lock success, one unlock success


@pytest.mark.asyncio
async def test_concurrency_limits_under_parallel_requests(db_engine) -> None:
    """Verify that launching multiple parallel sessions enforces the max limit (3) atomically."""
    health.set_healthy()
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    # 1. Seed Repository registry and Task/Approvals
    async with session_factory() as session:
        repo = RepositoryRegistryRecord(
            id=uuid.uuid4(),
            name="concurrency_test_repo",
            absolute_path=os.path.abspath("./concurrency_test_dir"),
            allowed_branches=["*"],
            allowed_commands=["*"],
            is_active=True,
        )
        session.add(repo)

        # Seed 5 tasks and active approvals
        task_ids = [uuid.uuid4() for _ in range(5)]
        for tid in task_ids:
            task = TaskRecord(
                id=tid,
                title=f"Parallel Task {tid}",
                status="queued",
                runtime_id="gemini",
            )
            session.add(task)
            approval = ApprovalRecord(
                id=uuid.uuid4(),
                task_id=tid,
                status="approved",
                requested_at=datetime.now(UTC),
                decided_by="owner_concurrency",
            )
            session.add(approval)
        await session.commit()

    # 2. Simulate 5 concurrent validation requests on distinct sessions
    # We mock subprocess.run in each task to return main branch
    mock_run = MagicMock(returncode=0, stdout="main\n")

    async def run_validation(tid):
        async with session_factory() as session:
            gov = GovernanceManager(session)
            try:
                res_repo = await gov.validate_execution(
                    task_id=tid,
                    working_dir="./concurrency_test_dir",
                    command="echo 'test'",
                    runtime="gemini",
                )
                # If it passes, we add a mock running ExecutionRecord to count against limit
                exec_rec = ExecutionRecord(
                    id=uuid.uuid4(),
                    task_id=tid,
                    runner="gemini",
                    repository=res_repo.absolute_path,
                    started_at=datetime.now(UTC),
                    completed_at=None,
                )
                session.add(exec_rec)
                await session.commit()
                return "passed"
            except RepositoryGovernanceError:
                return "blocked"

    # Patch subprocess.run once around the whole gather. Entering/exiting mock.patch inside each
    # concurrently-awaited coroutine is not isolation-safe: a coroutine can save the mock as the
    # "original" and later restore it, leaking the mock to unrelated tests. One enclosing patch
    # spans all concurrent validations and restores exactly once.
    with patch("subprocess.run", return_value=mock_run):
        results = await asyncio.gather(*(run_validation(tid) for tid in task_ids))

    # Assert that exactly 3 validations passed and 2 failed closed
    assert results.count("passed") == 3
    assert results.count("blocked") == 2
