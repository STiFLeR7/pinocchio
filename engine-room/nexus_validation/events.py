"""Validation events — the ``validation.*`` facts the Validation Engine emits.

Each fact is a canonical :class:`~nexus_core.domain.event.Event` with
``producer="validation"`` and ``source="nexus_validation"`` and a deterministic identifier,
so a validation cycle replays identically (ADR-001; the ``validation.*`` / ``evidence.*``
namespaces are reserved for Validation, doc 15 §4, doc 23 *Validation Events*). Session
state (the report) is a projection of this stream. Timestamps are the one captured-as-data,
non-structural value (INV-17); their source is injected so tests are reproducible and the
produced *value objects* (Evidence / Report) stay timestamp-free and deterministic.

``TimestampSource`` is reused from the runtime layer (validation is downstream of execution,
which is downstream of runtime) rather than re-declared, keeping one definition of the
primitive.
"""

from __future__ import annotations

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event
from nexus_runtime.events import (  # reused primitive (validation → execution → runtime)
    FixedTimestampSource,
    SystemTimestampSource,
    TimestampSource,
)

__all__ = [
    "VALIDATION_COMPLETED",
    "VALIDATION_EVIDENCE_COLLECTED",
    "VALIDATION_FAILED",
    "VALIDATION_RULE_EVALUATED",
    "VALIDATION_STARTED",
    "FixedTimestampSource",
    "SystemTimestampSource",
    "TimestampSource",
    "build_event",
]

VALIDATION_PRODUCER = "validation"
VALIDATION_SOURCE = "nexus_validation"
EVENT_VERSION = "1"

# --- canonical validation.* taxonomy (doc 15 §4 reserved; doc 23) --------------- #
VALIDATION_STARTED = "validation.started"
VALIDATION_EVIDENCE_COLLECTED = "validation.evidence_collected"
VALIDATION_RULE_EVALUATED = "validation.rule_evaluated"
VALIDATION_COMPLETED = "validation.completed"
VALIDATION_FAILED = "validation.failed"


def build_event(
    identifier: str,
    event_type: str,
    correlation_identifier: str,
    payload: Struct,
    timestamp: str,
    *,
    execution_identifier: str | None = None,
) -> Event:
    """Construct a canonical validation Event with deterministic identity."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=VALIDATION_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=execution_identifier,
        payload=payload,
        source=VALIDATION_SOURCE,
    )
