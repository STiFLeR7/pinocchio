"""Operations-Plane observability — plane instrumentation (INV-11; no dashboards).

Counters over the P1 sink only — derived convenience, never authoritative state. The operational views
(sessions, queues, inventories, health) are projected read-only by the services, not stored here.
"""

from __future__ import annotations

from nexus_infra import NullObservability, Observability


class OperationsObservability:
    """Operations-plane counters over the P1 sink (instrumentation only)."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def inspected(self) -> None:
        self._obs.increment("operations.inspected")

    def snapshot(self) -> None:
        self._obs.increment("operations.snapshot")
