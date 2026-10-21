"""Unit tests for the Nexus exception hierarchy."""

from __future__ import annotations

from nexus.core.exceptions import (
    AgentRouterError,
    ApprovalEngineError,
    CommunicationError,
    ConfigurationError,
    DatabaseError,
    DiscordError,
    EmailError,
    EventGatewayError,
    ExecutionEngineError,
    ExecutionTimeoutError,
    ModelRouterError,
    NexusError,
    RepositoryNotRegisteredError,
    TaskEngineError,
    UnauthorizedActionError,
    UnroutableEventError,
)
from nexus.core.types import EventType


def test_nexus_error_is_base() -> None:
    """Verify that NexusError derives from Python's Exception."""
    assert issubclass(NexusError, Exception)


def test_exception_hierarchy() -> None:
    """Verify that all specific exceptions subclass NexusError."""
    exceptions = [
        ConfigurationError,
        DatabaseError,
        EventGatewayError,
        TaskEngineError,
        ApprovalEngineError,
        ExecutionEngineError,
        ExecutionTimeoutError,
        AgentRouterError,
        UnroutableEventError,
        ModelRouterError,
        UnauthorizedActionError,
        RepositoryNotRegisteredError,
        CommunicationError,
        DiscordError,
        EmailError,
    ]
    for exc in exceptions:
        assert issubclass(exc, NexusError)


def test_unauthorized_action_error() -> None:
    """Verify detail field in exceptions."""
    err = UnauthorizedActionError("Forbidden", detail="Missing token")
    assert str(err) == "Forbidden"
    assert err.detail == "Missing token"


def test_agent_router_error() -> None:
    """Verify AgentRouterError attributes."""
    err = AgentRouterError("Failed", event_type=EventType.TASK_CREATED)
    assert err.event_type == EventType.TASK_CREATED
