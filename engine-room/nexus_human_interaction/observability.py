"""Human-Interaction observability — operator-session instrumentation (INV-11; no dashboards).

Counters over the P1 sink only — derived convenience, never authoritative state. The operator-facing
metadata (pipeline progress, stage timing, execution lineage, Knowledge provenance, session state) is
projected read-only by the façade's status / lineage / explain methods, not stored here.
"""

from __future__ import annotations

from nexus_infra import NullObservability, Observability


class OperatorObservability:
    """Interaction counters over the P1 sink (instrumentation only)."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def submitted(self) -> None:
        self._obs.increment("interaction.submitted")

    def resumed(self) -> None:
        self._obs.increment("interaction.resumed")

    def responded(self, *, stages: int) -> None:
        self._obs.increment("interaction.responded")
        self._obs.observe("interaction.stages_completed", float(stages))
