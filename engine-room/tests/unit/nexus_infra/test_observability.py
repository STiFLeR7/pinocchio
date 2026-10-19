"""Tests for :mod:`nexus_infra.observability`.

The substrate emits structured infrastructure events, counters, and timings.

- :class:`InMemoryObservability` collects everything for inspection (records,
  type-filtered queries, accumulating counters, observation lists).
- :func:`timed` measures a wrapped block against an injected :class:`Clock` and
  records the elapsed delta as an observation.
- :class:`NullObservability` is the zero-overhead default — every method a no-op.
"""

from __future__ import annotations

import logging

from nexus_infra import (
    InfraEvent,
    InfraEventType,
    InMemoryObservability,
    LoggingObservability,
    ManualClock,
    NullObservability,
)
from nexus_infra.observability import timed

# -- InMemoryObservability --------------------------------------------------- #


def test_record_stores_infra_events() -> None:
    obs = InMemoryObservability()
    event = InfraEvent(InfraEventType.EVENT_APPENDED, subject="evt-1")

    obs.record(event)

    assert obs.events == [event]


def test_events_of_filters_by_type() -> None:
    obs = InMemoryObservability()
    appended = InfraEvent(InfraEventType.EVENT_APPENDED, subject="evt-1")
    published = InfraEvent(InfraEventType.EVENT_PUBLISHED, subject="evt-1")
    appended_2 = InfraEvent(InfraEventType.EVENT_APPENDED, subject="evt-2")

    obs.record(appended)
    obs.record(published)
    obs.record(appended_2)

    assert obs.events_of(InfraEventType.EVENT_APPENDED) == (appended, appended_2)
    assert obs.events_of(InfraEventType.EVENT_PUBLISHED) == (published,)
    assert obs.events_of(InfraEventType.SNAPSHOT_CREATED) == ()


def test_increment_accumulates_counters() -> None:
    obs = InMemoryObservability()

    obs.increment("appended")
    obs.increment("appended")
    obs.increment("appended", 3)

    assert obs.counters["appended"] == 5


def test_observe_collects_observation_lists() -> None:
    obs = InMemoryObservability()

    obs.observe("latency", 1.0)
    obs.observe("latency", 2.5)
    obs.observe("other", 9.0)

    assert obs.observations["latency"] == [1.0, 2.5]
    assert obs.observations["other"] == [9.0]


# -- timed ------------------------------------------------------------------- #


def test_timed_records_advanced_delta_as_observation() -> None:
    clock = ManualClock(0)
    obs = InMemoryObservability()

    with timed(clock, obs, "m"):
        clock.advance(5)

    assert obs.observations["m"] == [5.0]


def test_timed_with_no_advance_records_zero() -> None:
    clock = ManualClock(100)
    obs = InMemoryObservability()

    with timed(clock, obs, "noop"):
        pass

    assert obs.observations["noop"] == [0.0]


def test_timed_records_even_when_block_raises() -> None:
    clock = ManualClock(0)
    obs = InMemoryObservability()

    try:
        with timed(clock, obs, "boom"):
            clock.advance(7)
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert obs.observations["boom"] == [7.0]


# -- NullObservability ------------------------------------------------------- #


def test_null_observability_methods_are_no_ops() -> None:
    obs = NullObservability()

    assert obs.record(InfraEvent(InfraEventType.EVENT_APPENDED, subject="evt-1")) is None
    assert obs.increment("anything") is None
    assert obs.increment("anything", 5) is None
    assert obs.observe("metric", 1.23) is None


# -- LoggingObservability ------------------------------------------------------ #


def test_logging_observability_logs_infra_events_at_info(caplog) -> None:  # type: ignore[no-untyped-def]
    logger = logging.getLogger("nexus.infra.test")
    obs = LoggingObservability(logger)

    with caplog.at_level(logging.INFO, logger="nexus.infra.test"):
        obs.record(InfraEvent(InfraEventType.EVENT_APPENDED, subject="evt-1", at_sequence=3))

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.INFO
    assert "event.appended" in record.message
    assert "evt-1" in record.message


def test_logging_observability_logs_conflicts_at_warning(caplog) -> None:  # type: ignore[no-untyped-def]
    logger = logging.getLogger("nexus.infra.test")
    obs = LoggingObservability(logger)

    with caplog.at_level(logging.INFO, logger="nexus.infra.test"):
        obs.record(InfraEvent(InfraEventType.CONCURRENCY_CONFLICT, subject="stream-1"))

    assert caplog.records[0].levelno == logging.WARNING


def test_logging_observability_logs_counters_and_observations(caplog) -> None:  # type: ignore[no-untyped-def]
    logger = logging.getLogger("nexus.infra.test")
    obs = LoggingObservability(logger)

    with caplog.at_level(logging.INFO, logger="nexus.infra.test"):
        obs.increment("event_store.appended")
        obs.observe("commit_latency_ns", 12.5)

    assert len(caplog.records) == 2
    assert "event_store.appended" in caplog.records[0].message
    assert "commit_latency_ns" in caplog.records[1].message


def test_logging_observability_defaults_to_a_named_logger() -> None:
    obs = LoggingObservability()

    assert obs._logger.name == "nexus.infra"
