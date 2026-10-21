"""Scheduler observability — timing + autonomy instrumentation (INV-11; no dashboards).

Counters over the P1 sink only — derived convenience, never authoritative state. The authoritative
schedule state is the durable ``scheduler.*`` log, projected read-only by the Scheduler's read methods.
"""

from __future__ import annotations

from nexus_infra import NullObservability, Observability


class SchedulerObservability:
    """Scheduler counters over the P1 sink (instrumentation only)."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def registered(self) -> None:
        self._obs.increment("scheduler.registered")

    def dispatched(self) -> None:
        self._obs.increment("scheduler.dispatched")

    def denied(self) -> None:
        self._obs.increment("scheduler.dispatch_denied")

    def requested(self) -> None:
        self._obs.increment("scheduler.dispatch_requested")

    def operation_ran(self) -> None:
        self._obs.increment("scheduler.operation_ran")
