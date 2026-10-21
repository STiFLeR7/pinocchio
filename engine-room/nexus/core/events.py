"""Nexus event model.

Defines the canonical ``NexusEvent`` Pydantic model used for all
internal event routing, audit logging, and inter-agent communication.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from nexus.core.types import EventType


class NexusEvent(BaseModel):
    """Immutable event envelope for the Nexus event bus.

    Every state transition, action, or notification in Nexus is
    represented as a ``NexusEvent`` and persisted to the audit log.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique event identifier.")
    event_type: EventType = Field(..., description="Canonical event type.")
    entity_type: str = Field(..., description="Type of entity this event relates to (e.g. 'task').")
    entity_id: uuid.UUID | None = Field(
        default=None,
        description="Primary key of the related entity, if any.",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary event payload.",
    )
    correlation_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        description="Correlation identifier for tracing related events.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of event creation.",
    )
    source: str = Field(
        default="nexus",
        description="Component or subsystem that emitted the event.",
    )

    model_config = {"frozen": True}
