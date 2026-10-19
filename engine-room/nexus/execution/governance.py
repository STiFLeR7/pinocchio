from __future__ import annotations

import asyncio
import fnmatch
import os
import random
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, update

from nexus.core.exceptions import ExecutionEngineError
from nexus.memory.models import (
    ApprovalRecord,
    AuditLogRecord,
    ExecutionRecord,
    GovernanceSemaphoreRecord,
    RepositoryRegistryRecord,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class RepositoryGovernanceError(ExecutionEngineError):
    """Exception raised when a subprocess run violates repository governance rules."""

    pass


class GovernanceManager:
    """Enforces safety constraints and whitelists on subprocess environments."""

    def __init__(self, db_session: AsyncSession) -> None:
        """Initialize the GovernanceManager with a database session."""
        self.session = db_session

    async def _write_audit(
        self,
        task_id: uuid.UUID,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Write an immutable audit log record to the database."""
        import uuid as uuid_pkg

        audit = AuditLogRecord(
            id=uuid_pkg.uuid4(),
            event_type=event_type,
            entity_type="task",
            entity_id=task_id,
            data=data,
            component="governance_engine",
            actor="system",
        )
        self.session.add(audit)
        await self.session.flush()

    async def validate_execution(
        self,
        task_id: uuid.UUID,
        working_dir: str,
        command: str,
        runtime: str,
    ) -> RepositoryRegistryRecord:
        """Validate execution parameters against safety and registry constraints.

        Raises RepositoryGovernanceError on violation.
        """
        # 0. Startup Health Check
        from nexus.core import health
        if not health.is_healthy():
            await self._write_audit(
                task_id,
                "ExecutionBlocked",
                {
                    "reason": f"Control plane is unhealthy: {health.get_health_reason()}",
                    "status": "system_unhealthy",
                },
            )
            raise RepositoryGovernanceError(
                f"Execution blocked because control plane is unhealthy: {health.get_health_reason()}"
            )

        # 1. Approved Runtime Validation (Component 1: System Policies)
        from nexus.memory.policy_service import PolicyService
        policy_service = PolicyService(self.session)

        allowed_runtimes_list = await policy_service.get_policy("allowed_runtimes")
        allowed_runtimes = {r.lower() for r in allowed_runtimes_list}
        if runtime.lower() not in allowed_runtimes:
            await self._write_audit(
                task_id,
                "RuntimeRejected",
                {
                    "runtime": runtime,
                    "allowed_runtimes": list(allowed_runtimes),
                    "reason": "Runtime not approved in platform",
                },
            )
            raise RepositoryGovernanceError(f"Runtime '{runtime}' is not approved.")

        # Load task
        from nexus.memory.models import TaskRecord

        task_stmt = select(TaskRecord).where(TaskRecord.id == task_id)
        task_res = await self.session.execute(task_stmt)
        task = task_res.scalar_one_or_none()
        if not task:
            raise RepositoryGovernanceError(f"Task with ID {task_id} not found.")

        # 2. Runtime Policy Approved Check
        required_policy = await policy_service.get_policy("required_runtime_policy")
        if task.runtime_policy != required_policy:
            await self._write_audit(
                task_id,
                "PolicyViolation",
                {
                    "runtime_policy": task.runtime_policy,
                    "expected": required_policy,
                    "reason": "Policy mismatch",
                },
            )
            raise RepositoryGovernanceError(
                f"Runtime policy is '{task.runtime_policy}', but '{required_policy}' is required."
            )

        # 3. Approval Record Validation
        app_stmt = (
            select(ApprovalRecord)
            .where(ApprovalRecord.task_id == task_id)
            .order_by(ApprovalRecord.created_at.desc())
            .limit(1)
        )
        app_res = await self.session.execute(app_stmt)
        approval = app_res.scalar_one_or_none()
        if not approval or approval.status != "approved":
            await self._write_audit(
                task_id,
                "ExecutionBlocked",
                {
                    "reason": "Execution lacks active approval authorization",
                    "status": "no_approval",
                },
            )
            raise RepositoryGovernanceError("Execution lacks active approval authorization.")

        # 4. Approved Repository & Working Directory Validation
        # Find matching repository record by absolute path overlap
        repo_stmt = select(RepositoryRegistryRecord)
        repo_res = await self.session.execute(repo_stmt)
        repositories = repo_res.scalars().all()

        matching_repo = None
        clean_working_dir = os.path.realpath(working_dir)
        for repo in repositories:
            clean_repo_path = os.path.realpath(repo.absolute_path)
            # Check if working_dir is inside repo directory
            if clean_working_dir == clean_repo_path or clean_working_dir.startswith(
                clean_repo_path + os.sep
            ):
                matching_repo = repo
                break

        if not matching_repo:
            await self._write_audit(
                task_id,
                "RepositoryValidated",
                {"status": "failed", "working_dir": working_dir, "reason": "Unknown repository"},
            )
            raise RepositoryGovernanceError(
                f"Working directory '{working_dir}' is not registered "
                f"under any approved repository."
            )

        # 5. Repository Active Check
        if matching_repo.status != "active" or not matching_repo.is_active:
            await self._write_audit(
                task_id,
                "RepositoryValidated",
                {
                    "status": "failed",
                    "repository_id": str(matching_repo.id),
                    "reason": "Repository disabled",
                },
            )
            raise RepositoryGovernanceError(f"Repository '{matching_repo.name}' is disabled.")

        # Log successful repository validation
        await self._write_audit(
            task_id,
            "RepositoryValidated",
            {"status": "passed", "repository_id": str(matching_repo.id)},
        )

        # 6. Runtime Allowed on Repo Check
        if matching_repo.allowed_runtimes:
            allowed_runtimes_lower = [r.lower() for r in matching_repo.allowed_runtimes]
            if runtime.lower() not in allowed_runtimes_lower:
                await self._write_audit(
                    task_id,
                    "RuntimeRejected",
                    {
                        "runtime": runtime,
                        "allowed_runtimes": matching_repo.allowed_runtimes,
                        "reason": "Runtime not allowed for repo",
                    },
                )
                raise RepositoryGovernanceError(
                    f"Runtime '{runtime}' is not allowed for repo '{matching_repo.name}'."
                )

        # Log successful runtime authorization
        await self._write_audit(
            task_id,
            "RuntimeAuthorized",
            {"runtime": runtime, "repository_id": str(matching_repo.id)},
        )

        # 7. Profile Allowed on Repo Check
        if (
            matching_repo.allowed_profiles
            and task.execution_profile not in matching_repo.allowed_profiles
        ):
                await self._write_audit(
                    task_id,
                    "PolicyViolation",
                    {
                        "profile": task.execution_profile,
                        "allowed_profiles": matching_repo.allowed_profiles,
                        "reason": "Profile not allowed for repo",
                    },
                )
                raise RepositoryGovernanceError(
                    f"Execution profile '{task.execution_profile}' is not allowed "
                    f"for repository '{matching_repo.name}'."
                )

        # 8. Owner Approved Check
        if matching_repo.owner:
            authorized_owners = [o.strip() for o in matching_repo.owner.split(",")]
            decided_by = str(approval.decided_by) if approval.decided_by is not None else ""
            if decided_by not in authorized_owners:
                await self._write_audit(
                    task_id,
                    "PolicyViolation",
                    {
                        "decided_by": decided_by,
                        "repo_owners": authorized_owners,
                        "reason": "Approval owner mismatch",
                    },
                )
                raise RepositoryGovernanceError(
                    f"Owner approval validation failed. Decided by '{decided_by}', "
                    f"but repo owner is '{matching_repo.owner}'."
                )

        # 9. Concurrency Semaphore Locking & Capacity Validation
        sem_name = f"repo_{matching_repo.id}"

        # Get concurrency retry configurations dynamically from policy service
        try:
            retry_limit = await policy_service.get_policy("concurrency_retry_count")
            await policy_service.get_policy("concurrency_retry_timeout")
        except Exception:
            retry_limit = 5

        # Helper to ensure the semaphore row exists
        async def ensure_semaphore() -> None:
            try:
                async with self.session.begin_nested():
                    stmt = select(GovernanceSemaphoreRecord).where(GovernanceSemaphoreRecord.name == sem_name)
                    res = await self.session.execute(stmt)
                    row = res.scalar_one_or_none()
                    if not row:
                        import uuid as uuid_pkg
                        sem = GovernanceSemaphoreRecord(
                            id=uuid_pkg.uuid4(),
                            name=sem_name,
                            is_locked=False,
                        )
                        self.session.add(sem)
                        await self.session.flush()
            except Exception:
                # Catch unique constraints (parallel insert race), pass
                pass

        await ensure_semaphore()

        # Retry loop for semaphore lock acquisition
        import time

        from sqlalchemy.exc import OperationalError
        lock_start = time.perf_counter()
        lock_acquired = False
        base_delay = 0.1

        for attempt in range(retry_limit):
            try:
                async with self.session.begin_nested():
                    # Acquire lock via update
                    stmt = (
                        update(GovernanceSemaphoreRecord)
                        .where(GovernanceSemaphoreRecord.name == sem_name)
                        .values(is_locked=True)
                    )
                    await self.session.execute(stmt)
                    await self.session.flush()
                    lock_acquired = True
                    break
            except OperationalError as e:
                if "database is locked" in str(e).lower():
                    delay = base_delay * (2 ** attempt) * random.uniform(0.5, 1.5)
                    await self._write_audit(
                        task_id,
                        "LockAcquisitionRetry",
                        {
                            "attempt": attempt + 1,
                            "delay_ms": int(delay * 1000),
                            "error": str(e),
                        },
                    )
                    await asyncio.sleep(delay)
                else:
                    raise

        lock_wait = (time.perf_counter() - lock_start) * 1000.0
        from nexus.core.metrics import record_metric
        record_metric("lock_wait_ms", lock_wait)
        import structlog
        structlog.get_logger("nexus.execution.governance").info(
            "concurrency_lock_finished",
            lock_wait_ms=round(lock_wait, 2),
            lock_acquired=lock_acquired,
        )

        if not lock_acquired:
            await self._write_audit(
                task_id,
                "LockAcquisitionFailed",
                {
                    "reason": "Retry exhaustion",
                    "max_retries": retry_limit,
                },
            )
            raise RepositoryGovernanceError(
                f"Concurrency validation lock acquisition timeout for repository '{matching_repo.name}'."
            )

        # Count active executions for this repository path
        active_stmt = select(ExecutionRecord).where(
            ExecutionRecord.repository == matching_repo.absolute_path,
            ExecutionRecord.completed_at.is_(None),
        )
        active_res = await self.session.execute(active_stmt)
        active_execs = active_res.scalars().all()

        # Determine effective concurrency limit (System Policy + Repository Overrides tightening only)
        global_limit = await policy_service.get_policy("default_concurrency_limit")
        repo_override = matching_repo.concurrency_limit_override
        effective_limit = global_limit
        if repo_override is not None:
            effective_limit = min(global_limit, repo_override)

        if len(active_execs) >= effective_limit:
            # Release semaphore
            stmt = (
                update(GovernanceSemaphoreRecord)
                .where(GovernanceSemaphoreRecord.name == sem_name)
                .values(is_locked=False)
            )
            await self.session.execute(stmt)
            await self.session.flush()

            await self._write_audit(
                task_id,
                "ExecutionBlocked",
                {
                    "active_execution_count": len(active_execs),
                    "limit": effective_limit,
                    "reason": "Repository execution limit exceeded",
                },
            )
            raise RepositoryGovernanceError(
                f"Execution limit exceeded for repository '{matching_repo.name}'. "
                f"Current active: {len(active_execs)} (limit: {effective_limit})."
            )

        # 10. Branch Constraints (whitelisted branch checks on active repo)
        active_branch = None
        try:
            import subprocess

            # Get active branch name
            res = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=clean_working_dir,
                capture_output=True,
                text=True,
                check=False,
                timeout=5.0,
            )
            if res.returncode == 0:
                active_branch = res.stdout.strip()
            else:
                error_msg = f"Git subprocess returned non-zero code {res.returncode}: {res.stderr.strip()}"
                # Release semaphore
                stmt = (
                    update(GovernanceSemaphoreRecord)
                    .where(GovernanceSemaphoreRecord.name == sem_name)
                    .values(is_locked=False)
                )
                await self.session.execute(stmt)
                await self.session.flush()

                await self._write_audit(
                    task_id,
                    "BranchVerificationFailed",
                    {
                        "working_dir": working_dir,
                        "error": error_msg,
                        "reason": "Subprocess execution failure",
                    },
                )
                raise RepositoryGovernanceError(f"Branch verification failed: {error_msg}")
        except RepositoryGovernanceError:
            raise
        except subprocess.TimeoutExpired as e:
            error_msg = f"Git branch check timed out: {e!s}"
            # Release semaphore
            stmt = (
                update(GovernanceSemaphoreRecord)
                .where(GovernanceSemaphoreRecord.name == sem_name)
                .values(is_locked=False)
            )
            await self.session.execute(stmt)
            await self.session.flush()

            await self._write_audit(
                task_id,
                "BranchVerificationFailed",
                {
                    "working_dir": working_dir,
                    "error": error_msg,
                    "reason": "TimeoutExpired",
                },
            )
            raise RepositoryGovernanceError(error_msg) from e
        except Exception as e:
            error_msg = f"Git branch check raised exception: {e!s}"
            # Release semaphore
            stmt = (
                update(GovernanceSemaphoreRecord)
                .where(GovernanceSemaphoreRecord.name == sem_name)
                .values(is_locked=False)
            )
            await self.session.execute(stmt)
            await self.session.flush()

            await self._write_audit(
                task_id,
                "BranchVerificationFailed",
                {
                    "working_dir": working_dir,
                    "error": error_msg,
                    "reason": "ExecutionError",
                },
            )
            raise RepositoryGovernanceError(error_msg) from e

        if active_branch:
            # Handle detached HEAD state
            if active_branch == "HEAD":
                hash_res = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=clean_working_dir,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5.0,
                )
                commit_hash = hash_res.stdout.strip() if hash_res.returncode == 0 else ""

                is_allowed = False
                if matching_repo.allowed_branches:
                    branches_list = (
                        list(matching_repo.allowed_branches.keys())
                        if isinstance(matching_repo.allowed_branches, dict)
                        else matching_repo.allowed_branches
                    )
                    if "HEAD" in branches_list or (commit_hash and commit_hash in branches_list) or "*" in branches_list:
                        is_allowed = True

                is_blocked = False
                if matching_repo.blocked_branches and ("HEAD" in matching_repo.blocked_branches or (commit_hash and commit_hash in matching_repo.blocked_branches)):
                    is_blocked = True

                if is_blocked or not is_allowed:
                    # Release semaphore
                    stmt = (
                        update(GovernanceSemaphoreRecord)
                        .where(GovernanceSemaphoreRecord.name == sem_name)
                        .values(is_locked=False)
                    )
                    await self.session.execute(stmt)
                    await self.session.flush()

                    await self._write_audit(
                        task_id,
                        "BranchRejected",
                        {
                            "branch": "HEAD",
                            "commit_hash": commit_hash,
                            "reason": "Detached HEAD branch / commit hash is not allowed or is blocked",
                        },
                    )
                    raise RepositoryGovernanceError(
                        "Execution blocked: Detached HEAD state is not whitelisted or is blocked."
                    )
            else:
                # Blocked branches check
                if matching_repo.blocked_branches:
                    blocked = any(
                        fnmatch.fnmatch(active_branch, pattern)
                        for pattern in matching_repo.blocked_branches
                    )
                    if blocked:
                        # Release semaphore
                        stmt = (
                            update(GovernanceSemaphoreRecord)
                            .where(GovernanceSemaphoreRecord.name == sem_name)
                            .values(is_locked=False)
                        )
                        await self.session.execute(stmt)
                        await self.session.flush()

                        await self._write_audit(
                            task_id,
                            "BranchRejected",
                            {
                                "branch": active_branch,
                                "blocked_branches": matching_repo.blocked_branches,
                                "reason": "Branch is blocked",
                            },
                        )
                        raise RepositoryGovernanceError(
                            f"Branch '{active_branch}' is blocked for "
                            f"repository '{matching_repo.name}'."
                        )

                # Protected branches check
                if matching_repo.protected_branches:
                    protected = any(
                        fnmatch.fnmatch(active_branch, pattern)
                        for pattern in matching_repo.protected_branches
                    )
                    if protected:
                        # Release semaphore
                        stmt = (
                            update(GovernanceSemaphoreRecord)
                            .where(GovernanceSemaphoreRecord.name == sem_name)
                            .values(is_locked=False)
                        )
                        await self.session.execute(stmt)
                        await self.session.flush()

                        await self._write_audit(
                            task_id,
                            "BranchRejected",
                            {
                                "branch": active_branch,
                                "protected_branches": matching_repo.protected_branches,
                                "reason": "Branch is protected",
                            },
                        )
                        raise RepositoryGovernanceError(
                            f"Branch '{active_branch}' is protected for "
                            f"repository '{matching_repo.name}'."
                        )

                # Allowed branches check
                if matching_repo.allowed_branches:
                    branches = matching_repo.allowed_branches
                    branches_list = list(branches.keys()) if isinstance(branches, dict) else branches

                    if "*" not in branches_list:
                        matched = any(
                            fnmatch.fnmatch(active_branch, pattern) for pattern in branches_list
                        )
                        if not matched:
                            # Release semaphore
                            stmt = (
                                update(GovernanceSemaphoreRecord)
                                .where(GovernanceSemaphoreRecord.name == sem_name)
                                .values(is_locked=False)
                            )
                            await self.session.execute(stmt)
                            await self.session.flush()

                            await self._write_audit(
                                task_id,
                                "BranchRejected",
                                {
                                    "branch": active_branch,
                                    "allowed_branches": branches_list,
                                    "reason": "Branch not whitelisted",
                                },
                            )
                            raise RepositoryGovernanceError(
                                f"Branch '{active_branch}' is not whitelisted for "
                                f"repository '{matching_repo.name}'."
                            )

        # 11. Command Filter Safety Constraints
        global_blacklist = await policy_service.get_policy("global_command_blacklist")
        repo_blacklist_additions = matching_repo.command_blacklist_additions or []
        effective_blacklist = list(set(global_blacklist + repo_blacklist_additions))

        for pattern in effective_blacklist:
            if pattern in command:
                # Release semaphore
                stmt = (
                    update(GovernanceSemaphoreRecord)
                    .where(GovernanceSemaphoreRecord.name == sem_name)
                    .values(is_locked=False)
                )
                await self.session.execute(stmt)
                await self.session.flush()

                await self._write_audit(
                    task_id,
                    "PolicyViolation",
                    {
                        "command": command,
                        "violation": pattern,
                        "reason": "Forbidden command pattern",
                    },
                )
                raise RepositoryGovernanceError(
                    f"Command contains forbidden string pattern: '{pattern}'"
                )

        # Release semaphore upon successful validation passage
        stmt = (
            update(GovernanceSemaphoreRecord)
            .where(GovernanceSemaphoreRecord.name == sem_name)
            .values(is_locked=False)
        )
        await self.session.execute(stmt)
        await self.session.flush()

        return matching_repo
