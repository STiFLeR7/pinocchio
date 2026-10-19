"""Control plane health state tracking module.

Provides:
- Liveness/health check status tracking.
- Git binary startup checks.
"""

from __future__ import annotations

import subprocess
from typing import Any

import structlog

logger = structlog.get_logger("nexus.core.health")

_healthy: bool = True
_health_reason: str = "healthy"


def is_healthy() -> bool:
    """Return the global health status of the control plane."""
    global _healthy
    return _healthy


def get_health_reason() -> str:
    """Return the reason for the current health status."""
    global _health_reason
    return _health_reason


def set_unhealthy(reason: str) -> None:
    """Mark the control plane unhealthy."""
    global _healthy, _health_reason
    _healthy = False
    _health_reason = reason
    logger.critical("control_plane_marked_unhealthy", reason=reason)


def set_healthy() -> None:
    """Mark the control plane healthy."""
    global _healthy, _health_reason
    _healthy = True
    _health_reason = "healthy"
    logger.info("control_plane_marked_healthy")


async def run_git_startup_validation(session_factory: Any = None) -> bool:
    """Validate that Git binary is installed, accessible, and functional.

    If validation fails, mark the control plane unhealthy and write a critical audit event.
    """
    try:
        # Check Git version
        res = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5.0
        )
        if res.returncode == 0:
            set_healthy()
            return True
        else:
            reason = f"Git binary check returned non-zero code {res.returncode}"
            set_unhealthy(reason)
    except Exception as e:
        reason = f"Git binary not found or failed to execute: {e!s}"
        set_unhealthy(reason)

    # If unhealthy, write audit log
    if not is_healthy() and session_factory:
        import uuid
        from datetime import UTC, datetime

        from nexus.database import get_session
        from nexus.memory.models import AuditLogRecord

        try:
            async with get_session(session_factory) as session:
                audit = AuditLogRecord(
                    id=uuid.uuid4(),
                    event_type="SystemUnhealthy",
                    entity_type="system",
                    entity_id=None,
                    data={"reason": get_health_reason(), "dependency": "git"},
                    component="control_plane",
                    actor="system",
                    created_at=datetime.now(UTC)
                )
                session.add(audit)
                await session.flush()
        except Exception as db_err:
            logger.error("failed_to_write_unhealthy_audit_log", error=str(db_err))

    return is_healthy()
