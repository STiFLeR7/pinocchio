"""Emit / consume seams for Events.

These are the boundaries a Phase-2 event bus implements. The foundation defines
them so producers and consumers depend on abstractions, not a concrete bus.
Consumers are required to be **idempotent** (INV-16): handling the same Event
identifier more than once must cause no duplicate effect — the implementation
detail of *how* (dedup store) belongs to the consumer, but the contract is here.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from nexus_core.domain.event import Event


@runtime_checkable
class EventEmitter(Protocol):
    """Appends an Event to the authoritative log (the only way a fact becomes true)."""

    def emit(self, event: Event) -> None: ...


@runtime_checkable
class EventHandler(Protocol):
    """Handles a single delivered Event. Must be idempotent over ``event.identifier``."""

    def handle(self, event: Event) -> None: ...


@runtime_checkable
class EventConsumer(Protocol):
    """Subscribes a handler to events, typically filtered by type or correlation.

    Delivery is at-least-once; the consumer (or its handler) deduplicates by
    ``event.identifier`` (INV-16). Ordering within a correlation stream is
    causal/deterministic (doc 23).
    """

    def subscribe(self, handler: EventHandler) -> None: ...

    def unsubscribe(self, handler: EventHandler) -> None: ...
