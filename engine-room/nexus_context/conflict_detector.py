"""Step 3 — Conflict Detection (identify, surface, never silently resolve).

The detector inspects the normalized item set and reports four kinds of conflict
(:class:`~nexus_context.categories.ConflictKind`):

- **duplicate** — the same ``(category, key)`` reported by more than one source with
  the *same* value.
- **contradiction** — the same ``(category, key)`` reported with *differing* values.
- **stale** — an item another item explicitly ``supersedes``.
- **missing_dependency** — a ``declared_dependency`` key with no item present.

Every conflict is returned for the package to surface (in ``known_unknowns`` /
``validation_status``). The detector resolves nothing — surfacing, not silent
correction, is the contract (doc 03 *Context Validation*).
"""

from __future__ import annotations

from nexus_context.categories import ConflictKind, ContextCategory
from nexus_context.requests import Conflict, ContextItem, ContextRequest


class ConflictDetector:
    """Surfaces duplicate, contradictory, stale, and missing-dependency conflicts."""

    def detect(
        self, items: tuple[ContextItem, ...], request: ContextRequest
    ) -> tuple[Conflict, ...]:
        """Return all surfaced conflicts in a deterministic order."""
        conflicts: list[Conflict] = []
        conflicts.extend(self._value_conflicts(items))
        conflicts.extend(self._stale_conflicts(items))
        conflicts.extend(self._missing_dependencies(items, request))
        return tuple(
            sorted(
                conflicts,
                key=lambda c: (c.kind.value, c.category.value if c.category else "", c.key),
            )
        )

    def _value_conflicts(self, items: tuple[ContextItem, ...]) -> list[Conflict]:
        groups: dict[tuple[ContextCategory, str], list[ContextItem]] = {}
        for item in items:
            groups.setdefault((item.category, item.key), []).append(item)
        conflicts: list[Conflict] = []
        for (category, key), grouped in groups.items():
            if len(grouped) < 2:
                continue
            refs = tuple(sorted(member.identity for member in grouped))
            sources = sorted({member.source.value for member in grouped})
            values = [member.value for member in grouped]
            identical = all(value == values[0] for value in values)
            kind = ConflictKind.DUPLICATE if identical else ConflictKind.CONTRADICTION
            conflicts.append(
                Conflict(
                    kind=kind,
                    category=category,
                    key=key,
                    item_refs=refs,
                    detail={"sources": sources},
                )
            )
        return conflicts

    def _stale_conflicts(self, items: tuple[ContextItem, ...]) -> list[Conflict]:
        by_key: dict[str, ContextItem] = {item.key: item for item in items}
        conflicts: list[Conflict] = []
        for item in items:
            for superseded_key in item.supersedes:
                superseded = by_key.get(superseded_key)
                if superseded is None:
                    continue
                conflicts.append(
                    Conflict(
                        kind=ConflictKind.STALE,
                        category=superseded.category,
                        key=superseded_key,
                        item_refs=tuple(sorted((item.identity, superseded.identity))),
                        detail={"superseded_by": item.identity},
                    )
                )
        return conflicts

    def _missing_dependencies(
        self, items: tuple[ContextItem, ...], request: ContextRequest
    ) -> list[Conflict]:
        present = {item.key for item in items}
        conflicts: list[Conflict] = []
        for dependency in request.declared_dependencies:
            if dependency not in present:
                conflicts.append(
                    Conflict(
                        kind=ConflictKind.MISSING_DEPENDENCY,
                        category=None,
                        key=dependency,
                        item_refs=(),
                        detail={"reason": "declared dependency has no context item"},
                    )
                )
        return conflicts
