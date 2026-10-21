"""Execution observability — derived counters over the Phase 2 sink (never authoritative).

Mirrors :class:`nexus_runtime.observability.RuntimeObservability`: a thin facade that
increments named counters on the injected Phase 2 sink. The authoritative record of a run
is the ``runtime.*`` event log (doc 15); these counters are a derived convenience for
operators and later Supervision (doc 16) and never influence projected state (doc 00 §3).
"""

from __future__ import annotations

from nexus_infra import NullObservability, Observability

STARTED = "execution.started"
OUTPUT = "execution.output"
PROGRESS = "execution.progress"
ARTIFACT = "execution.artifact_emitted"
TIMED_OUT = "execution.timed_out"
COMPLETED = "execution.completed"
CANCELLED = "execution.cancelled"
FAILED = "execution.failed"
DESTROYED = "execution.destroyed"


class ExecutionObservability:
    """Execution-scoped counters over the Phase 2 observability sink (no dashboards)."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def started(self) -> None:
        self._obs.increment(STARTED)

    def output(self, length: int) -> None:
        self._obs.increment(OUTPUT)
        self._obs.observe("execution.output_length", float(length))

    def progress(self) -> None:
        self._obs.increment(PROGRESS)

    def artifact(self) -> None:
        self._obs.increment(ARTIFACT)

    def timed_out(self) -> None:
        self._obs.increment(TIMED_OUT)

    def completed(self) -> None:
        self._obs.increment(COMPLETED)

    def cancelled(self) -> None:
        self._obs.increment(CANCELLED)

    def failed(self) -> None:
        self._obs.increment(FAILED)

    def destroyed(self) -> None:
        self._obs.increment(DESTROYED)
