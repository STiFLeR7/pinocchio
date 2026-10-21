"""Recovery observability — derived counters over the Phase 2 sink (never authoritative).

Mirrors the runtime/execution/validation observability facades: increments named counters on
the injected Phase 2 sink. The authoritative record of a recovery decision is the
``recovery.*`` event log and the Recovery Plan; these counters are a derived convenience
(doc 16) and never influence the decision.
"""

from __future__ import annotations

from nexus_infra import NullObservability, Observability

STARTED = "recovery.started"
RULE_EVALUATED = "recovery.rule_evaluated"
DECISION_CREATED = "recovery.decision_created"
COMPLETED = "recovery.completed"
FAILED = "recovery.failed"


class RecoveryObservability:
    """Recovery-scoped counters over the Phase 2 observability sink (no dashboards)."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def started(self) -> None:
        self._obs.increment(STARTED)

    def rule_evaluated(self) -> None:
        self._obs.increment(RULE_EVALUATED)

    def decision_created(self, decision: str) -> None:
        self._obs.increment(DECISION_CREATED)
        self._obs.increment(f"recovery.decision.{decision}")

    def completed(self) -> None:
        self._obs.increment(COMPLETED)

    def failed(self) -> None:
        self._obs.increment(FAILED)
