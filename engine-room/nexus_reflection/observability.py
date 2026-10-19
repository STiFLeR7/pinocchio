"""Reflection observability — derived counters over the Phase 2 sink (never authoritative).

Mirrors the runtime/execution/validation/recovery observability facades: increments named
counters on the injected Phase 2 sink. The authoritative record of a reflection is the
``reflection.*`` event log and the Reflection Report; these counters are a derived convenience
(doc 16) and never influence the analysis.
"""

from __future__ import annotations

from nexus_infra import NullObservability, Observability

STARTED = "reflection.started"
ANALYSIS_COMPLETED = "reflection.analysis_completed"
REPORT_CREATED = "reflection.report_created"
COMPLETED = "reflection.completed"
FAILED = "reflection.failed"


class ReflectionObservability:
    """Reflection-scoped counters over the Phase 2 observability sink (no dashboards)."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def started(self) -> None:
        self._obs.increment(STARTED)

    def analysis_completed(self, patterns: int) -> None:
        self._obs.increment(ANALYSIS_COMPLETED)
        self._obs.observe("reflection.pattern_count", float(patterns))

    def report_created(self) -> None:
        self._obs.increment(REPORT_CREATED)

    def completed(self) -> None:
        self._obs.increment(COMPLETED)

    def failed(self) -> None:
        self._obs.increment(FAILED)
