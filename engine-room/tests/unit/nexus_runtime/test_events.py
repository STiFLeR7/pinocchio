"""Unit tests for nexus_runtime.events.

Verifies event-type constants, timestamp sources, and build_event field population.
"""

from __future__ import annotations

from datetime import datetime

from nexus_runtime.events import (
    EVENT_VERSION,
    RUNTIME_ALLOCATED,
    RUNTIME_CAPABILITIES_MATCHED,
    RUNTIME_DISCOVERED,
    RUNTIME_FAILED,
    RUNTIME_PREPARED,
    RUNTIME_PRODUCER,
    RUNTIME_READY,
    RUNTIME_REGISTERED,
    RUNTIME_RELEASED,
    RUNTIME_SESSION_CREATED,
    RUNTIME_SOURCE,
    FixedTimestampSource,
    SystemTimestampSource,
    TimestampSource,
    build_event,
)

# --------------------------------------------------------------------------- #
# Constants                                                                     #
# --------------------------------------------------------------------------- #


def test_runtime_producer_value() -> None:
    assert RUNTIME_PRODUCER == "runtime"


def test_runtime_source_value() -> None:
    assert RUNTIME_SOURCE == "nexus_runtime"


def test_event_version_value() -> None:
    assert EVENT_VERSION == "1"


def test_runtime_registered_value() -> None:
    assert RUNTIME_REGISTERED == "runtime.registered"


def test_runtime_discovered_value() -> None:
    assert RUNTIME_DISCOVERED == "runtime.candidates_resolved"


def test_runtime_capabilities_matched_value() -> None:
    assert RUNTIME_CAPABILITIES_MATCHED == "runtime.capabilities_matched"


def test_runtime_session_created_value() -> None:
    assert RUNTIME_SESSION_CREATED == "runtime.session_created"


def test_runtime_allocated_value() -> None:
    assert RUNTIME_ALLOCATED == "runtime.allocated"


def test_runtime_prepared_value() -> None:
    assert RUNTIME_PREPARED == "runtime.prepared"


def test_runtime_ready_value() -> None:
    assert RUNTIME_READY == "runtime.ready"


def test_runtime_released_value() -> None:
    assert RUNTIME_RELEASED == "runtime.released"


def test_runtime_failed_value() -> None:
    assert RUNTIME_FAILED == "runtime.failed"


# --------------------------------------------------------------------------- #
# TimestampSource — protocol compliance                                         #
# --------------------------------------------------------------------------- #


def test_fixed_timestamp_source_satisfies_protocol() -> None:
    assert isinstance(FixedTimestampSource(), TimestampSource)


def test_system_timestamp_source_satisfies_protocol() -> None:
    assert isinstance(SystemTimestampSource(), TimestampSource)


# --------------------------------------------------------------------------- #
# FixedTimestampSource                                                          #
# --------------------------------------------------------------------------- #


def test_fixed_timestamp_source_default_value() -> None:
    ts = FixedTimestampSource()
    assert ts.now() == "1970-01-01T00:00:00+00:00"


def test_fixed_timestamp_source_custom_value() -> None:
    ts = FixedTimestampSource("2024-06-01T12:00:00+00:00")
    assert ts.now() == "2024-06-01T12:00:00+00:00"


def test_fixed_timestamp_source_is_deterministic() -> None:
    ts = FixedTimestampSource("2024-01-01T00:00:00+00:00")
    assert ts.now() == ts.now()


def test_fixed_timestamp_source_repeated_calls_same_value() -> None:
    ts = FixedTimestampSource("2000-01-01T00:00:00+00:00")
    first = ts.now()
    second = ts.now()
    assert first == second


# --------------------------------------------------------------------------- #
# SystemTimestampSource                                                         #
# --------------------------------------------------------------------------- #


def test_system_timestamp_source_returns_non_empty_string() -> None:
    ts = SystemTimestampSource()
    result = ts.now()
    assert isinstance(result, str)
    assert result  # non-empty


def test_system_timestamp_source_returns_parseable_iso8601() -> None:
    ts = SystemTimestampSource()
    result = ts.now()
    # Must parse without error
    parsed = datetime.fromisoformat(result)
    assert parsed is not None


