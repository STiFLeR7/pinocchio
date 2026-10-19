"""Knowledge retrieval -- the read-only serve contract for consumers (doc 09).

Consumption is where accumulated understanding influences future work, and it is deliberately
constrained: consumers **read, never write**, and they reach learning **only through Knowledge**,
never through Reflection (INV-26). A retrieval is a ``query -> immutable views`` function over the
Item projections; it never changes Knowledge state.

- **Read-only.** Returned Items are the frozen core ``Knowledge`` value objects, referencing
  artifacts/evidence by id (INV-27); a consumer cannot accept, evolve, deprecate, or expire.
- **Current by default.** Only ``Active`` Items (``Current`` and above the serving floor) are
  returned unless ``include_historical`` is set for audit (doc 06/11).
- **Confidence-aware / deterministic.** The same query against the same state returns the same
  views, in insertion order (INV-16 stable ordering).
"""

from __future__ import annotations

from nexus_core.contracts.base import Struct, ValueObject
from nexus_core.contracts.enums import ConfidenceLadder, Domain, KnowledgeType
from nexus_core.domain.knowledge import Knowledge
from nexus_core.persistence.interfaces import Repository
from nexus_knowledge import ids
from nexus_knowledge.lifecycle import is_served
from nexus_knowledge.observability import KnowledgeObservability
from nexus_knowledge.policy import PersistencePolicy, at_least


class KnowledgeQuery(ValueObject):
    """An immutable read-only retrieval request (doc 09)."""

    subject: str | None = None
    kind: KnowledgeType | None = None
    subject_key: str | None = None
    confidence_floor: ConfidenceLadder | None = None
    include_historical: bool = False
    limit: int | None = None
    domain: Domain | None = None
    applicability: Struct | None = None


class KnowledgeRetrieval:
    """The deterministic, side-effect-free serve operation over the Item projections (doc 09)."""

    def __init__(
        self,
        items: Repository[Knowledge],
        policy: PersistencePolicy,
        observability: KnowledgeObservability | None = None,
    ) -> None:
        self._items = items
        self._policy = policy
        self._obs = observability or KnowledgeObservability()

    def resolve(self, query: KnowledgeQuery) -> tuple[Knowledge, ...]:
        """Return the immutable Items matching ``query`` (Active by default), deterministically."""
        matched = [item for item in self._items.list_all() if self._matches(query, item)]
        if query.limit is not None:
            matched = matched[: query.limit]
        result = tuple(matched)
        self._obs.item_served(len(result))
        return result

    def _matches(self, query: KnowledgeQuery, item: Knowledge) -> bool:
        if not query.include_historical and not is_served(item, self._policy):
            return False
        if query.subject_key is not None and item.identity != query.subject_key:
            return False
        if query.kind is not None and item.type is not query.kind:
            return False
        if query.domain is not None and item.domain is not query.domain:
            return False
        if query.applicability is not None and (
            item.applicability is None
            or any(
                item.applicability.get(key) != value for key, value in query.applicability.items()
            )
        ):
            return False
        if query.subject is not None and ids.subject_key(item.type, query.subject) != item.identity:
            return False
        return not (
            query.confidence_floor is not None
            and not at_least(item.confidence, query.confidence_floor)
        )
