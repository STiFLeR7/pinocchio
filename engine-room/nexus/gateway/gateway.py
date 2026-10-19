"""In-memory event gateway and bus routing for the Nexus Control Plane."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import structlog

from nexus.core.types import EventType

if TYPE_CHECKING:
    from nexus.core.events import NexusEvent

logger = structlog.get_logger("nexus.gateway")


class EventGateway:
    """Coordinates event distribution and routes NexusEvents asynchronously."""

    def __init__(self) -> None:
        """Initialize the event routing mapping dictionary."""
        self._subscribers: dict[EventType, list[Callable[[NexusEvent], Awaitable[None]]]] = (
            defaultdict(list)
        )

    def subscribe(
        self,
        event_type: EventType,
        callback: Callable[[NexusEvent], Awaitable[None]],
    ) -> None:
        """Register an async callback handler to subscribe to a specific event type."""
        self._subscribers[event_type].append(callback)
        logger.debug("event_subscribed", event_type=event_type, handler=callback.__name__)

    async def publish(self, event: NexusEvent) -> None:
        """Asynchronously dispatch the published event to all subscribed callbacks."""
        event_type = event.event_type
        subscribers = self._subscribers.get(event_type, [])

        logger.info(
            "publishing_event",
            event_id=event.id,
            event_type=event_type.value if hasattr(event_type, "value") else str(event_type),
            correlation_id=event.correlation_id,
            subscriber_count=len(subscribers),
        )

        for callback in subscribers:
            try:
                await callback(event)
            except Exception as e:
                logger.error(
                    "subscriber_callback_failed",
                    event_id=event.id,
                    event_type=(
                        event_type.value if hasattr(event_type, "value") else str(event_type)
                    ),
                    handler=callback.__name__,
                    error=str(e),
                    exc_info=True,
                )
