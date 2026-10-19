"""Recovery events — the ``recovery.*`` facts the Recovery Engine emits.

Milestone 4. Each fact is a canonical :class:`~nexus_core.domain.event.Event` with
``producer="recovery"`` and ``source="nexus_recovery"`` and a deterministic identifier, so a
recovery cycle replays identically (ADR-001; the ``recovery.*`` namespace is reserved for
Recovery, doc 19 / doc 23). The Recovery Plan is a projection of this stream. Timestamps are
the one captured-as-data, non-structural value (INV-17); their source is injected so tests are
reproducible and the produced *value object* (the Plan) stays timestamp-free and deterministic.

``TimestampSource`` is reused from the runtime layer (recovery is downstream of validation,
which is downstream of execution, which is downstream of runtime) rather than re-declared,
keeping one definition of the primitive.
"""

from __future__ import annotations

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event
from nexus_runtime.events import (  # reused primitive (recovery → validation → execution → runtime)
    FixedTimestampSource,
    SystemTimestampSource,
    TimestampSource,
)

__all__ = [
    "RECOVERY_COMPLETED",
    "RECOVERY_DECISION_CREATED",
    "RECOVERY_FAILED",
    "RECOVERY_RULE_EVALUATED",
    "RECOVERY_STARTED",
    "FixedTimestampSource",
    "SystemTimestampSource",
    "TimestampSource",
    "build_event",
]

RECOVERY_PRODUCER = "recovery"
RECOVERY_SOURCE = "nexus_recovery"
EVENT_VERSION = "1"

# --- canonical recovery.* taxonomy (doc 19 / doc 23) ---------------------------- #
RECOVERY_STARTED = "recovery.started"
RECOVERY_RULE_EVALUATED = "recovery.rule_evaluated"
RECOVERY_DECISION_CREATED = "recovery.decision_created"
RECOVERY_COMPLETED = "recovery.completed"
RECOVERY_FAILED = "recovery.failed"


def build_event(
    identifier: str,
    event_type: str,
    correlation_identifier: str,
    payload: Struct,
    timestamp: str,
    *,
    execution_identifier: str | None = None,
) -> Event:
    """Construct a canonical recovery Event with deterministic identity."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=RECOVERY_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=execution_identifier,
        payload=payload,
        source=RECOVERY_SOURCE,
    )
