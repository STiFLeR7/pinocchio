"""Sandbox audit integration mapping events to the central database logs."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from nexus.memory.models import AuditLogRecord


class SandboxAuditIntegration:
    """Bridges sandbox lifecycle events to the central AuditLogRecord model."""

    def __init__(self, db_session: AsyncSession):
        self.session = db_session

    async def audit_event(
        self,
        event_type: str,
        sandbox_id: str,
        data: dict[str, Any] | None = None,
        correlation_id: uuid.UUID | None = None,
    ) -> None:
        """Write an immutable audit log row for the specified sandbox event."""
        audit_rec = AuditLogRecord(
            event_type=event_type,
            entity_type="sandbox",
            entity_id=None,
            data={
                "sandbox_id": sandbox_id,
                **(data or {}),
            },
            correlation_id=correlation_id,
            component="sandbox_manager",
            actor="system",
        )
        self.session.add(audit_rec)
        await self.session.flush()
