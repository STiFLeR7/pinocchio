"""Policy observability — derived counters over the Phase 2 sink (never authoritative).

Mirrors the validation/runtime observability facades: increments named counters on the
injected Phase 2 sink. The authoritative record of an evaluation is the ``policy.*``
event log and the returned :class:`~nexus_policy.model.PolicyEvaluation`; these counters
are a derived convenience (doc 16) and never influence a decision.
"""

from __future__ import annotations

from nexus_core.contracts.enums import PolicyDecision
from nexus_infra import NullObservability, Observability

EVALUATED = "policy.evaluated"
DEFAULT_APPLIED = "policy.default_applied"
REGISTERED = "policy.registered"


class PolicyObservability:
    """Policy-scoped counters over the Phase 2 observability sink (no dashboards)."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def evaluated(self, decision: PolicyDecision) -> None:
        self._obs.increment(EVALUATED)
        self._obs.increment(f"policy.decision.{decision.value}")

    def default_applied(self) -> None:
        self._obs.increment(DEFAULT_APPLIED)

    def registered(self) -> None:
        self._obs.increment(REGISTERED)
