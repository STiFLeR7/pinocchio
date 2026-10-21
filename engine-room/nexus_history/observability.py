"""Execution-history observability — derived counters over the P1 sink (never authoritative).

Mirrors the repository/estimation/engineering facades. The authoritative record of a projection is
the ``execution_history.*`` event log and the returned
:class:`~nexus_history.model.ExecutionHistoryProfile`; these counters are a derived convenience and
never influence the profile.
"""

from __future__ import annotations

from nexus_infra import NullObservability, Observability


class HistoryObservability:
    """Execution-history-scoped counters over the P1 observability sink."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def projected(self, *, scope: str, event_count: int, execution_count: int) -> None:
        self._obs.increment("execution_history.projected")
        self._obs.increment(f"execution_history.scope.{scope.split('|', 1)[0].split(':', 1)[0]}")
        self._obs.observe("execution_history.event_count", float(event_count))
        self._obs.observe("execution_history.execution_count", float(execution_count))
