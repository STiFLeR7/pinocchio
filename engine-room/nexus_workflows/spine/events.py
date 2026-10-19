"""Constitutional-pipeline events — the additive ``pipeline.*`` stage-coordination facts.

The pipeline coordinator records **only** stage-coordination facts (it owns the *orchestration* of the
constitutional stages, never their behavior — the owners record their own ``intent.*`` / ``planning.*``
/ ``execution.*`` / ``validation.*`` facts unchanged). Each is a canonical
:class:`~nexus_core.domain.event.Event` with ``producer="pipeline"`` and ``source="nexus_workflows.spine"``.
The ``pipeline.*`` stream is the durable spine of a Goal→Knowledge run: it replays the stage
progression and, together with the owners' embedded artifacts, drives restart from the last completed
constitutional boundary (INV-13/14/18). Timestamps are injected and captured as data (INV-17).
"""

from __future__ import annotations

from datetime import UTC, datetime

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event

PIPELINE_PRODUCER = "pipeline"
PIPELINE_SOURCE = "nexus_workflows.spine"
EVENT_VERSION = "1"

PIPELINE_STARTED = "pipeline.started"
PIPELINE_STAGE_STARTED = "pipeline.stage_started"
PIPELINE_STAGE_COMPLETED = "pipeline.stage_completed"
PIPELINE_KNOWLEDGE_GROUNDED = "pipeline.knowledge_grounded"
PIPELINE_PAUSED = "pipeline.paused"
PIPELINE_RESUMED = "pipeline.resumed"
PIPELINE_COMPLETED = "pipeline.completed"

__all__ = [
    "PIPELINE_COMPLETED",
    "PIPELINE_KNOWLEDGE_GROUNDED",
    "PIPELINE_PAUSED",
    "PIPELINE_PRODUCER",
    "PIPELINE_RESUMED",
    "PIPELINE_SOURCE",
    "PIPELINE_STAGE_COMPLETED",
    "PIPELINE_STAGE_STARTED",
    "PIPELINE_STARTED",
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
    """Construct a canonical ``pipeline.*`` Event with a single producer (INV-02)."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=PIPELINE_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=None,
        payload=payload,
        source=PIPELINE_SOURCE,
    )
