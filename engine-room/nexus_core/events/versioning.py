"""Event versioning interfaces.

Published event types are never mutated in place; schemas evolve by adding new
optional payload fields or new versions, and old Events remain replayable forever
via **upcasting** (ADR-001 §6, doc 23 *Event Versioning*). The foundation defines
the upcasting interface and a registry interface; concrete upcasters are provided
per event-type in later phases.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from nexus_core.domain.event import Event


@runtime_checkable
class EventUpcaster(Protocol):
    """Upgrades an older Event record to the current schema version.

    Upcasting is pure and total over the versions it declares support for: it
    never loses recorded data and never recomputes non-deterministic values
    (INV-17) — it only re-shapes an existing record.
    """

    def can_upcast(self, event_type: str, version: str) -> bool: ...

    def upcast(self, event: Event) -> Event: ...


@runtime_checkable
class UpcasterRegistry(Protocol):
    """Resolves the upcaster(s) needed to bring an Event to the current version."""

    def register(self, upcaster: EventUpcaster) -> None: ...

    def upcast_to_current(self, event: Event) -> Event: ...
