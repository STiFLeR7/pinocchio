"""Knowledge events -- the ``knowledge.*`` facts the Knowledge Engine emits (doc 07).

Knowledge is **event-sourced** (ADR-001): the durable Item, its version chain, its lifecycle
state, and its freshness are all *projections* of an append-only ``knowledge.*`` stream. Each fact
is a canonical :class:`~nexus_core.domain.event.Event` with ``producer="knowledge"`` and
``source="nexus_knowledge"`` and a deterministic identifier carrying the ``know`` marker (doc 07),
so an ingestion replays identically and never collides with runtime / validation / recovery /
reflection events in the shared, correlated store.

Timestamps are the one captured-as-data, non-structural value (INV-17); their source is injected
so tests are reproducible and the produced *value objects* (Items / Versions) stay timestamp-free
in their identity. ``TimestampSource`` is reused from the runtime layer (Knowledge is downstream)
rather than re-declared, keeping one definition of the primitive.
"""

from __future__ import annotations

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event
from nexus_runtime.events import (  # reused primitive (knowledge -> ... -> runtime)
    FixedTimestampSource,
    SystemTimestampSource,
    TimestampSource,
)

__all__ = [
    "KNOWLEDGE_CANDIDATE_ACCEPTED",
    "KNOWLEDGE_CANDIDATE_RECEIVED",
    "KNOWLEDGE_CANDIDATE_REJECTED",
    "KNOWLEDGE_FEEDBACK_RECORDED",
    "KNOWLEDGE_ITEM_ARCHIVED",
    "KNOWLEDGE_ITEM_CREATED",
    "KNOWLEDGE_ITEM_DEPRECATED",
    "KNOWLEDGE_ITEM_EVOLVED",
    "KNOWLEDGE_ITEM_EXPIRED",
    "KNOWLEDGE_ITEM_SERVED",
    "KNOWLEDGE_ITEM_SUPERSEDED",
    "FixedTimestampSource",
    "SystemTimestampSource",
    "TimestampSource",
    "build_event",
]

KNOWLEDGE_PRODUCER = "knowledge"
KNOWLEDGE_SOURCE = "nexus_knowledge"
EVENT_VERSION = "1"

# --- canonical knowledge.* taxonomy (doc 07) ----------------------------------- #
# Ingestion.
KNOWLEDGE_CANDIDATE_RECEIVED = "knowledge.candidate_received"
KNOWLEDGE_CANDIDATE_ACCEPTED = "knowledge.candidate_accepted"
KNOWLEDGE_CANDIDATE_REJECTED = "knowledge.candidate_rejected"
# Item lifecycle.
KNOWLEDGE_ITEM_CREATED = "knowledge.item_created"
KNOWLEDGE_ITEM_EVOLVED = "knowledge.item_evolved"
KNOWLEDGE_ITEM_SUPERSEDED = "knowledge.item_superseded"
KNOWLEDGE_ITEM_DEPRECATED = "knowledge.item_deprecated"
KNOWLEDGE_ITEM_EXPIRED = "knowledge.item_expired"
KNOWLEDGE_ITEM_ARCHIVED = "knowledge.item_archived"
# Serving (optional, read-only-safe -- emitting changes no Knowledge state).
KNOWLEDGE_ITEM_SERVED = "knowledge.item_served"
KNOWLEDGE_FEEDBACK_RECORDED = "knowledge.feedback_recorded"


def build_event(
    identifier: str,
    event_type: str,
    correlation_identifier: str,
    payload: Struct,
    timestamp: str,
) -> Event:
    """Construct a canonical knowledge Event with deterministic identity."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=KNOWLEDGE_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload=payload,
        source=KNOWLEDGE_SOURCE,
    )
