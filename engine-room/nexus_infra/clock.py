"""Clock abstraction.

Timings are an *observability* concern only — they are never written into the
authoritative event payloads that projections fold, so a real wall/monotonic
clock here does not violate INV-17 (determinism of replay). The clock is an
injected interface purely so tests can make timings reproducible.
"""

from __future__ import annotations

import time
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """A monotonic source of nanosecond timestamps for instrumentation."""

    def now_ns(self) -> int: ...


class SystemClock:
    """Production clock backed by ``time.perf_counter_ns`` (monotonic)."""

    def now_ns(self) -> int:
        return time.perf_counter_ns()


class ManualClock:
    """Deterministic clock for tests: time advances only when told to."""

    def __init__(self, start_ns: int = 0) -> None:
        self._now = start_ns

    def now_ns(self) -> int:
        return self._now

    def advance(self, delta_ns: int) -> None:
        """Move the clock forward by ``delta_ns`` (must be non-negative)."""
        if delta_ns < 0:
            raise ValueError("a clock cannot move backwards")
        self._now += delta_ns
