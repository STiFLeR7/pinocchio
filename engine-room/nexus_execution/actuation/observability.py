"""Execution-actuation observability — deterministic instrumentation over the P1 sink.

Exposes execution-traversal metadata (node timing/completion, queue depth, active runtimes, checkpoint
history) as counters over the incumbent Observability sink. It is instrumentation only — it never
produces :mod:`observation.md` Observations (that is Supervision's, INV-11) and never controls
execution (INV-23). Derived and convenient, never authoritative — the Event Log is (INV-13).
"""

from __future__ import annotations

from nexus_infra import NullObservability, Observability


class ActuationObservability:
    """Traversal counters over the P1 observability sink (derived convenience, never authoritative)."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def started(self, *, nodes: int) -> None:
        self._obs.increment("execution.actuation_started")
        self._obs.observe("execution.graph_node_count", float(nodes))

    def wave(self, *, ready: int) -> None:
        self._obs.increment("execution.wave")
        self._obs.observe("execution.wave_ready_depth", float(ready))

    def node_completed(self) -> None:
        self._obs.increment("execution.node_completed")

    def node_failed(self) -> None:
        self._obs.increment("execution.node_failed")

    def checkpoint(self) -> None:
        self._obs.increment("execution.checkpoint")

    def approval_waiting(self) -> None:
        self._obs.increment("execution.approval_waiting")

    def completed(self, *, completed: int, waves: int) -> None:
        self._obs.increment("execution.actuation_completed")
        self._obs.observe("execution.completed_node_count", float(completed))
        self._obs.observe("execution.wave_count", float(waves))
