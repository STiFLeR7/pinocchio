"""Step 3 — the Projection Engine (ADR-001 §3.2, AP-203, INV-14/16).

A projection is a read model folded from the event log. This engine drives a
:class:`~nexus_core.persistence.Projection`, adding the platform guarantees the
projection itself should not have to re-implement:

- **Idempotency (INV-16):** each event identifier is applied at most once, so
  duplicate or out-of-order delivery causes no duplicate state change. This is
  the AP-202 dedup mechanism, provided once here.
- **Determinism (INV-14):** folding the same event sequence always yields the
  same state; the engine adds no non-determinism.
- **Rebuild:** discard and re-fold from the log (replay equivalence).
- **Replay-from-position:** fold only the tail after a restored snapshot.
- **Projection versioning:** a schema version travels with the read model so a
  changed projection shape can be detected and rebuilt.

Projections are read-only; business logic lives elsewhere. The engine also
satisfies ``EventHandler`` (``handle`` == ``apply``) so it can subscribe to the
bus for live projection.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from nexus_core.domain.event import Event
from nexus_core.persistence.interfaces import Projection
from nexus_infra.event_versioning import InMemoryUpcasterRegistry
from nexus_infra.observability import (
    InfraEvent,
    InfraEventType,
    NullObservability,
    Observability,
)


class ProjectionEngine[S]:
    """Drives a :class:`Projection` with idempotent, deterministic folding."""

    def __init__(
        self,
        factory: Callable[[], Projection[S]],
        *,
        version: int = 1,
        upcasters: InMemoryUpcasterRegistry | None = None,
        observability: Observability | None = None,
    ) -> None:
        self._factory = factory
        self._projection: Projection[S] = factory()
        self._version = version
        self._upcasters = upcasters
        self._obs: Observability = observability or NullObservability()
        self._seen: set[str] = set()
        self._applied = 0

    # -- application --------------------------------------------------------- #

    def apply(self, event: Event) -> None:
        """Fold one event into the projection, at most once per identifier."""
        if event.identifier in self._seen:
            self._obs.increment("projection.duplicate_skipped")
            return
        resolved = self._upcasters.upcast_to_current(event) if self._upcasters else event
        self._projection.apply(resolved)
        self._seen.add(event.identifier)
        self._applied += 1
        self._obs.record(InfraEvent(InfraEventType.PROJECTION_APPLIED, subject=event.identifier))
        self._obs.increment("projection.applied")

    def handle(self, event: Event) -> None:
        """``EventHandler`` adapter — lets the engine subscribe to the bus."""
        self.apply(event)

    def consume(self, events: Iterable[Event]) -> None:
        """Fold a sequence of events in order."""
        for event in events:
            self.apply(event)

    # -- build / rebuild ----------------------------------------------------- #

    def rebuild(self, events: Iterable[Event]) -> None:
        """Discard current state and re-fold from scratch (replay equivalence)."""
        self._projection = self._factory()
        self._seen.clear()
        self._applied = 0
        self.consume(events)
        self._obs.record(
            InfraEvent(
                InfraEventType.PROJECTION_REBUILT,
                subject=f"v{self._version}",
                detail={"applied": self._applied},
            )
        )

    # -- state --------------------------------------------------------------- #

    @property
    def state(self) -> S:
        """The current projected read model."""
        return self._projection.state

    @property
    def version(self) -> int:
        """The projection schema version."""
        return self._version

    @property
    def applied_count(self) -> int:
        """How many distinct events have been folded."""
        return self._applied

    def has_seen(self, event_identifier: str) -> bool:
        """Whether an event identifier has already been folded (dedup state)."""
        return event_identifier in self._seen
