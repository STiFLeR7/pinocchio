"""Event — the authoritative, immutable, append-only unit of operational truth.

Contract: ``contracts/event.md``. Binding: ADR-001 (Event is authoritative; State
and Checkpoints derive from the log), ADR-003. Invariants: INV-13, INV-15, INV-16,
INV-17, INV-07, INV-39.

The Event is the one envelope every layer produces. Its schema is canonical and
singular; the ``producer`` field records which layer emitted each instance. An
Event is immutable: a correction is a new Event, never an edit.
"""

from __future__ import annotations

from typing import ClassVar

from nexus_core.contracts.base import DomainObject, Struct
from nexus_core.contracts.enums import Priority


class Event(DomainObject):
    """A single, immutable operational fact (contract: event.md)."""

    LIFECYCLE_NAME: ClassVar[str] = "event"

    # --- required ---------------------------------------------------------- #
    identifier: str
    """Globally unique identity; the dedup key for idempotent consumption (INV-16)."""
    type: str
    """Canonical event type (e.g. ``goal.created``, ``execution.started``)."""
    version: str
    """Schema version of this event type; enables upcasting (ADR-001 §6)."""
    timestamp: str
    """When the fact occurred/was recorded; captured as data so replay is deterministic (INV-17)."""
    producer: str
    """The subsystem/layer that emitted the Event."""
    correlation_identifier: str
    """Ties this Event to all Events of the same operation; the causal-ordering boundary (INV-39)."""
    execution_identifier: str | None
    """The execution session/context, when applicable (explicit ``None`` when not)."""
    payload: Struct
    """Event-specific data, including non-deterministic values captured as recorded data (INV-17)."""
    source: str
    """Provenance beyond the producing layer (originating surface/runtime adapter)."""

    # --- optional ---------------------------------------------------------- #
    metadata: Struct | None = None
    """Observability/routing context (subsystem, trace id, delivery status, retry count, latency)."""
    schema_version: str | None = None
    """Explicit schema-version marker where the substrate distinguishes it from ``version``."""
    causation_identifier: str | None = None
    """Reference (by id) to the Event that directly caused this one."""
    sequence_position: int | None = None
    """Logical ordered position within the correlation stream (not a storage offset)."""
    priority: Priority | None = None
    """Delivery/observability hint only — never a governance decision."""
