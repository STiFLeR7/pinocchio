"""Validation observability — derived counters over the Phase 2 sink (never authoritative).

Mirrors the runtime/execution observability facades: increments named counters on the
injected Phase 2 sink. The authoritative record of a validation is the ``validation.*``
event log and the Report; these counters are a derived convenience (doc 16) and never
influence the verdict.
"""

from __future__ import annotations

from nexus_infra import NullObservability, Observability

STARTED = "validation.started"
EVIDENCE_COLLECTED = "validation.evidence_collected"
RULE_EVALUATED = "validation.rule_evaluated"
COMPLETED = "validation.completed"
FAILED = "validation.failed"


class ValidationObservability:
    """Validation-scoped counters over the Phase 2 observability sink (no dashboards)."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def started(self) -> None:
        self._obs.increment(STARTED)

    def evidence_collected(self, count: int) -> None:
        self._obs.increment(EVIDENCE_COLLECTED)
        self._obs.observe("validation.evidence_count", float(count))

    def rule_evaluated(self) -> None:
        self._obs.increment(RULE_EVALUATED)

    def completed(self) -> None:
        self._obs.increment(COMPLETED)

    def failed(self) -> None:
        self._obs.increment(FAILED)
