"""Step 2 — Normalization (heterogeneous fragments → one canonical representation).

The normalizer converts the raw, source-shaped fragments every collector returns
into a single canonical :class:`~nexus_context.requests.ContextItem` set. It does
**only** canonicalization: it assigns each item a deterministic identity, preserves
its category/source/value/provenance, and returns the set in a stable, sorted
order. It performs no provider-specific logic beyond this adapter step, and it does
**not** merge or drop duplicates — surfacing duplicates and contradictions is the
conflict detector's job (this stage never silently resolves anything).
"""

from __future__ import annotations

from nexus_context import ids
from nexus_context.requests import ContextItem, RawContextFragment


class Normalizer:
    """Adapts heterogeneous fragments into the canonical, deterministically ordered item set."""

    def normalize(self, fragments: tuple[RawContextFragment, ...]) -> tuple[ContextItem, ...]:
        """Map fragments to canonical items, sorted by identity for determinism."""
        items = [
            ContextItem(
                identity=ids.item_id(fragment.source.value, fragment.category.value, fragment.key),
                category=fragment.category,
                key=fragment.key,
                source=fragment.source,
                value=fragment.payload,
                observed_at=fragment.observed_at,
                references=fragment.references,
                supersedes=fragment.supersedes,
            )
            for fragment in fragments
        ]
        return tuple(sorted(items, key=lambda item: item.identity))
