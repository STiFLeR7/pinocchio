"""Unit tests for the NexusEvent Pydantic model."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from nexus.core.events import NexusEvent
from nexus.core.types import EventType


def test_event_creation() -> None:
    """Verify that a NexusEvent can be created with default values and custom fields."""
    entity_id = uuid.uuid4()
    event = NexusEvent(
        event_type=EventType.TASK_CREATED,
        entity_type="task",
        entity_id=entity_id,
        data={"title": "Test Task"},
    )
    assert isinstance(event.id, uuid.UUID)
    assert isinstance(event.timestamp, datetime)
    assert event.event_type == EventType.TASK_CREATED
    assert event.entity_type == "task"
    assert event.entity_id == entity_id
    assert event.data == {"title": "Test Task"}
    assert isinstance(event.correlation_id, uuid.UUID)
    assert event.source == "nexus"


def test_event_serialization() -> None:
    """Verify that model_dump() returns all expected keys for serialization."""
    event = NexusEvent(
        event_type=EventType.TASK_CREATED,
        entity_type="task",
    )
    dumped = event.model_dump()
    assert "id" in dumped
    assert "event_type" in dumped
    assert "entity_type" in dumped
    assert "entity_id" in dumped
    assert "data" in dumped
    assert "correlation_id" in dumped
    assert "timestamp" in dumped
    assert "source" in dumped


def test_event_requires_event_type() -> None:
    """Verify that event_type and entity_type are required fields."""
    with pytest.raises(ValidationError):
        NexusEvent(entity_type="task")  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        NexusEvent(event_type=EventType.TASK_CREATED)  # type: ignore[call-arg]
