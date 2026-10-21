"""Unit tests for nexus_harness.events.

Pins the 10 event-type constant strings, the injectable timestamp sources
(fixed/system) and their Protocol conformance, and build_event's canonical
Event construction (producer/source/version, explicit execution_identifier=None,
pass-through fields, and immutability).
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from nexus_core.domain.event import Event
from nexus_harness.events import (
    ARTIFACTS_RESOLVED,
    CAPABILITIES_RESOLVED,
    CONTEXT_RESOLVED,
    EVENT_VERSION,
    EXECUTION_MANIFEST_CREATED,
    EXECUTION_PACKAGE_CREATED,
    HARNESS_COMPLETED,
    HARNESS_FAILED,
    HARNESS_PRODUCER,
    HARNESS_REQUEST_VALIDATED,
    HARNESS_SOURCE,
    POLICIES_RESOLVED,
    SKILLS_RESOLVED,
    FixedTimestampSource,
    SystemTimestampSource,
    TimestampSource,
    build_event,
)

# ---------------------------------------------------------------------------
# Layer identity constants
# ---------------------------------------------------------------------------


def test_layer_identity_constants() -> None:
    assert HARNESS_PRODUCER == "harness"
    assert HARNESS_SOURCE == "nexus_harness"
    assert EVENT_VERSION == "1"


# ---------------------------------------------------------------------------
# Event-type constant strings
# ---------------------------------------------------------------------------


def test_harness_request_validated_constant() -> None:
    assert HARNESS_REQUEST_VALIDATED == "harness.request_validated"


def test_skills_resolved_constant() -> None:
    assert SKILLS_RESOLVED == "harness.skills_resolved"


def test_capabilities_resolved_constant() -> None:
    assert CAPABILITIES_RESOLVED == "harness.capabilities_resolved"


def test_policies_resolved_constant() -> None:
    assert POLICIES_RESOLVED == "harness.policies_resolved"


def test_context_resolved_constant() -> None:
    assert CONTEXT_RESOLVED == "harness.context_resolved"


def test_artifacts_resolved_constant() -> None:
    assert ARTIFACTS_RESOLVED == "harness.artifacts_resolved"


def test_execution_package_created_constant() -> None:
    assert EXECUTION_PACKAGE_CREATED == "harness.execution_package_created"


def test_execution_manifest_created_constant() -> None:
    assert EXECUTION_MANIFEST_CREATED == "harness.execution_manifest_created"


def test_harness_completed_constant() -> None:
    assert HARNESS_COMPLETED == "harness.completed"


def test_harness_failed_constant() -> None:
    assert HARNESS_FAILED == "harness.failed"


def test_all_event_type_constants_are_distinct() -> None:
    constants = [
        HARNESS_REQUEST_VALIDATED,
        SKILLS_RESOLVED,
        CAPABILITIES_RESOLVED,
        POLICIES_RESOLVED,
        CONTEXT_RESOLVED,
        ARTIFACTS_RESOLVED,
        EXECUTION_PACKAGE_CREATED,
        EXECUTION_MANIFEST_CREATED,
        HARNESS_COMPLETED,
        HARNESS_FAILED,
    ]
    assert len(constants) == len(set(constants))


# ---------------------------------------------------------------------------
# FixedTimestampSource
# ---------------------------------------------------------------------------


def test_fixed_timestamp_source_returns_configured_value() -> None:
    source = FixedTimestampSource("2026-06-30T12:00:00+00:00")
    assert source.now() == "2026-06-30T12:00:00+00:00"


def test_fixed_timestamp_source_default_is_epoch() -> None:
    assert FixedTimestampSource().now() == "1970-01-01T00:00:00+00:00"


def test_fixed_timestamp_source_is_deterministic() -> None:
    source = FixedTimestampSource("2026-01-01T00:00:00+00:00")
    assert source.now() == source.now()


def test_fixed_timestamp_source_implements_protocol() -> None:
    assert isinstance(FixedTimestampSource(), TimestampSource)


# ---------------------------------------------------------------------------
# SystemTimestampSource
# ---------------------------------------------------------------------------


def test_system_timestamp_source_returns_iso8601_string() -> None:
    value = SystemTimestampSource().now()
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None


def test_system_timestamp_source_implements_protocol() -> None:
    assert isinstance(SystemTimestampSource(), TimestampSource)


# ---------------------------------------------------------------------------
# build_event — canonical construction
# ---------------------------------------------------------------------------


def test_build_event_constructs_event_instance() -> None:
    event = build_event(
        "evt-scope-package-0001",
        HARNESS_REQUEST_VALIDATED,
        "cor-goal-1",
        {},
        "1970-01-01T00:00:00+00:00",
    )
    assert isinstance(event, Event)


def test_build_event_sets_producer_to_harness() -> None:
    event = build_event(
        "evt-1",
        HARNESS_REQUEST_VALIDATED,
        "cor-x",
        {},
        "1970-01-01T00:00:00+00:00",
    )
    assert event.producer == "harness"


def test_build_event_sets_source_to_nexus_harness() -> None:
    event = build_event(
        "evt-1",
        HARNESS_REQUEST_VALIDATED,
        "cor-x",
        {},
        "1970-01-01T00:00:00+00:00",
    )
    assert event.source == "nexus_harness"


def test_build_event_sets_version() -> None:
    event = build_event(
        "evt-1",
        HARNESS_REQUEST_VALIDATED,
        "cor-x",
        {},
        "1970-01-01T00:00:00+00:00",
    )
    assert event.version == "1"


def test_build_event_sets_execution_identifier_to_none() -> None:
    event = build_event(
        "evt-1",
        EXECUTION_PACKAGE_CREATED,
        "cor-x",
        {},
        "1970-01-01T00:00:00+00:00",
    )
    assert event.execution_identifier is None


def test_build_event_passes_through_all_required_fields() -> None:
    payload = {"pkg": "pkg-hreq-session-1-nodeA"}
    event = build_event(
        "evt-scope-package-0042",
        EXECUTION_PACKAGE_CREATED,
        "cor-goal-1",
        payload,
        "2026-06-30T00:00:00+00:00",
    )
    assert event.identifier == "evt-scope-package-0042"
    assert event.type == EXECUTION_PACKAGE_CREATED
    assert event.correlation_identifier == "cor-goal-1"
    assert event.payload == payload
    assert event.timestamp == "2026-06-30T00:00:00+00:00"


def test_build_event_optional_fields_default_to_none() -> None:
    event = build_event(
        "evt-1",
        HARNESS_COMPLETED,
        "cor-x",
        {},
        "1970-01-01T00:00:00+00:00",
    )
    assert event.sequence_position is None
    assert event.causation_identifier is None


def test_build_event_sequence_position_passes_through() -> None:
    event = build_event(
        "evt-2",
        SKILLS_RESOLVED,
        "cor-x",
        {},
        "1970-01-01T00:00:00+00:00",
        sequence_position=7,
    )
    assert event.sequence_position == 7


def test_build_event_causation_identifier_passes_through() -> None:
    event = build_event(
        "evt-3",
        CAPABILITIES_RESOLVED,
        "cor-x",
        {},
        "1970-01-01T00:00:00+00:00",
        causation_identifier="evt-2",
    )
    assert event.causation_identifier == "evt-2"


def test_build_event_both_optional_fields_pass_through() -> None:
    event = build_event(
        "evt-4",
        HARNESS_FAILED,
        "cor-x",
        {"reason": "missing skill"},
        "1970-01-01T00:00:00+00:00",
        sequence_position=3,
        causation_identifier="evt-1",
    )
    assert event.sequence_position == 3
    assert event.causation_identifier == "evt-1"


def test_build_event_produces_frozen_event() -> None:
    event = build_event(
        "evt-1",
        HARNESS_REQUEST_VALIDATED,
        "cor-x",
        {},
        "1970-01-01T00:00:00+00:00",
    )
    with pytest.raises(ValidationError):
        event.identifier = "mutated"  # type: ignore[misc]
