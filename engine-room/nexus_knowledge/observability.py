"""Knowledge observability -- derived counters over the Phase 2 sink (never authoritative).

Mirrors the runtime / validation / recovery / reflection observability facades: increments named
counters and records observations on the injected Phase 2 sink. The authoritative record of
Knowledge is the ``knowledge.*`` event log and the Item projections (doc 07/12); these counters
are a derived convenience (doc 16) and **never influence a Knowledge decision** -- acceptance,
evolution, and expiration remain pure functions of evidence and policy. A ``Null`` sink is the
zero-overhead default.
"""

from __future__ import annotations

from nexus_core.contracts.enums import ConfidenceLadder
from nexus_infra import NullObservability, Observability

CANDIDATE_RECEIVED = "knowledge.candidate_received"
CANDIDATE_ACCEPTED = "knowledge.candidate_accepted"
CANDIDATE_REJECTED = "knowledge.candidate_rejected"
ITEM_CREATED = "knowledge.item_created"
ITEM_EVOLVED = "knowledge.item_evolved"
ITEM_SUPERSEDED = "knowledge.item_superseded"
ITEM_DEPRECATED = "knowledge.item_deprecated"
ITEM_EXPIRED = "knowledge.item_expired"
ITEM_ARCHIVED = "knowledge.item_archived"
ITEM_SERVED = "knowledge.item_served"


class KnowledgeObservability:
    """Knowledge-scoped counters over the Phase 2 observability sink (no dashboards)."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def candidate_received(self) -> None:
        self._obs.increment(CANDIDATE_RECEIVED)

    def candidate_accepted(self) -> None:
        self._obs.increment(CANDIDATE_ACCEPTED)

    def candidate_rejected(self, reason: str) -> None:
        self._obs.increment(CANDIDATE_REJECTED)
        self._obs.increment(f"{CANDIDATE_REJECTED}.{reason}")

    def item_created(self, confidence: ConfidenceLadder) -> None:
        self._obs.increment(ITEM_CREATED)
        self._obs.increment(f"knowledge.confidence.{confidence.value}")

    def item_evolved(self, confidence: ConfidenceLadder) -> None:
        self._obs.increment(ITEM_EVOLVED)
        self._obs.increment(f"knowledge.confidence.{confidence.value}")

    def item_superseded(self) -> None:
        self._obs.increment(ITEM_SUPERSEDED)

    def item_deprecated(self) -> None:
        self._obs.increment(ITEM_DEPRECATED)

    def item_expired(self) -> None:
        self._obs.increment(ITEM_EXPIRED)

    def item_archived(self) -> None:
        self._obs.increment(ITEM_ARCHIVED)

    def item_served(self, count: int) -> None:
        self._obs.increment(ITEM_SERVED)
        self._obs.observe("knowledge.served_count", float(count))
