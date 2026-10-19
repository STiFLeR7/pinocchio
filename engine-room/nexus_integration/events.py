"""Migration events — the ``migration.*`` facts the integration substrate records.

Recorded Shadow Adjudication (ADR-008 §3.2) records three facts per decision plus flag
changes, all as canonical :class:`~nexus_core.domain.event.Event` s in the durable log
(ADR-007) under one correlation stream (INV-39), append-only (INV-13):

- ``migration.decision_recorded`` — the legacy decision at the owner's boundary
  (ADR-008 *DecisionRecord*: inputs echo, value, decision identity, engine version).
- ``migration.shadow_decision`` — the constitutional owner's side-effect-free shadow
  (*ShadowDecision*).
- ``migration.decision_diff`` — the classified comparison (*DecisionDiff*).
- ``migration.flag_set`` — a per-owner flag transition (durable, versioned, replayable).

Timestamps are captured as data (INV-17); the source is injected so replay is
reproducible and the value objects stay timestamp-free.
"""

from __future__ import annotations

from datetime import UTC, datetime

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event

__all__ = [
    "MIGRATION_DECISION_DIFF",
    "MIGRATION_DECISION_RECORDED",
    "MIGRATION_FLAG_SET",
    "MIGRATION_SHADOW_DECISION",
    "build_event",
    "system_now",
]

MIGRATION_PRODUCER = "integration"
MIGRATION_SOURCE = "nexus_integration"
EVENT_VERSION = "1"

MIGRATION_DECISION_RECORDED = "migration.decision_recorded"
MIGRATION_SHADOW_DECISION = "migration.shadow_decision"
MIGRATION_DECISION_DIFF = "migration.decision_diff"
MIGRATION_FLAG_SET = "migration.flag_set"


def system_now() -> str:
    """Default timestamp source: wall-clock UTC, ISO-8601 (captured as event data)."""
    return datetime.now(UTC).isoformat()


def build_event(
    identifier: str,
    event_type: str,
    correlation_identifier: str,
    payload: Struct,
    timestamp: str,
    *,
    causation_identifier: str | None = None,
) -> Event:
    """Construct a canonical migration Event with deterministic identity."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=MIGRATION_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload=payload,
        source=MIGRATION_SOURCE,
        causation_identifier=causation_identifier,
    )
