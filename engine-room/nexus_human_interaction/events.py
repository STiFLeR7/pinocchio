"""Human-Interaction events — the additive ``interaction.*`` operator-session facts.

The Human Interaction layer records **only** operator-session facts: a session started, a request
submitted, a response recorded, an interaction resumed. It records no reasoning and no engine fact —
the constitutional owners record their own. Each is a canonical
:class:`~nexus_core.domain.event.Event` with ``producer="human_interaction"`` and
``source="nexus_human_interaction"``. The ``interaction.*`` stream is durable, so replay reconstructs the
operator session exactly and a restart resumes it without replaying completed constitutional stages
(INV-13/14/18). Timestamps are injected and captured as data (INV-17).
"""

from __future__ import annotations

from datetime import UTC, datetime

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event

INTERACTION_PRODUCER = "human_interaction"
INTERACTION_SOURCE = "nexus_human_interaction"
EVENT_VERSION = "1"

INTERACTION_SESSION_STARTED = "interaction.session_started"
INTERACTION_REQUEST_SUBMITTED = "interaction.request_submitted"
INTERACTION_RESPONSE_RECORDED = "interaction.response_recorded"
INTERACTION_RESUMED = "interaction.resumed"

__all__ = [
    "INTERACTION_PRODUCER",
    "INTERACTION_REQUEST_SUBMITTED",
    "INTERACTION_RESPONSE_RECORDED",
    "INTERACTION_RESUMED",
    "INTERACTION_SESSION_STARTED",
    "INTERACTION_SOURCE",
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
    """Construct a canonical ``interaction.*`` Event with a single producer (INV-02)."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=INTERACTION_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload=payload,
        source=INTERACTION_SOURCE,
    )
