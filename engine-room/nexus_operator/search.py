"""Operational Search — deterministic keyword search over persisted state (Milestone 4).

Search reuses the existing repositories and the explorer's read-only views; it is a plain
case-insensitive substring match over stable text fields — **no vector search, no embeddings**.
Results are fully deterministic: the same query over the same state always returns the same hits in
the same order (grouped by domain, then by identifier).

Searchable domains: Goals, Knowledge, Briefings, and Validation Reports.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from nexus_knowledge.persistence import KnowledgeRepositories
from nexus_operator.explorer import OperationalExplorer
from nexus_operator.history import SessionHistory


class SearchDomain(enum.StrEnum):
    """The persisted domains operator search covers."""

    GOAL = "goal"
    KNOWLEDGE = "knowledge"
    BRIEFING = "briefing"
    VALIDATION = "validation"


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One deterministic search match."""

    domain: SearchDomain
    identifier: str
    title: str
    snippet: str


@dataclass(frozen=True, slots=True)
class SearchResults:
    """The immutable, ordered results of one query."""

    query: str
    hits: tuple[SearchHit, ...]

    def __len__(self) -> int:
        return len(self.hits)

    def in_domain(self, domain: SearchDomain) -> tuple[SearchHit, ...]:
        """Only the hits in ``domain``."""
        return tuple(hit for hit in self.hits if hit.domain is domain)

    @property
    def identifiers(self) -> tuple[str, ...]:
        """Every matched identifier, in result order."""
        return tuple(hit.identifier for hit in self.hits)


def _matches(needle: str, *fields: str) -> bool:
    return any(needle in field.lower() for field in fields)


def search(
    query: str,
    *,
    history: SessionHistory,
    knowledge: KnowledgeRepositories | None = None,
) -> SearchResults:
    """Deterministically search Goals, Knowledge, Briefings, and Validation Reports for ``query``."""
    needle = query.strip().lower()
    if not needle:
        return SearchResults(query=query, hits=())

    explorer = OperationalExplorer(history, knowledge)
    hits: list[SearchHit] = []

    for goal in explorer.goals():
        if _matches(needle, goal.goal_id, goal.outcome):
            hits.append(SearchHit(SearchDomain.GOAL, goal.goal_id, goal.outcome, goal.status))
    for item in explorer.knowledge_items():
        if _matches(needle, item.identity, item.understanding):
            hits.append(
                SearchHit(SearchDomain.KNOWLEDGE, item.identity, item.type, item.understanding)
            )
    for briefing in explorer.briefings():
        if _matches(needle, briefing.title, briefing.brief_type):
            hits.append(
                SearchHit(
                    SearchDomain.BRIEFING,
                    briefing.submission_id,
                    briefing.title,
                    briefing.brief_type,
                )
            )
    for report in explorer.validation_reports():
        if _matches(needle, report.work_package_id, report.decision):
            hits.append(
                SearchHit(
                    SearchDomain.VALIDATION,
                    report.work_package_id,
                    report.decision,
                    report.decision,
                )
            )

    ordered = tuple(sorted(hits, key=lambda h: (h.domain.value, h.identifier)))
    return SearchResults(query=query, hits=ordered)
