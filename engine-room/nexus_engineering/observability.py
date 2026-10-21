"""Engineering observability — derived counters over the P1 sink (never authoritative).

Mirrors the policy/estimation facades. The authoritative record of a reasoning act is the
``engineering.*`` event log and the returned :class:`~nexus_engineering.model.EngineeringStrategy`;
these counters are a derived convenience and never influence the reasoning.
"""

from __future__ import annotations

from nexus_infra import NullObservability, Observability


class EngineeringObservability:
    """Engineering-scoped counters over the P1 observability sink."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def strategized(self, classification: str, autonomy: str, risk: str) -> None:
        self._obs.increment("engineering.strategized")
        self._obs.increment(f"engineering.classification.{classification}")
        self._obs.increment(f"engineering.autonomy.{autonomy}")
        self._obs.increment(f"engineering.risk.{risk}")
