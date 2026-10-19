"""Migration observability — derived telemetry over the Phase 2 sink (never authoritative).

Mirrors the policy/validation facades: increments named counters on the injected sink.
The authoritative record of a migration is the append-only ``migration.*`` event log; these
counters are a derived convenience (migration telemetry / shadow diff dashboard input) and
never influence routing.
"""

from __future__ import annotations

from nexus_infra import NullObservability, Observability
from nexus_integration.model import Authority, DiffVerdict, FlagState


class MigrationObservability:
    """Migration-scoped counters over the Phase 2 observability sink."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def decision_recorded(self, owner: str) -> None:
        self._obs.increment("migration.decision_recorded")
        self._obs.increment(f"migration.owner.{owner}.recorded")

    def shadow_decision(self, owner: str) -> None:
        self._obs.increment("migration.shadow_decision")

    def diff(self, verdict: DiffVerdict) -> None:
        self._obs.increment("migration.diff")
        self._obs.increment(f"migration.diff.{verdict.value}")

    def routed(self, authority: Authority) -> None:
        self._obs.increment(f"migration.authoritative.{authority.value}")

    def flag_set(self, owner: str, state: FlagState) -> None:
        self._obs.increment("migration.flag_set")
        self._obs.increment(f"migration.flag.{state.value}")

    def rolled_back(self, owner: str) -> None:
        self._obs.increment("migration.rollback")
