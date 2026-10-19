"""Step 4 — Relevance Ranking (deterministic, explicit rules — no AI scoring).

Each item is scored by a fixed integer rule table: a base weight per Context
Category (goal/constraint context outranks historical/workspace context for
planning), plus a weight per source class (operator/environment outranks
runtime/workspace), plus any explicit additive overrides the request supplies in
``relevance_weights`` (keyed by category *or* source value). There is no LLM, no
learned model, and no floating-point heuristic — identical inputs always produce
identical scores and identical ordering (relevance descending, then identity).
"""

from __future__ import annotations

from nexus_context.categories import ContextCategory, ContextSource
from nexus_context.requests import ContextItem, ContextRequest

# Explicit base relevance per Context Category (higher = more relevant to Planning).
_CATEGORY_BASE: dict[ContextCategory, int] = {
    ContextCategory.GOAL: 100,
    ContextCategory.CONSTRAINT: 80,
    ContextCategory.EXECUTION: 70,
    ContextCategory.OPERATIONAL: 60,
    ContextCategory.DOMAIN: 50,
    ContextCategory.RESOURCE: 40,
    ContextCategory.WORKSPACE: 30,
    ContextCategory.HISTORICAL: 20,
}

# Explicit additive weight per source class (operator intent is the most authoritative).
_SOURCE_WEIGHT: dict[ContextSource, int] = {
    ContextSource.OPERATOR: 20,
    ContextSource.ENVIRONMENT: 15,
    ContextSource.KNOWLEDGE: 10,
    ContextSource.RUNTIME: 8,
    ContextSource.WORKSPACE: 5,
}


class RelevanceRanker:
    """Assigns a deterministic integer relevance to each item and orders the set."""

    def rank(
        self, items: tuple[ContextItem, ...], request: ContextRequest
    ) -> tuple[ContextItem, ...]:
        """Return items with ``relevance`` assigned, ordered by relevance then identity."""
        overrides = request.relevance_weights
        ranked = [
            item.model_copy(update={"relevance": self._score(item, overrides)}) for item in items
        ]
        return tuple(sorted(ranked, key=lambda item: (-item.relevance, item.identity)))

    def _score(self, item: ContextItem, overrides: object) -> int:
        score = _CATEGORY_BASE[item.category] + _SOURCE_WEIGHT[item.source]
        score += self._override(overrides, item.category.value)
        score += self._override(overrides, item.source.value)
        return score

    @staticmethod
    def _override(overrides: object, name: str) -> int:
        if isinstance(overrides, dict):
            value = overrides.get(name)
            if isinstance(value, bool):
                return 0
            if isinstance(value, int):
                return value
        return 0
