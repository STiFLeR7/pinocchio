"""Estimation observability — derived counters over the Phase 2 sink (never authoritative).

Mirrors the policy/validation facades. The authoritative record of an estimation is the
``estimation.*`` event log and the returned :class:`~nexus_estimation.model.EstimationReport`;
these counters are a derived convenience and never influence an estimate.
"""

from __future__ import annotations

from nexus_estimation.vocabulary import ComplexityBand, ConfidenceBand
from nexus_infra import NullObservability, Observability


class EstimationObservability:
    """Estimation-scoped counters over the Phase 2 observability sink."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def estimated(self, complexity: ComplexityBand, confidence: ConfidenceBand) -> None:
        self._obs.increment("estimation.estimated")
        self._obs.increment(f"estimation.complexity.{complexity.value}")
        self._obs.increment(f"estimation.confidence.{confidence.value}")
