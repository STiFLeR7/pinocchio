"""Execution runners for executing tools and scripts."""

from __future__ import annotations

import uuid
from typing import Any

from nexus.execution.runners.base import BaseRuntimeAdapter


class RuntimeRegistry:
    """Registry pattern mapping runner names to their concrete adapters."""

    def __init__(self) -> None:
        self._registry: dict[str, type[BaseRuntimeAdapter]] = {}

    def register(self, runtime_id: str) -> Any:
        """Decorator to register a runtime adapter class."""
        def decorator(cls: type[BaseRuntimeAdapter]) -> type[BaseRuntimeAdapter]:
            self._registry[runtime_id.lower()] = cls
            return cls
        return decorator

    def get_adapter_cls(self, runtime_id: str) -> type[BaseRuntimeAdapter]:
        """Resolve a registered runtime class by its ID."""
        clean_id = runtime_id.lower().replace("_", "").replace("-", "")
        # Handle aliases
        if clean_id == "claudecode":
            clean_id = "claude"
        # Back-compat: the Nexus agent runtime was developed under the codename "hermes".
        # Legacy ``runner="hermes"`` / ``"hermes_agent"`` values resolve to the renamed runtime.
        if clean_id in ("hermes", "hermesagent"):
            clean_id = "nexus"

        cls = self._registry.get(clean_id)
        if not cls:
            raise KeyError(f"No runtime adapter registered for runner ID: {runtime_id}")
        return cls


runtime_registry = RuntimeRegistry()


def get_runtime_adapter(
    runner_name: str,
    db_session: Any,
    execution_id: uuid.UUID,
    event_gateway: Any = None,
    openrouter_client: Any = None,
    settings: Any = None,
) -> BaseRuntimeAdapter:
    """Resolve and instantiate the correct execution adapter by runner name using the registry."""
    # Import modules to trigger registration decorators
    from typing import cast

    from nexus.execution.runners.claude import ClaudeRuntimeAdapter  # noqa: F401
    from nexus.execution.runners.gemini import GeminiRuntimeAdapter  # noqa: F401
    from nexus.execution.runners.nexus_agent import NexusRuntimeAdapter  # noqa: F401
    cls: Any = runtime_registry.get_adapter_cls(runner_name)
    return cast(
        BaseRuntimeAdapter,
        cls(
            db_session=db_session,
            execution_id=execution_id,
            event_gateway=event_gateway,
            openrouter_client=openrouter_client,
            settings=settings,
        ),
    )
