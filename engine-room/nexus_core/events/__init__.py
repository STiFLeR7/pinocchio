"""Event primitives (Step 5) — the surrounding types and interfaces for the
authoritative Event (the Event model itself lives in ``nexus_core.domain.event``).

Provides ``EventMetadata`` (observability/routing context), identifier and
versioning interfaces, and the emit/consume seams a later-phase event bus will
implement. **No event bus is implemented here** — that belongs to Phase 2
(AP-201). These are interfaces and value objects only, so the substrate honors
at-least-once delivery + idempotency (INV-16) and append-only upcasting
(ADR-001 §6) by contract.
"""

from nexus_core.events.identifiers import IdentifierFactory
from nexus_core.events.interfaces import EventConsumer, EventEmitter, EventHandler
from nexus_core.events.metadata import EventMetadata
from nexus_core.events.versioning import EventUpcaster, UpcasterRegistry

__all__ = [
    "EventConsumer",
    "EventEmitter",
    "EventHandler",
    "EventMetadata",
    "EventUpcaster",
    "IdentifierFactory",
    "UpcasterRegistry",
]
