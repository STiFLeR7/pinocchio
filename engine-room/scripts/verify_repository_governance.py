"""Verification script for AP-304 Repository Governance validation.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from nexus.core.types import ApprovalStatus
from nexus.database import Base
from nexus.execution.governance import GovernanceManager, RepositoryGovernanceError
from nexus.memory.models import (
    ApprovalRecord,
    AuditLogRecord,
    RepositoryRegistryRecord,
    TaskRecord,
)


class SafeSessionWrapper:
    def __init__(self, session: Any) -> None:
        self._session = session

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)

    async def commit(self) -> None:
        await self._session.flush()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def close(self) -> None:
        pass


async def init_db(engine_url: str) -> Any:
    engine = create_async_engine(engine_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    return engine


async def verify_audit_log(session: Any, task_id: uuid.UUID, event_type: str) -> None:
    stmt = select(AuditLogRecord).where(
        AuditLogRecord.entity_id == task_id, AuditLogRecord.event_type == event_type
    )
    res = await session.execute(stmt)
    audit = res.scalar_one_or_none()
    if audit:
        print(f"  [DB AuditLogRecord] FOUND '{event_type}' for task {task_id}")
        print(f"    Data: {audit.data}")
    else:
        print(f"  [DB AuditLogRecord] NOT FOUND for event '{event_type}' on task {task_id}")


async def main() -> None:
    db_url = "sqlite+aiosqlite:///data/governance_acceptance.db"
    if os.path.exists("data/governance_acceptance.db"):
        with contextlib.suppress(Exception):
            os.remove("data/governance_acceptance.db")

    engine = await init_db(db_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as root_session:
        session = SafeSessionWrapper(root_session)
        gov = GovernanceManager(session)

        # Seed initial registry
        repo = RepositoryRegistryRecord(
            id=uuid.uuid4(),
            name="workspace_root",
            absolute_path=os.path.abspath("."),
            allowed_branches=["*"],
            allowed_commands=["*"],
            is_active=True,
            allowed_runtimes=["gemini", "claude"],
            allowed_profiles=["coding", "analysis"],
            owner="111222333",
            status="active",
        )
        session.add(repo)
        await session.flush()

        print("\n=== RUNNING AP-304 FAILURE TESTING SCENARIOS ===")

        # -------------------------------------------------------------
        # Scenario 1: Unknown Repository
        # -------------------------------------------------------------
        print("\n--- Scenario 1: Unknown Repository ---")
        task1 = TaskRecord(
            id=uuid.uuid4(),
            title="Unknown Repo Task",
            description="cmd:echo 1",
            priority=2,
            runtime_type="cli",
            runtime_id="gemini",
            execution_profile="coding",
            runtime_policy="approved",
        )
        session.add(task1)
        await session.flush()

        approval1 = ApprovalRecord(
            id=uuid.uuid4(),
            task_id=task1.id,
            status=ApprovalStatus.APPROVED.value,
            requested_at=datetime.now(UTC),
            decided_by="111222333",
        )
        session.add(approval1)
        await session.flush()

        try:
            # Using random/unregistered path
            await gov.validate_execution(
                task_id=task1.id,
                working_dir="/unregistered/path/to/repo",
                command="echo 1",
                runtime="gemini",
            )
            print("  [FAIL] Expected validation failure, but it passed.")
        except RepositoryGovernanceError as e:
            print(f"  [SUCCESS] Validation failed as expected: {e}")
            await verify_audit_log(session, task1.id, "RepositoryValidated")

        # -------------------------------------------------------------
        # Scenario 2: Blocked Runtime
        # -------------------------------------------------------------
        print("\n--- Scenario 2: Blocked Runtime ---")
        task2 = TaskRecord(
            id=uuid.uuid4(),
            title="Blocked Runtime Task",
            description="cmd:echo 1",
            priority=2,
            runtime_type="cli",
            runtime_id="hermes",
            execution_profile="coding",
            runtime_policy="approved",
        )
        session.add(task2)
        await session.flush()

        approval2 = ApprovalRecord(
            id=uuid.uuid4(),
            task_id=task2.id,
            status=ApprovalStatus.APPROVED.value,
            requested_at=datetime.now(UTC),
            decided_by="111222333",
        )
        session.add(approval2)
        await session.flush()

        try:
            # Hermes is not allowed in repo.allowed_runtimes = ["gemini", "claude"]
            await gov.validate_execution(
                task_id=task2.id,
                working_dir=".",
                command="echo 1",
                runtime="hermes",
            )
            print("  [FAIL] Expected validation failure, but it passed.")
        except RepositoryGovernanceError as e:
            print(f"  [SUCCESS] Validation failed as expected: {e}")
            await verify_audit_log(session, task2.id, "RuntimeRejected")

        # -------------------------------------------------------------
        # Scenario 3: Blocked/Invalid Branch
        # -------------------------------------------------------------
        print("\n--- Scenario 3: Invalid/Blocked Branch ---")
        # Update repo allowed branches to something other than current branch
        # (or mock a blocked one)
        repo.blocked_branches = ["master", "main"]
        await session.flush()

        task3 = TaskRecord(
            id=uuid.uuid4(),
            title="Blocked Branch Task",
            description="cmd:echo 1",
            priority=2,
            runtime_type="cli",
            runtime_id="gemini",
            execution_profile="coding",
            runtime_policy="approved",
        )
        session.add(task3)
        await session.flush()

        approval3 = ApprovalRecord(
            id=uuid.uuid4(),
            task_id=task3.id,
            status=ApprovalStatus.APPROVED.value,
            requested_at=datetime.now(UTC),
            decided_by="111222333",
        )
        session.add(approval3)
        await session.flush()

        try:
            await gov.validate_execution(
                task_id=task3.id,
                working_dir=".",
                command="echo 1",
                runtime="gemini",
            )
            print("  [FAIL] Expected validation failure, but it passed.")
        except RepositoryGovernanceError as e:
            print(f"  [SUCCESS] Validation failed as expected: {e}")
            await verify_audit_log(session, task3.id, "BranchRejected")

        # Reset blocked branches for subsequent tests
        repo.blocked_branches = []
        await session.flush()

        # -------------------------------------------------------------
        # Scenario 4: Policy Violation
        # -------------------------------------------------------------
        print("\n--- Scenario 4: Policy Violation (policy != approved) ---")
        task4 = TaskRecord(
            id=uuid.uuid4(),
            title="Blocked Policy Task",
            description="cmd:echo 1",
            priority=2,
            runtime_type="cli",
            runtime_id="gemini",
            execution_profile="coding",
            runtime_policy="blocked",
        )
        session.add(task4)
        await session.flush()

        approval4 = ApprovalRecord(
            id=uuid.uuid4(),
            task_id=task4.id,
            status=ApprovalStatus.APPROVED.value,
            requested_at=datetime.now(UTC),
            decided_by="111222333",
        )
        session.add(approval4)
        await session.flush()

        try:
            await gov.validate_execution(
                task_id=task4.id,
                working_dir=".",
                command="echo 1",
                runtime="gemini",
            )
            print("  [FAIL] Expected validation failure, but it passed.")
        except RepositoryGovernanceError as e:
            print(f"  [SUCCESS] Validation failed as expected: {e}")
            await verify_audit_log(session, task4.id, "PolicyViolation")

        # -------------------------------------------------------------
        # Scenario 5: Expired/No Approval
        # -------------------------------------------------------------
        print("\n--- Scenario 5: Expired or Missing Approval ---")
        task5 = TaskRecord(
            id=uuid.uuid4(),
            title="No Approval Task",
            description="cmd:echo 1",
            priority=2,
            runtime_type="cli",
            runtime_id="gemini",
            execution_profile="coding",
            runtime_policy="approved",
        )
        session.add(task5)
        await session.flush()

        # No approval record seeded for task5
        try:
            await gov.validate_execution(
                task_id=task5.id,
                working_dir=".",
                command="echo 1",
                runtime="gemini",
            )
            print("  [FAIL] Expected validation failure, but it passed.")
        except RepositoryGovernanceError as e:
            print(f"  [SUCCESS] Validation failed as expected: {e}")
            await verify_audit_log(session, task5.id, "ExecutionBlocked")

        # -------------------------------------------------------------
        # Scenario 6: Repository Disabled
        # -------------------------------------------------------------
        print("\n--- Scenario 6: Repository Disabled ---")
        repo.status = "disabled"
        await session.flush()

        task6 = TaskRecord(
            id=uuid.uuid4(),
            title="Disabled Repo Task",
            description="cmd:echo 1",
            priority=2,
            runtime_type="cli",
            runtime_id="gemini",
            execution_profile="coding",
            runtime_policy="approved",
        )
        session.add(task6)
        await session.flush()

        approval6 = ApprovalRecord(
            id=uuid.uuid4(),
            task_id=task6.id,
            status=ApprovalStatus.APPROVED.value,
            requested_at=datetime.now(UTC),
            decided_by="111222333",
        )
        session.add(approval6)
        await session.flush()

        try:
            await gov.validate_execution(
                task_id=task6.id,
                working_dir=".",
                command="echo 1",
                runtime="gemini",
            )
            print("  [FAIL] Expected validation failure, but it passed.")
        except RepositoryGovernanceError as e:
            print(f"  [SUCCESS] Validation failed as expected: {e}")
            await verify_audit_log(session, task6.id, "RepositoryValidated")

        await session.commit()
        print("\nRepository Governance validation complete.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
