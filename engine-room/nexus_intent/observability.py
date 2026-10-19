"""Intent observability — derived counters over the P1 sink (never authoritative).

Mirrors the policy/estimation/engineering facades. The authoritative record of a resolution is the
``intent.*`` event log and the returned :class:`~nexus_intent.model.IntentAnalysis`; these counters
are a derived convenience and never influence the understanding.
"""

from __future__ import annotations

from nexus_infra import NullObservability, Observability


class IntentObservability:
    """Intent-scoped counters over the P1 observability sink."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def resolved(self, *, resolved: bool, confidence: str, clarifications: int) -> None:
        self._obs.increment("intent.resolved" if resolved else "intent.awaiting_clarification")
        self._obs.increment(f"intent.confidence.{confidence}")
        if clarifications:
            self._obs.increment("intent.clarification_requested")
