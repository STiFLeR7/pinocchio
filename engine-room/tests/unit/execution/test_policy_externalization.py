"""Unit and integration tests for AP-316 Policy Externalization implementation.

Verifies:
- System policy creation, schema validation, and database updates.
- Optimistic locking conflict detection and safety rollback controls.
- Policy revision logs and historical change reconstruction.
- Hierarchical policy merging (tightening concurrency limits, merging blacklists).
- Fail-closed behavior on missing or invalid policy registry states.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.core import health
from nexus.execution.governance import GovernanceManager, RepositoryGovernanceError
from nexus.memory.models import (
    ApprovalRecord,
    AuditLogRecord,
    ExecutionRecord,
    RepositoryRegistryRecord,
    SystemPolicyHistoryRecord,
    TaskRecord,
)
from nexus.memory.policy_service import PolicyService, PolicyValidationError


@pytest.mark.asyncio
async def test_policy_creation_and_enforcement(db_session: AsyncSession) -> None:
    """Verify that creating and retrieving system policies operates correctly."""
    policy_service = PolicyService(db_session)

    # 1. Create a policy
    await policy_service.create_policy(
        key="required_runtime_policy",
        value="approved_prod_only",
        updated_by="admin_operator",
    )

    # 2. Retrieve policy
    val = await policy_service.get_policy("required_runtime_policy")
    assert val == "approved_prod_only"

    # 3. Check historical records are created
    stmt = select(SystemPolicyHistoryRecord).where(SystemPolicyHistoryRecord.policy_key == "required_runtime_policy")
    res = await db_session.execute(stmt)
    history = res.scalars().all()
    assert len(history) == 1
    assert history[0].version == 1
    assert history[0].updated_by == "admin_operator"
    assert history[0].change_type == "create"


@pytest.mark.asyncio
async def test_policy_schema_validation_failures(db_session: AsyncSession) -> None:
    """Verify that type schema validation fails closed on invalid formats."""
    policy_service = PolicyService(db_session)

    # Create invalid allowed_runtimes format (should be list, not int)
    with pytest.raises(PolicyValidationError, match="allowed_runtimes must be a list of strings"):
        await policy_service.create_policy("allowed_runtimes", 12345, "admin")

    # Create invalid concurrency limit (must be positive int)
    with pytest.raises(PolicyValidationError, match="default_concurrency_limit must be a positive integer"):
        await policy_service.create_policy("default_concurrency_limit", -10, "admin")


@pytest.mark.asyncio
async def test_policy_optimistic_locking_conflict(db_session: AsyncSession) -> None:
    """Verify version conflict raises concurrency modification exception and fails safely."""
    policy_service = PolicyService(db_session)

    # Create key
    await policy_service.create_policy("required_runtime_policy", "approved", "admin")

    # Try updating with outdated version (version 1 is current, we send version 99)
    with pytest.raises(RepositoryGovernanceError, match="Optimistic lock conflict"):
        await policy_service.update_policy(
            key="required_runtime_policy",
            value="changed_value",
            current_version=99,
            updated_by="concurrent_admin",
        )

    # Verify value is unmodified
    val = await policy_service.get_policy("required_runtime_policy")
    assert val == "approved"


@pytest.mark.asyncio
async def test_policy_fallback_log_warning(db_session: AsyncSession) -> None:
    """Verify query fallback logs PolicyFallbackUsed warning when key is missing in DB."""
    policy_service = PolicyService(db_session)

    # allowed_runtimes is not in DB, should query policy_defaults ALLOWED_RUNTIMES
    val = await policy_service.get_policy("allowed_runtimes")
    # "nexus" is the renamed agent runtime; "hermes" retained as the deprecated codename alias.
    assert val == ["gemini", "claude", "nexus", "hermes"]

    # Verify PolicyFallbackUsed audit is generated
    stmt = select(AuditLogRecord).where(AuditLogRecord.event_type == "PolicyFallbackUsed")
    res = await db_session.execute(stmt)
    audit = res.scalar_one_or_none()
    assert audit is not None
    assert audit.data["policy_key"] == "allowed_runtimes"


@pytest.mark.asyncio
async def test_hierarchy_concurrency_limits_tightening(db_session: AsyncSession) -> None:
    """Verify repository policy limits can tighten concurrency limits but cannot loosen/weaken them."""
    health.set_healthy()
    policy_service = PolicyService(db_session)
    gov = GovernanceManager(db_session)
    task_id = uuid.uuid4()

    # 1. Setup policy default: default_concurrency_limit = 3
    await policy_service.create_policy("default_concurrency_limit", 3, "admin")
    await policy_service.create_policy("allowed_runtimes", ["gemini"], "admin")
    await policy_service.create_policy("required_runtime_policy", "approved", "admin")
    await policy_service.create_policy("global_command_blacklist", [], "admin")

    # 2. Seed Repository with override limit: 1
    repo_stmt = select(RepositoryRegistryRecord).where(RepositoryRegistryRecord.name == "workspace_root")
    res = await db_session.execute(repo_stmt)
    repo = res.scalar_one()
    repo.concurrency_limit_override = 1

    # Seed task and approval
    task = TaskRecord(
        id=task_id,
        title="Concurrency Test Task",
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

    # Seed 1 active execution
    exec_rec = ExecutionRecord(
        id=uuid.uuid4(),
        task_id=task_id,
        runner="gemini",
        repository=repo.absolute_path,
        started_at=datetime.now(UTC),
        completed_at=None,
    )
    db_session.add(exec_rec)
    await db_session.flush()

    # Act & Assert: since override limit is 1, and 1 execution is active, next run must be blocked
    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="main\n")):
        with pytest.raises(RepositoryGovernanceError, match=r"Execution limit exceeded.*limit: 1"):
            await gov.validate_execution(
                task_id=task_id,
                working_dir=".",
                command="echo 'test'",
                runtime="gemini",
            )


@pytest.mark.asyncio
async def test_hierarchy_concurrency_limits_weakening_ignored(db_session: AsyncSession) -> None:
    """Verify repository policy limits override cannot weaken global limits (e.g. overriding 3 to 10 is blocked)."""
    health.set_healthy()
    policy_service = PolicyService(db_session)
    gov = GovernanceManager(db_session)
    task_id = uuid.uuid4()

    # 1. Setup policy default: default_concurrency_limit = 3
    await policy_service.create_policy("default_concurrency_limit", 3, "admin")
    await policy_service.create_policy("allowed_runtimes", ["gemini"], "admin")
    await policy_service.create_policy("required_runtime_policy", "approved", "admin")
    await policy_service.create_policy("global_command_blacklist", [], "admin")

    # 2. Seed Repository with override limit: 10 (weaker than global 3)
    repo_stmt = select(RepositoryRegistryRecord).where(RepositoryRegistryRecord.name == "workspace_root")
    res = await db_session.execute(repo_stmt)
    repo = res.scalar_one()
    repo.concurrency_limit_override = 10

    task = TaskRecord(
        id=task_id,
        title="Concurrency Test Task",
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

    # Seed 3 active executions
    for _i in range(3):
        exec_rec = ExecutionRecord(
            id=uuid.uuid4(),
            task_id=task_id,
            runner="gemini",
            repository=repo.absolute_path,
            started_at=datetime.now(UTC),
            completed_at=None,
        )
        db_session.add(exec_rec)
    await db_session.flush()

    # Act & Assert: since global limit is 3, validation must reject even though repository requested 10
    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="main\n")):
        with pytest.raises(RepositoryGovernanceError, match=r"Execution limit exceeded.*limit: 3"):
            await gov.validate_execution(
                task_id=task_id,
                working_dir=".",
                command="echo 'test'",
                runtime="gemini",
            )


@pytest.mark.asyncio
async def test_hierarchy_command_blacklist_additions(db_session: AsyncSession) -> None:
    """Verify repository blacklist additions append constraints and filter command runs."""
    health.set_healthy()
    policy_service = PolicyService(db_session)
    gov = GovernanceManager(db_session)
    task_id = uuid.uuid4()

    # 1. Setup policy default blacklist: ["sudo"]
    await policy_service.create_policy("global_command_blacklist", ["sudo "], "admin")
    await policy_service.create_policy("allowed_runtimes", ["gemini"], "admin")
    await policy_service.create_policy("required_runtime_policy", "approved", "admin")
    await policy_service.create_policy("default_concurrency_limit", 3, "admin")

    # 2. Seed Repository with blacklist additions: ["wget "]
    repo_stmt = select(RepositoryRegistryRecord).where(RepositoryRegistryRecord.name == "workspace_root")
    res = await db_session.execute(repo_stmt)
    repo = res.scalar_one()
    repo.command_blacklist_additions = ["wget "]

    task = TaskRecord(
        id=task_id,
        title="Blacklist Task",
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

    # Act & Assert: Verify global blacklist blocks
    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="main\n")):
        with pytest.raises(RepositoryGovernanceError, match="Command contains forbidden string pattern"):
            await gov.validate_execution(
                task_id=task_id,
                working_dir=".",
                command="sudo apt-get install",
                runtime="gemini",
            )

    # Act & Assert: Verify repo additions block
    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="main\n")):
        with pytest.raises(RepositoryGovernanceError, match="Command contains forbidden string pattern"):
            await gov.validate_execution(
                task_id=task_id,
                working_dir=".",
                command="wget http://external.site/script",
                runtime="gemini",
            )
