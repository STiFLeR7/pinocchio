"""Knowledge persistence -- the repositories the Knowledge Engine writes through.

Knowledge reuses the **Phase 2** persistence substrate unchanged (no new mechanism, Milestone 7):
the durable Item is the frozen core :class:`~nexus_core.domain.knowledge.Knowledge` contract,
stored through the pre-built :class:`~nexus_infra.KnowledgeRepository`; the immutable version
chain and the ingested candidates are stored through the generic ``InMemoryRepository``.

- **items** -- the current Item projection per Subject Key (the newest version, folded).
- **versions** -- the append-only version records (the auditable evolution history, doc 10).
- **candidates** -- the candidates already ingested, so re-submitting one is idempotent by
  identity (INV-16) and never double-counted.

Every write is by identity and never mutates a stored object in place (objects are frozen); a new
version replaces the prior projection by Subject Key while the version chain only grows.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.domain.knowledge import Knowledge
from nexus_core.persistence.interfaces import Repository
from nexus_infra import InMemoryRepository, KnowledgeRepository, Observability
from nexus_knowledge.candidate import KnowledgeCandidate
from nexus_knowledge.model import KnowledgeVersion


@dataclass(frozen=True, slots=True)
class KnowledgeRepositories:
    """The repositories Knowledge persists its Items, versions, and candidates through."""

    items: Repository[Knowledge]
    versions: Repository[KnowledgeVersion]
    candidates: Repository[KnowledgeCandidate]


def build_knowledge_repositories(
    observability: Observability | None = None,
) -> KnowledgeRepositories:
    """Wire the default knowledge repositories over the Phase 2 substrate (reused, not modified)."""
    return KnowledgeRepositories(
        items=KnowledgeRepository(observability),
        versions=InMemoryRepository[KnowledgeVersion](
            "knowledge_version", lambda v: v.identity, observability
        ),
        candidates=InMemoryRepository[KnowledgeCandidate](
            "knowledge_candidate", lambda c: c.identity, observability
        ),
    )
