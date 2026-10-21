"""Event versioning framework (ADR-001 §6, AP-101).

Published event types are append-only and never mutated; old events stay
replayable forever by **upcasting** them to the current schema version on read.
This module provides the registry that resolves and chains upcasters. It is the
*framework only* — concrete per-event-type upcasters and any data migration are
later-phase concerns. Upcasting is pure: it re-shapes a recorded event, never
recomputes a non-deterministic value (INV-17).
"""

from __future__ import annotations

from nexus_core.domain.event import Event
from nexus_core.events.versioning import EventUpcaster
from nexus_infra.errors import UpcastError

# Guards against an upcaster that claims applicability without advancing version.
_MAX_UPCAST_STEPS = 64


class InMemoryUpcasterRegistry:
    """Resolves and chains upcasters to bring an event to the current version."""

    def __init__(self) -> None:
        self._upcasters: list[EventUpcaster] = []

    def register(self, upcaster: EventUpcaster) -> None:
        """Add an upcaster; later registrations are tried after earlier ones."""
        self._upcasters.append(upcaster)

    def upcast_to_current(self, event: Event) -> Event:
        """Apply applicable upcasters until none remains (a fixed point).

        Raises :class:`UpcastError` if upcasting does not converge (an upcaster
        kept claiming applicability without producing a new version/identifier).
        """
        current = event
        for _ in range(_MAX_UPCAST_STEPS):
            upcaster = self._find(current)
            if upcaster is None:
                return current
            upgraded = upcaster.upcast(current)
            if upgraded == current:
                raise UpcastError(
                    f"upcaster {type(upcaster).__name__} did not advance event "
                    f"{current.identifier!r} (type {current.type!r}, version {current.version!r})"
                )
            current = upgraded
        raise UpcastError(
            f"upcasting did not converge for event {event.identifier!r} after "
            f"{_MAX_UPCAST_STEPS} steps"
        )

    def _find(self, event: Event) -> EventUpcaster | None:
        for upcaster in self._upcasters:
            if upcaster.can_upcast(event.type, event.version):
                return upcaster
        return None
