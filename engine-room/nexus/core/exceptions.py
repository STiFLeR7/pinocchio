"""Nexus exception hierarchy.

All Nexus-specific errors derive from ``NexusError`` so callers can
catch a single base class when desired.  Subsystem errors are grouped
by domain to enable targeted error handling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nexus.core.types import EventType

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class NexusError(Exception):
    """Root exception for all Nexus-specific errors."""

    def __init__(self, message: str = "", *, detail: str | None = None) -> None:
        self.detail = detail
        super().__init__(message)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class ConfigurationError(NexusError):
    """Raised when application configuration is invalid or missing."""


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


class DatabaseError(NexusError):
    """Raised on database connectivity or query failures."""


# ---------------------------------------------------------------------------
# Event gateway
# ---------------------------------------------------------------------------


class EventGatewayError(NexusError):
    """Raised when the event gateway cannot dispatch an event."""


# ---------------------------------------------------------------------------
# Task engine
# ---------------------------------------------------------------------------


class TaskEngineError(NexusError):
    """Raised on task lifecycle violations or failures."""


# ---------------------------------------------------------------------------
# Approval engine
# ---------------------------------------------------------------------------


class ApprovalEngineError(NexusError):
    """Raised on approval workflow violations or failures."""


# ---------------------------------------------------------------------------
# Execution engine
# ---------------------------------------------------------------------------


class ExecutionEngineError(NexusError):
    """Raised on execution runner failures."""


class ExecutionTimeoutError(ExecutionEngineError):
    """Raised when an execution exceeds its timeout threshold."""


class SandboxResolutionError(ExecutionEngineError):
    """Raised when an execution sandbox provider cannot be resolved safely (fail-closed).

    Refuses to fall back to host execution when isolation is disabled or the configured provider
    is unrecognized (S-2 / A-006 R-01, R-02).
    """


class SandboxUnavailableError(SandboxResolutionError):
    """Raised when a configured sandbox provider is unavailable at validation time (fail-closed).

    Subclasses :class:`SandboxResolutionError` so existing fail-closed handling still applies. Used
    when the policy-enforcing provider (e.g. Docker) cannot be reached (S-3 / A-006 R-06).
    """


class WorkspaceConfinementError(ExecutionEngineError):
    """Raised when a file operation resolves outside the approved execution workspace (fail-closed).

    Enforces a single containment boundary for runtime file operations so agent file tools cannot
    read or write host paths beyond the approved workspace (S-4 / A-006 R-05).
    """


# ---------------------------------------------------------------------------
# Agent router
# ---------------------------------------------------------------------------


class AgentRouterError(NexusError):
    """Raised when the agent router encounters a problem."""

    def __init__(
        self,
        message: str = "",
        *,
        event_type: EventType | None = None,
        detail: str | None = None,
    ) -> None:
        self.event_type = event_type
        super().__init__(message, detail=detail)


class UnroutableEventError(AgentRouterError):
    """Raised when no agent can handle a given event type."""


# ---------------------------------------------------------------------------
# Model router
# ---------------------------------------------------------------------------


class ModelRouterError(NexusError):
    """Raised when the LLM model router cannot fulfil a request."""


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


class UnauthorizedActionError(NexusError):
    """Raised when a caller lacks permission for an action."""


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class RepositoryNotRegisteredError(NexusError):
    """Raised when referencing an unregistered repository."""


# ---------------------------------------------------------------------------
# Communication
# ---------------------------------------------------------------------------


class CommunicationError(NexusError):
    """Base for communication subsystem errors."""


class DiscordError(CommunicationError):
    """Raised on Discord API or bot failures."""


class EmailError(CommunicationError):
    """Raised on email / SMTP delivery failures."""
