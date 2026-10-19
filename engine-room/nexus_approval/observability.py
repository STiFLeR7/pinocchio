"""Approval-Exchange observability — approval-lifecycle instrumentation (INV-11; no dashboards).

Counters over the P1 sink only — derived convenience, never authoritative state. The authoritative
approval history is the durable ``approval.*`` log, projected read-only by the exchange's session / pending
/ history methods, not stored here.
"""

from __future__ import annotations

from nexus_infra import NullObservability, Observability


class ApprovalObservability:
    """Approval-lifecycle counters over the P1 sink (instrumentation only)."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def requested(self) -> None:
        self._obs.increment("approval.requested")

    def approved(self) -> None:
        self._obs.increment("approval.approved")

    def denied(self) -> None:
        self._obs.increment("approval.denied")

    def expired(self) -> None:
        self._obs.increment("approval.expired")
