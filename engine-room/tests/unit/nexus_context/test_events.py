"""Unit tests for :mod:`nexus_context.events`.

Phase 4 emits canonical :class:`~nexus_core.domain.event.Event` facts with a
``context_engineering`` producer and a ``nexus_context`` source. Timestamps are the
one captured-as-data value (INV-17); their source is injected so cycles replay
deterministically. These tests pin the event-type constants, the two timestamp
sources (fixed/deterministic and system/parseable), the runtime-checkable
``TimestampSource`` Protocol, and the :func:`build_event` envelope's fixed fields,
pass-through fields, and immutability.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from nexus_context.events import (
    CONTEXT_COLLECTED,
    CONTEXT_COLLECTION_STARTED,
    CONTEXT_ENGINEERING_COMPLETED,
    CONTEXT_ENGINEERING_FAILED,
    CONTEXT_PACKAGE_CREATED,
    CONTEXT_PRODUCER,
    CONTEXT_SOURCE,
    CONTEXT_VALIDATED,
    EVENT_VERSION,
    FixedTimestampSource,
    SystemTimestampSource,
    TimestampSource,
    build_event,
)
from nexus_core.domain.event import Event

# -- type + identity constants ----------------------------------------------- #


def test_event_type_constants_have_expected_values() -> None:
    assert CONTEXT_COLLECTION_STARTED == "context.collection_started"
    assert CONTEXT_COLLECTED == "context.collected"
    assert CONTEXT_VALIDATED == "context.validated"
    assert CONTEXT_PACKAGE_CREATED == "context.package_created"
    assert CONTEXT_ENGINEERING_COMPLETED == "context_engineering.completed"
    assert CONTEXT_ENGINEERING_FAILED == "context_engineering.failed"


def test_producer_source_and_version_constants() -> None:
    assert CONTEXT_PRODUCER == "context_engineering"
    assert CONTEXT_SOURCE == "nexus_context"
    assert EVENT_VERSION == "1"


# -- FixedTimestampSource ---------------------------------------------------- #


def test_fixed_timestamp_source_returns_its_value() -> None:
    source = FixedTimestampSource("2026-06-29T12:00:00+00:00")
    assert source.now() == "2026-06-29T12:00:00+00:00"


def test_fixed_timestamp_source_default_is_epoch() -> None:
    assert FixedTimestampSource().now() == "1970-01-01T00:00:00+00:00"


def test_fixed_timestamp_source_is_deterministic_across_calls() -> None:
    source = FixedTimestampSource("2026-06-29T12:00:00+00:00")
    assert source.now() == source.now()


# -- SystemTimestampSource --------------------------------------------------- #


def test_system_timestamp_source_returns_parseable_iso8601() -> None:
    value = SystemTimestampSource().now()
    # Must parse as ISO-8601; we assert parseability, never a specific instant.
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None


# -- TimestampSource Protocol ------------------------------------------------ #


def test_fixed_timestamp_source_satisfies_protocol() -> None:
    assert isinstance(FixedTimestampSource(), TimestampSource)


def test_system_timestamp_source_satisfies_protocol() -> None:
    assert isinstance(SystemTimestampSource(), TimestampSource)


# -- build_event envelope ---------------------------------------------------- #


def test_build_event_sets_fixed_envelope_fields() -> None:
    event = build_event(
        "evt-1",
        CONTEXT_COLLECTED,
        "cor-1",
        {"count": 3},
        "1970-01-01T00:00:00+00:00",
    )
    assert isinstance(event, Event)
    assert event.producer == "context_engineering"
    assert event.source == "nexus_context"
    assert event.version == "1"
    assert event.execution_identifier is None


def test_build_event_passes_through_given_fields() -> None:
    event = build_event(
        "evt-2",
        CONTEXT_PACKAGE_CREATED,
        "cor-2",
        {"identity": "context-goal-1-v1"},
        "2026-06-29T12:00:00+00:00",
    )
    assert event.identifier == "evt-2"
    assert event.type == CONTEXT_PACKAGE_CREATED
    assert event.correlation_identifier == "cor-2"
    assert event.payload == {"identity": "context-goal-1-v1"}
    assert event.timestamp == "2026-06-29T12:00:00+00:00"


def test_build_event_optionals_default_to_none() -> None:
    event = build_event(
        "evt-3",
        CONTEXT_VALIDATED,
        "cor-3",
        {},
        "1970-01-01T00:00:00+00:00",
    )
    assert event.sequence_position is None
    assert event.causation_identifier is None


def test_build_event_passes_through_optional_fields() -> None:
    event = build_event(
        "evt-4",
        CONTEXT_ENGINEERING_COMPLETED,
        "cor-4",
        {},
        "1970-01-01T00:00:00+00:00",
        sequence_position=7,
        causation_identifier="evt-3",
    )
    assert event.sequence_position == 7
    assert event.causation_identifier == "evt-3"


def test_build_event_uses_fixed_timestamp_source_value() -> None:
    timestamp = FixedTimestampSource().now()
    event = build_event(
        "evt-5",
        CONTEXT_ENGINEERING_FAILED,
        "cor-5",
        {"error": "boom"},
        timestamp,
    )
    assert event.timestamp == "1970-01-01T00:00:00+00:00"


def test_build_event_is_deterministic_for_identical_inputs() -> None:
    args = ("evt-6", CONTEXT_COLLECTION_STARTED, "cor-6", {"k": "v"}, "1970-01-01T00:00:00+00:00")
    assert build_event(*args) == build_event(*args)


def test_event_is_frozen() -> None:
    event = build_event(
        "evt-7",
        CONTEXT_COLLECTED,
        "cor-7",
        {},
        "1970-01-01T00:00:00+00:00",
    )
    with pytest.raises(ValidationError):
        event.identifier = "mutated"  # type: ignore[misc]
