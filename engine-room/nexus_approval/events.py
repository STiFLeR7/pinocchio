"""Approval-Exchange events — the additive ``approval.*`` decision-lifecycle facts.

The Approval Exchange records **only** the approval-coordination lifecycle: a request published, a
request pending, and the terminal operator decision (approved / denied / expired). It records no policy
verdict (Policy owns evaluation — INV-28), no execution fact (Actuation owns traversal), and no
reasoning — it coordinates the *exchange* of an authorization the operator supplies and writes it as
immutable audit (log events, INV-29). Each is a canonical :class:`~nexus_core.domain.event.Event` with
``producer="approval_exchange"`` and ``source="nexus_approval"``. The ``approval.*`` stream is durable, so
replay reconstructs the identical approval history and a restart resumes an in-flight approval wait
(INV-13/14/18). Timestamps are injected and captured as data (INV-17).
"""

from __future__ import annotations

from datetime import UTC, datetime

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event

APPROVAL_PRODUCER = "approval_exchange"
APPROVAL_SOURCE = "nexus_approval"
EVENT_VERSION = "1"

APPROVAL_REQUESTED = "approval.requested"
APPROVAL_PENDING = "approval.pending"
APPROVAL_APPROVED = "approval.approved"
APPROVAL_DENIED = "approval.denied"
APPROVAL_EXPIRED = "approval.expired"

__all__ = [
    "APPROVAL_APPROVED",
    "APPROVAL_DENIED",
    "APPROVAL_EXPIRED",
    "APPROVAL_PENDING",
    "APPROVAL_PRODUCER",
    "APPROVAL_REQUESTED",
    "APPROVAL_SOURCE",
    "build_event",
    "system_now",
]


def system_now() -> str:
    """Default timestamp source: wall-clock UTC, ISO-8601 (captured as event data)."""
    return datetime.now(UTC).isoformat()


def build_event(
    identifier: str,
    event_type: str,
    correlation_identifier: str,
    payload: Struct,
    timestamp: str,
) -> Event:
    """Construct a canonical ``approval.*`` Event with a single producer (INV-02)."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=APPROVAL_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload=payload,
        source=APPROVAL_SOURCE,
    )
