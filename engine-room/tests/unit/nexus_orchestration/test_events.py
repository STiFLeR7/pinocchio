"""Unit tests for orchestration events (the operational facts the Orchestrator emits).

These tests pin the canonical event-type constant strings, the injectable
timestamp sources (fixed/system) and their Protocol conformance, and
``build_event``'s canonical Event construction (producer/source/version,
explicit ``execution_identifier=None``, pass-through fields, immutability).
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from nexus_core.domain.event import Event
from nexus_orchestration.events import (
    APPROVAL_GRANTED,
    APPROVAL_REJECTED,
    APPROVAL_REQUESTED,
    DEPENDENCY_SATISFIED,
    EVENT_VERSION,
    EXECUTION_QUEUED,
    EXECUTION_SESSION_CREATED,
    HARNESS_REQUEST_CREATED,
    ORCHESTRATION_COMPLETED,
    ORCHESTRATION_FAILED,
    ORCHESTRATION_PRODUCER,
    ORCHESTRATION_SOURCE,
    RUNTIME_REQUEST_CREATED,
    WORK_PACKAGE_READY,
    FixedTimestampSource,
    SystemTimestampSource,
    TimestampSource,
    build_event,
)


def test_event_type_constant_values() -> None:
    assert EXECUTION_SESSION_CREATED == "orchestration.execution_session_created"
    assert WORK_PACKAGE_READY == "orchestration.work_package_ready"
    assert DEPENDENCY_SATISFIED == "orchestration.dependency_satisfied"
    assert EXECUTION_QUEUED == "orchestration.execution_queued"
    assert APPROVAL_REQUESTED == "orchestration.approval_requested"
    assert APPROVAL_GRANTED == "orchestration.approval_granted"
    assert APPROVAL_REJECTED == "orchestration.approval_rejected"
    assert HARNESS_REQUEST_CREATED == "orchestration.harness_request_created"
    assert RUNTIME_REQUEST_CREATED == "orchestration.runtime_request_created"
    assert ORCHESTRATION_COMPLETED == "orchestration.completed"
    assert ORCHESTRATION_FAILED == "orchestration.failed"


def test_layer_identity_constants() -> None:
    assert ORCHESTRATION_PRODUCER == "orchestration"
    assert ORCHESTRATION_SOURCE == "nexus_orchestration"
    assert EVENT_VERSION == "1"


def test_fixed_timestamp_source_returns_value() -> None:
    source = FixedTimestampSource("2026-06-30T12:00:00+00:00")
    assert source.now() == "2026-06-30T12:00:00+00:00"


def test_fixed_timestamp_source_default_is_epoch() -> None:
    assert FixedTimestampSource().now() == "1970-01-01T00:00:00+00:00"


def test_system_timestamp_source_parses_as_iso() -> None:
    value = SystemTimestampSource().now()
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None


def test_fixed_timestamp_source_is_timestamp_source() -> None:
    assert isinstance(FixedTimestampSource(), TimestampSource)


def test_system_timestamp_source_is_timestamp_source() -> None:
    assert isinstance(SystemTimestampSource(), TimestampSource)


def test_build_event_constructs_canonical_event() -> None:
    payload = {"node": "node-a"}
    event = build_event(
        "evt-1",
        EXECUTION_SESSION_CREATED,
        "cor-x",
        payload,
        "1970-01-01T00:00:00+00:00",
    )
    assert isinstance(event, Event)
    assert event.identifier == "evt-1"
    assert event.type == EXECUTION_SESSION_CREATED
    assert event.version == "1"
    assert event.timestamp == "1970-01-01T00:00:00+00:00"
    assert event.producer == "orchestration"
    assert event.source == "nexus_orchestration"
    assert event.correlation_identifier == "cor-x"
    assert event.execution_identifier is None
    assert event.payload == payload


def test_build_event_optional_fields_default_to_none() -> None:
    event = build_event(
        "evt-1",
        WORK_PACKAGE_READY,
        "cor-x",
        {},
        "1970-01-01T00:00:00+00:00",
    )
    assert event.sequence_position is None
    assert event.causation_identifier is None


def test_build_event_optional_fields_pass_through() -> None:
    event = build_event(
        "evt-2",
        DEPENDENCY_SATISFIED,
        "cor-x",
        {},
        "1970-01-01T00:00:00+00:00",
        sequence_position=3,
        causation_identifier="evt-1",
    )
    assert event.sequence_position == 3
    assert event.causation_identifier == "evt-1"


def test_build_event_produces_frozen_event() -> None:
    event = build_event(
        "evt-1",
        EXECUTION_QUEUED,
        "cor-x",
        {},
        "1970-01-01T00:00:00+00:00",
    )
    with pytest.raises(ValidationError):
        event.identifier = "mutated"  # type: ignore[misc]
