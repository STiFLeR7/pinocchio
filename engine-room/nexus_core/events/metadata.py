"""``EventMetadata`` — the observability/routing context carried by an Event.

These fields (doc 23 *Event Metadata* / *Observability*) describe an Event's
delivery and tracing without altering the meaning of the recorded fact. The
Event model accepts metadata as an opaque ``Struct``; this value object gives a
typed shape for producers and observers that want one.
"""

from __future__ import annotations

from nexus_core.contracts.base import ValueObject
from nexus_core.contracts.enums import Priority


class EventMetadata(ValueObject):
    """Typed observability/routing context for an Event (all fields optional)."""

    subsystem: str | None = None
    execution_session: str | None = None
    goal_identifier: str | None = None
    work_package_identifier: str | None = None
    priority: Priority | None = None
    trace_identifier: str | None = None
    delivery_status: str | None = None
    retry_count: int | None = None
    latency_ms: float | None = None
