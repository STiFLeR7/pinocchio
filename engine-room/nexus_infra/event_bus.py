"""Step 2 — the in-process Event Bus (AP-201).

Synchronous publish/subscribe dispatch within one process. No Kafka, no network,
no broker. Responsibilities: publish, subscribe, unsubscribe, filtered dispatch,
and dead-lettering of events whose handler raises (a poison event must not break
delivery to other handlers, AP-201 acceptance criteria).

Correlation and metadata "propagate" simply because the immutable Event carries
them — the bus passes each event through unchanged. Handlers are idempotent over
``event.identifier`` (INV-16); the bus guarantees at-least-once *delivery* and
preserves registration/append order.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import count

from nexus_core.domain.event import Event
from nexus_core.events.interfaces import EventHandler
from nexus_infra.observability import (
    InfraEvent,
    InfraEventType,
    NullObservability,
    Observability,
)

EventFilter = Callable[[Event], bool]


def accept_all(event: Event) -> bool:
    """A filter that accepts every event."""
    return True


def by_type(*types: str) -> EventFilter:
    """A filter accepting only events whose ``type`` is in ``types``."""
    allowed = frozenset(types)
    return lambda event: event.type in allowed


def by_correlation(correlation_identifier: str) -> EventFilter:
    """A filter accepting only events in one correlation stream."""
    return lambda event: event.correlation_identifier == correlation_identifier


@dataclass(frozen=True, slots=True)
class _Subscription:
    token: int
    handler: EventHandler
    predicate: EventFilter


@dataclass(frozen=True, slots=True)
class DeadLetter:
    """An event that a handler failed to process, retained for inspection/replay."""

    event: Event
    handler: str
    error: str


class InProcessEventBus:
    """A synchronous, single-process event bus implementing ``EventConsumer``."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._subscriptions: list[_Subscription] = []
        self._dead_letters: list[DeadLetter] = []
        self._tokens = count(1)
        self._obs: Observability = observability or NullObservability()

    # -- EventConsumer protocol ---------------------------------------------- #

    def subscribe(self, handler: EventHandler, predicate: EventFilter = accept_all) -> None:
        """Register ``handler``, optionally restricted by ``predicate``."""
        self._subscriptions.append(_Subscription(next(self._tokens), handler, predicate))

    def unsubscribe(self, handler: EventHandler) -> None:
        """Remove every subscription bound to ``handler`` (no error if absent)."""
        self._subscriptions = [s for s in self._subscriptions if s.handler is not handler]

    # -- dispatch ------------------------------------------------------------ #

    def publish(self, event: Event) -> None:
        """Deliver ``event`` to every matching handler, in subscription order.

        A handler that raises does not stop delivery to the others; its failure is
        recorded and the event is dead-lettered for that handler.
        """
        self._obs.record(InfraEvent(InfraEventType.EVENT_PUBLISHED, subject=event.identifier))
        for subscription in tuple(self._subscriptions):
            if not subscription.predicate(event):
                continue
            try:
                subscription.handler.handle(event)
            except Exception as exc:  # bus must isolate one handler's failure from the rest
                self._dead_letter(event, subscription.handler, exc)
            else:
                self._obs.record(
                    InfraEvent(InfraEventType.EVENT_DELIVERED, subject=event.identifier)
                )
                self._obs.increment("event_bus.delivered")

    def _dead_letter(self, event: Event, handler: EventHandler, exc: Exception) -> None:
        self._dead_letters.append(
            DeadLetter(event=event, handler=type(handler).__name__, error=str(exc))
        )
        self._obs.record(
            InfraEvent(
                InfraEventType.HANDLER_FAILED,
                subject=event.identifier,
                detail={"handler": type(handler).__name__, "error": str(exc)},
            )
        )
        self._obs.record(InfraEvent(InfraEventType.EVENT_DEAD_LETTERED, subject=event.identifier))
        self._obs.increment("event_bus.dead_lettered")

    # -- dead-letter inspection ---------------------------------------------- #

    @property
    def dead_letters(self) -> tuple[DeadLetter, ...]:
        """Events that failed delivery, in occurrence order."""
        return tuple(self._dead_letters)

    @property
    def subscription_count(self) -> int:
        """How many active subscriptions exist."""
        return len(self._subscriptions)

    def clear_dead_letters(self) -> None:
        """Discard the dead-letter record (e.g. after operator remediation)."""
        self._dead_letters.clear()
