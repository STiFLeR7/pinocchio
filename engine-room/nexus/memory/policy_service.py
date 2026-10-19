"""Service layer managing global and repository-specific governance policies."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update

from nexus.core import policy_defaults
from nexus.core.exceptions import ExecutionEngineError
from nexus.execution.governance import RepositoryGovernanceError
from nexus.memory.models import (
    AuditLogRecord,
    SystemPolicyHistoryRecord,
    SystemPolicyRecord,
)


class PolicyValidationError(ExecutionEngineError):
    """Exception raised when a dynamic policy fails schema validation."""
    pass


class PolicyService:
    """Handles registry lookups, optimistic locking updates, and historical audit revision logs."""

    def __init__(self, db_session: Any) -> None:
        """Initialize the PolicyService with a database session."""
        self.session = db_session

    async def _write_audit(
        self,
        event_type: str,
        data: dict[str, Any],
        actor: str = "system",
    ) -> None:
        """Write an immutable audit log record to the database."""
        import uuid as uuid_pkg

        audit = AuditLogRecord(
            id=uuid_pkg.uuid4(),
            event_type=event_type,
            entity_type="system_policy",
            entity_id=None,
            data=data,
            component="policy_engine",
            actor=actor,
            created_at=datetime.now(UTC),
        )
        self.session.add(audit)
        await self.session.flush()

    async def get_policy(self, key: str) -> Any:
        """Retrieve policy value from database registry with fallback to legacy code defaults.

        Fails closed if the policy value is invalid or corrupted.
        """
        stmt = select(SystemPolicyRecord).where(SystemPolicyRecord.policy_key == key)
        try:
            res = await self.session.execute(stmt)
            policy = res.scalar_one_or_none()
        except Exception as e:
            # Registry unavailable (database query fails) -> Fail-closed!
            await self._write_audit(
                "PolicyRegistryUnavailable",
                {"policy_key": key, "error": str(e)},
            )
            raise RepositoryGovernanceError(f"Policy registry unavailable: {e!s}") from e

        if policy is not None:
            val = policy.policy_value
            # Validate schema format correctness (Component 1 validation thresholds)
            self._validate_policy_schema(key, val)
            return val

        # Key not in registry -> Fallback to legacy defaults (Phase 1 Dual-Read/Fallback behavior)
        default_val = getattr(policy_defaults, key.upper(), None)
        if default_val is not None:
            await self._write_audit(
                "PolicyFallbackUsed",
                {
                    "policy_key": key,
                    "reason": "Missing registry key, using code fallback defaults",
                },
            )
            self._validate_policy_schema(key, default_val)
            return default_val

        # Policy not in registry and no legacy default exists -> Fail-Closed!
        await self._write_audit(
            "PolicyMissingError",
            {"policy_key": key, "reason": "No policy value or legacy default found"},
        )
        raise RepositoryGovernanceError(f"Governance policy configuration '{key}' is missing.")

    async def update_policy(
        self,
        key: str,
        value: Any,
        current_version: int,
        updated_by: str,
    ) -> None:
        """Update system policy with optimistic locking protection.

        Raises RepositoryGovernanceError on version conflicts or validation failures.
        """
        # Validate schema first
        self._validate_policy_schema(key, value)

        # Check existing policy
        stmt = select(SystemPolicyRecord).where(SystemPolicyRecord.policy_key == key)
        res = await self.session.execute(stmt)
        policy = res.scalar_one_or_none()

        if not policy:
            raise RepositoryGovernanceError(f"Policy key '{key}' does not exist. Use create_policy instead.")

        import uuid as uuid_pkg

        # Perform optimistic update
        update_stmt = (
            update(SystemPolicyRecord)
            .where(
                SystemPolicyRecord.policy_key == key,
                SystemPolicyRecord.version == current_version,
            )
            .values(
                policy_value=value,
                version=current_version + 1,
                updated_by=updated_by,
            )
        )
        result = await self.session.execute(update_stmt)
        await self.session.flush()

        if result.rowcount == 0:
            await self._write_audit(
                "PolicyVersionConflict",
                {
                    "policy_key": key,
                    "attempted_version": current_version,
                    "reason": "Concurrent update detected",
                },
                actor=updated_by,
            )
            raise RepositoryGovernanceError(
                f"Optimistic lock conflict: policy '{key}' was modified by another operator."
            )

        # Insert history log revision (Component 3: Revision History)
        history = SystemPolicyHistoryRecord(
            id=uuid_pkg.uuid4(),
            policy_key=key,
            policy_value=value,
            version=current_version + 1,
            updated_by=updated_by,
            change_type="update",
            created_at=datetime.now(UTC),
        )
        self.session.add(history)
        await self.session.flush()

        await self._write_audit(
            "PolicyUpdated",
            {
                "policy_key": key,
                "version": current_version + 1,
                "value": value,
            },
            actor=updated_by,
        )

    async def create_policy(self, key: str, value: Any, updated_by: str) -> None:
        """Initialize a new system policy registry record."""
        self._validate_policy_schema(key, value)

        import uuid as uuid_pkg

        policy = SystemPolicyRecord(
            id=uuid_pkg.uuid4(),
            policy_key=key,
            policy_value=value,
            version=1,
            updated_by=updated_by,
            created_at=datetime.now(UTC),
        )
        self.session.add(policy)

        # Insert history
        history = SystemPolicyHistoryRecord(
            id=uuid_pkg.uuid4(),
            policy_key=key,
            policy_value=value,
            version=1,
            updated_by=updated_by,
            change_type="create",
            created_at=datetime.now(UTC),
        )
        self.session.add(history)
        await self.session.flush()

        await self._write_audit(
            "PolicyCreated",
            {"policy_key": key, "value": value},
            actor=updated_by,
        )

    def _validate_policy_schema(self, key: str, value: Any) -> None:
        """Validate dynamic policies against expected type constraints (schema definitions)."""
        try:
            if key == "allowed_runtimes":
                if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                    raise TypeError("allowed_runtimes must be a list of strings")
            elif key == "global_command_blacklist":
                if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                    raise TypeError("global_command_blacklist must be a list of strings")
            elif key == "default_concurrency_limit":
                if not isinstance(value, int) or value <= 0:
                    raise TypeError("default_concurrency_limit must be a positive integer")
            elif key == "required_runtime_policy" and not isinstance(value, str):
                raise TypeError("required_runtime_policy must be a string")
        except Exception as e:
            raise PolicyValidationError(f"Schema validation failed for policy '{key}': {e!s}") from e

    async def seed_default_policies(self) -> None:
        """Verify if system policies are seeded, and perform idempotent first-boot seeding.

        Writes PolicyRegistrySeeded events to audit logs and tracks metadata.
        """
        import uuid as uuid_pkg

        # Check existing policies
        stmt = select(SystemPolicyRecord)
        res = await self.session.execute(stmt)
        existing_policies = res.scalars().all()
        existing_keys = {p.policy_key for p in existing_policies}

        defaults_map = {
            "allowed_runtimes": policy_defaults.ALLOWED_RUNTIMES,
            "global_command_blacklist": policy_defaults.GLOBAL_COMMAND_BLACKLIST,
            "default_concurrency_limit": policy_defaults.DEFAULT_CONCURRENCY_LIMIT,
            "required_runtime_policy": policy_defaults.REQUIRED_RUNTIME_POLICY,
            "concurrency_retry_count": policy_defaults.CONCURRENCY_RETRY_COUNT,
            "concurrency_retry_timeout": policy_defaults.CONCURRENCY_RETRY_TIMEOUT,
        }

        seeded_keys = []
        for key, val in defaults_map.items():
            if key not in existing_keys:
                policy = SystemPolicyRecord(
                    id=uuid_pkg.uuid4(),
                    policy_key=key,
                    policy_value=val,
                    version=1,
                    updated_by="system_seeder",
                    created_at=datetime.now(UTC),
                )
                self.session.add(policy)

                # History record (Component 3: Revision History)
                history = SystemPolicyHistoryRecord(
                    id=uuid_pkg.uuid4(),
                    policy_key=key,
                    policy_value=val,
                    version=1,
                    updated_by="system_seeder",
                    change_type="create",
                    created_at=datetime.now(UTC),
                )
                self.session.add(history)
                seeded_keys.append(key)

        if seeded_keys:
            await self.session.flush()
            await self._write_audit(
                "PolicyRegistrySeeded",
                {
                    "seeded_keys": seeded_keys,
                    "source": "code_defaults_v1",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                actor="system_seeder",
            )