# --------------------------------------------------------------------------- #
# build_event — required fields                                                 #
# --------------------------------------------------------------------------- #

_FIXED_TS = "1970-01-01T00:00:00+00:00"
_PAYLOAD: dict = {"key": "value"}


def test_build_event_sets_identifier() -> None:
    event = build_event("evt-001", "runtime.ready", "cor-abc", _PAYLOAD, _FIXED_TS)
    assert event.identifier == "evt-001"


def test_build_event_sets_type() -> None:
    event = build_event("evt-001", "runtime.ready", "cor-abc", _PAYLOAD, _FIXED_TS)
    assert event.type == "runtime.ready"


def test_build_event_sets_version() -> None:
    event = build_event("evt-001", "runtime.ready", "cor-abc", _PAYLOAD, _FIXED_TS)
    assert event.version == EVENT_VERSION


def test_build_event_sets_producer() -> None:
    event = build_event("evt-001", "runtime.ready", "cor-abc", _PAYLOAD, _FIXED_TS)
    assert event.producer == RUNTIME_PRODUCER


def test_build_event_sets_source() -> None:
    event = build_event("evt-001", "runtime.ready", "cor-abc", _PAYLOAD, _FIXED_TS)
    assert event.source == RUNTIME_SOURCE


def test_build_event_sets_timestamp() -> None:
    event = build_event("evt-001", "runtime.ready", "cor-abc", _PAYLOAD, _FIXED_TS)
    assert event.timestamp == _FIXED_TS


def test_build_event_sets_correlation_identifier() -> None:
    event = build_event("evt-001", "runtime.ready", "cor-abc", _PAYLOAD, _FIXED_TS)
    assert event.correlation_identifier == "cor-abc"


def test_build_event_sets_payload() -> None:
    event = build_event("evt-001", "runtime.ready", "cor-abc", _PAYLOAD, _FIXED_TS)
    assert event.payload == _PAYLOAD


def test_build_event_execution_identifier_is_none() -> None:
    event = build_event("evt-001", "runtime.ready", "cor-abc", _PAYLOAD, _FIXED_TS)
    assert event.execution_identifier is None


def test_build_event_sequence_position_defaults_to_none() -> None:
    event = build_event("evt-001", "runtime.ready", "cor-abc", _PAYLOAD, _FIXED_TS)
    assert event.sequence_position is None


def test_build_event_causation_identifier_defaults_to_none() -> None:
    event = build_event("evt-001", "runtime.ready", "cor-abc", _PAYLOAD, _FIXED_TS)
    assert event.causation_identifier is None


# --------------------------------------------------------------------------- #
# build_event — optional fields                                                 #
# --------------------------------------------------------------------------- #


def test_build_event_sets_sequence_position_when_provided() -> None:
    event = build_event(
        "evt-002",
        "runtime.allocated",
        "cor-abc",
        {},
        _FIXED_TS,
        sequence_position=7,
    )
    assert event.sequence_position == 7


def test_build_event_sets_causation_identifier_when_provided() -> None:
    event = build_event(
        "evt-003",
        "runtime.allocated",
        "cor-abc",
        {},
        _FIXED_TS,
        causation_identifier="evt-001",
    )
    assert event.causation_identifier == "evt-001"


def test_build_event_sets_both_optional_fields() -> None:
    event = build_event(
        "evt-004",
        "runtime.failed",
        "cor-xyz",
        {"reason": "timeout"},
        _FIXED_TS,
        sequence_position=3,
        causation_identifier="evt-002",
    )
    assert event.sequence_position == 3
    assert event.causation_identifier == "evt-002"


def test_build_event_is_deterministic() -> None:
    e1 = build_event("evt-001", "runtime.ready", "cor-abc", _PAYLOAD, _FIXED_TS)
    e2 = build_event("evt-001", "runtime.ready", "cor-abc", _PAYLOAD, _FIXED_TS)
    assert e1.identifier == e2.identifier
    assert e1.type == e2.type
    assert e1.timestamp == e2.timestamp
