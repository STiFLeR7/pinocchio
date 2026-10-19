"""P16/A unit — schedule timing is a deterministic, pure function of injected time.

Occurrences depend only on the timing spec and the injected ``now`` — no wall clock — so replay and restart
reproduce the identical occurrence set, and occurrence indices are stable (which keys de-duplication).
"""

from __future__ import annotations

from nexus_scheduler.model import ScheduleTrigger
from nexus_scheduler.timing import due_occurrences, is_exhausted

T0 = "2026-07-21T00:00:00+00:00"
T1 = "2026-07-21T01:00:00+00:00"
T2 = "2026-07-21T02:00:00+00:00"


def _indices(trigger: ScheduleTrigger, now: str) -> list[int]:
    return [index for index, _ in due_occurrences(trigger, now)]


def test_one_time_fires_once_at_or_after_run_at() -> None:
    trigger = ScheduleTrigger.one_time(T1)
    assert _indices(trigger, T0) == []  # not yet due
    assert _indices(trigger, T1) == [0]
    assert _indices(trigger, T2) == [0]  # still a single occurrence


def test_immediate_and_delayed() -> None:
    immediate = ScheduleTrigger(kind=ScheduleTrigger.immediate().kind, anchor=T0)
    assert _indices(immediate, T0) == [0]
    delayed = ScheduleTrigger(
        kind=ScheduleTrigger.delayed(3600).kind, anchor=T0, delay_seconds=3600
    )
    assert _indices(delayed, T0) == []  # anchor + 1h not reached
    assert _indices(delayed, T1) == [0]


def test_interval_enumerates_all_due_occurrences() -> None:
    trigger = ScheduleTrigger.interval(3600, anchor=T0)
    assert _indices(trigger, T0) == [0]
    assert _indices(trigger, T2) == [0, 1, 2]  # hourly: T0, T1, T2


def test_interval_respects_max_occurrences_and_expiry() -> None:
    capped = ScheduleTrigger.interval(3600, anchor=T0, max_occurrences=2)
    assert _indices(capped, T2) == [0, 1]
    expiring = ScheduleTrigger.interval(3600, anchor=T0, expires_at=T1)
    assert _indices(expiring, T2) == [0, 1]  # T2 occurrence is past the expiry


def test_cron_alias_maps_to_a_deterministic_interval() -> None:
    trigger = ScheduleTrigger.from_cron("@hourly", anchor=T0)
    assert _indices(trigger, T2) == [0, 1, 2]


def test_is_exhausted() -> None:
    assert is_exhausted(ScheduleTrigger.one_time(T1), T2, dispatched=1)
    assert not is_exhausted(ScheduleTrigger.one_time(T1), T2, dispatched=0)
    assert is_exhausted(
        ScheduleTrigger.interval(3600, anchor=T0, max_occurrences=2), T2, dispatched=2
    )
    assert not is_exhausted(ScheduleTrigger.interval(3600, anchor=T0), T2, dispatched=5)
    # an expiring recurring schedule is exhausted once its next occurrence would pass the deadline
    assert is_exhausted(ScheduleTrigger.interval(3600, anchor=T0, expires_at=T1), T2, dispatched=2)
