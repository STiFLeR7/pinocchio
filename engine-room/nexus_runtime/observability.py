"""Runtime observability — instrumentation only (counters/timings; no dashboards).

A thin runtime-metrics facade over the Phase 2 :class:`~nexus_infra.observability.Observability`
sink. RM's *authoritative* telemetry is the ``runtime.*`` event log (every event carries the
operation's ``correlation_identifier``, so a session timeline and its cross-subsystem trace
are reconstructable from the log — doc 15 §3, doc 16). These counters are a *derived*
convenience for operators and later Supervision; they never influence projected state
(doc 00 §3 — telemetry is never authoritative).

This module builds no dashboard and stores nothing durably; it only increments named
counters on the injected sink (defaulting to the zero-overhead null sink).
"""

from __future__ import annotations

from nexus_infra import NullObservability, Observability

REGISTERED = "runtime.registered"
DISCOVERED = "runtime.discovered"
ALLOCATED = "runtime.allocated"
SESSION_CREATED = "runtime.session_created"
SESSION_READY = "runtime.session_ready"
RELEASED = "runtime.released"
FAILED = "runtime.failed"


class RuntimeObservability:
    """Runtime-scoped counters over the Phase 2 observability sink (no dashboards)."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def registered(self) -> None:
        self._obs.increment(REGISTERED)

    def discovered(self, resolved_count: int) -> None:
        self._obs.increment(DISCOVERED)
        self._obs.observe("runtime.candidates_resolved_count", float(resolved_count))

    def session_created(self) -> None:
        self._obs.increment(SESSION_CREATED)

    def allocated(self) -> None:
        self._obs.increment(ALLOCATED)

    def session_ready(self) -> None:
        self._obs.increment(SESSION_READY)

    def released(self) -> None:
        self._obs.increment(RELEASED)

    def failed(self) -> None:
        self._obs.increment(FAILED)
