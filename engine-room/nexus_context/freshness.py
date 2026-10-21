"""Step 5 — Freshness Validation (valid / stale / expired via timestamps + policy).

Each item carrying an ``observed_at`` instant is aged against the policy's explicit
``evaluation_instant`` (never the wall clock, so the verdict is reproducible) and
the applicable ``max_age`` (per-category override, else the policy default):

- age <= ``max_age``                  -> **valid**
- ``max_age`` < age <= 2x ``max_age``  -> **stale**
- age > 2x ``max_age``                 -> **expired**

An item with no timestamp, no evaluation instant, or no applicable threshold is
left **unknown** / **valid** rather than guessed — freshness is measured, never
inferred. A future-dated observation is treated as valid (clock skew, not decay).
"""

from __future__ import annotations

from datetime import datetime

from nexus_context.categories import FreshnessState
from nexus_context.requests import ContextItem, FreshnessPolicy


class FreshnessValidator:
    """Assigns a deterministic freshness verdict to each item from timestamps + policy."""

    def evaluate(
        self, items: tuple[ContextItem, ...], policy: FreshnessPolicy
    ) -> tuple[ContextItem, ...]:
        """Return items with ``freshness`` assigned per the policy."""
        return tuple(
            item.model_copy(update={"freshness": self._verdict(item, policy)}) for item in items
        )

    def _verdict(self, item: ContextItem, policy: FreshnessPolicy) -> FreshnessState:
        if item.observed_at is None or policy.evaluation_instant is None:
            return FreshnessState.UNKNOWN
        age = self._age_seconds(policy.evaluation_instant, item.observed_at)
        if age is None:
            return FreshnessState.UNKNOWN
        if age < 0:
            return FreshnessState.VALID
        max_age = self._max_age(item.category.value, policy)
        if max_age is None:
            return FreshnessState.VALID
        if age <= max_age:
            return FreshnessState.VALID
        if age <= 2 * max_age:
            return FreshnessState.STALE
        return FreshnessState.EXPIRED

    @staticmethod
    def _age_seconds(evaluation_instant: str, observed_at: str) -> float | None:
        try:
            evaluated = datetime.fromisoformat(evaluation_instant)
            observed = datetime.fromisoformat(observed_at)
            return (evaluated - observed).total_seconds()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _max_age(category: str, policy: FreshnessPolicy) -> int | None:
        override = policy.by_category.get(category)
        if isinstance(override, bool):
            override = None
        if isinstance(override, int):
            return override
        return policy.default_max_age_seconds
