"""Step 6 — Context Package Builder (immutable, deterministic packaging).

The final stage assembles the ranked, freshness-evaluated item set into a frozen
:class:`~nexus_core.domain.context_package.ContextPackage` conforming to the frozen
contract. It routes each item into one of the eight canonical Context Categories,
derives confidence from an explicit rule, merges the Goal's and request's
constraints, and surfaces every gap and conflict in ``known_unknowns`` /
``validation_status`` rather than hiding it.

It never plans, selects a runtime, executes, or builds the procedural side of work
— it produces *understanding*, by reference, and stops (doc 03 *Architectural
Boundaries*; preserves INV-03/INV-08 at the context seam).
"""

from __future__ import annotations

from nexus_context import ids
from nexus_context.categories import ConflictKind, ContextCategory
from nexus_context.requests import Conflict, ContextItem, ContextRequest
from nexus_core.contracts.base import Constraint, Correlation, Reference, Struct
from nexus_core.contracts.enums import InterpretationConfidence
from nexus_core.domain.context_package import ContextCategories, ContextPackage
from nexus_core.domain.goal import Goal


class ContextPackageBuilder:
    """Packages the assembled item set into an immutable Context Package."""

    def build(
        self,
        goal: Goal,
        items: tuple[ContextItem, ...],
        conflicts: tuple[Conflict, ...],
        request: ContextRequest,
        validation_status: Struct,
        *,
        correlation_identifier: str,
    ) -> ContextPackage:
        """Assemble the deterministic Context Package for ``goal``."""
        return ContextPackage(
            identity=ids.context_id(goal.identity, request.package_version),
            goal_ref=Reference(target_type="goal", identifier=goal.identity),
            correlation=Correlation(correlation_identifier=correlation_identifier),
            context_categories=self._categories(items),
            constraints=self._constraints(goal, request),
            resources=self._dedup_refs(request.resources),
            confidence=self._confidence(items, conflicts),
            validation_status=validation_status,
            supporting_artifacts=self._dedup_refs(request.supporting_artifacts),
            references=self._references(items, request),
            known_unknowns=self._known_unknowns(conflicts, request),
            freshness=self._freshness_summary(items, request),
            source=self._source_summary(items),
        )

    # -- category assembly --------------------------------------------------- #

    def _categories(self, items: tuple[ContextItem, ...]) -> ContextCategories:
        buckets: dict[ContextCategory, dict[str, object]] = {}
        for item in items:
            bucket = buckets.setdefault(item.category, {})
            bucket[item.key] = {
                "value": dict(item.value),
                "source": item.source.value,
                "relevance": item.relevance,
                "freshness": item.freshness.value,
                "observed_at": item.observed_at,
                "references": list(item.references),
            }
        sorted_buckets = {
            category: dict(sorted(bucket.items())) for category, bucket in buckets.items()
        }
        return ContextCategories(
            goal_context=sorted_buckets.get(ContextCategory.GOAL, {}),
            domain_context=sorted_buckets.get(ContextCategory.DOMAIN, {}),
            workspace_context=sorted_buckets.get(ContextCategory.WORKSPACE, {}),
            historical_context=sorted_buckets.get(ContextCategory.HISTORICAL, {}),
            operational_context=sorted_buckets.get(ContextCategory.OPERATIONAL, {}),
            constraint_context=sorted_buckets.get(ContextCategory.CONSTRAINT, {}),
            resource_context=sorted_buckets.get(ContextCategory.RESOURCE, {}),
            execution_context=sorted_buckets.get(ContextCategory.EXECUTION, {}),
        )

    # -- derived fields ------------------------------------------------------ #

    @staticmethod
    def _confidence(
        items: tuple[ContextItem, ...], conflicts: tuple[Conflict, ...]
    ) -> InterpretationConfidence:
        if not items:
            return InterpretationConfidence.UNKNOWN
        kinds = {conflict.kind for conflict in conflicts}
        if ConflictKind.CONTRADICTION in kinds or ConflictKind.MISSING_DEPENDENCY in kinds:
            return InterpretationConfidence.LOW
        categories = {item.category for item in items}
        if ContextCategory.GOAL in categories and len(categories) >= 2:
            return InterpretationConfidence.HIGH
        return InterpretationConfidence.MEDIUM

    @staticmethod
    def _constraints(goal: Goal, request: ContextRequest) -> tuple[Constraint, ...]:
        merged: list[Constraint] = []
        for constraint in (*goal.constraints, *request.constraints):
            if constraint not in merged:
                merged.append(constraint)
        return tuple(merged)

    @staticmethod
    def _dedup_refs(refs: tuple[Reference, ...]) -> tuple[Reference, ...]:
        seen: set[tuple[str, str]] = set()
        unique: list[Reference] = []
        for ref in refs:
            signature = (ref.target_type, ref.identifier)
            if signature not in seen:
                seen.add(signature)
                unique.append(ref)
        return tuple(unique)

    @staticmethod
    def _references(items: tuple[ContextItem, ...], request: ContextRequest) -> tuple[str, ...]:
        collected = set(request.references)
        for item in items:
            collected.update(item.references)
        return tuple(sorted(collected))

    @staticmethod
    def _known_unknowns(
        conflicts: tuple[Conflict, ...], request: ContextRequest
    ) -> tuple[str, ...]:
        gaps = set(request.known_unknowns)
        for conflict in conflicts:
            if conflict.kind in {
                ConflictKind.MISSING_DEPENDENCY,
                ConflictKind.CONTRADICTION,
                ConflictKind.STALE,
            }:
                gaps.add(f"{conflict.kind.value}:{conflict.key}")
        return tuple(sorted(gaps))

    @staticmethod
    def _freshness_summary(items: tuple[ContextItem, ...], request: ContextRequest) -> Struct:
        counts: dict[str, int] = {}
        for item in items:
            counts[item.freshness.value] = counts.get(item.freshness.value, 0) + 1
        return {
            "evaluation_instant": request.freshness_policy.evaluation_instant,
            "counts": dict(sorted(counts.items())),
        }

    @staticmethod
    def _source_summary(items: tuple[ContextItem, ...]) -> Struct:
        return {
            "sources": sorted({item.source.value for item in items}),
            "categories": sorted({item.category.value for item in items}),
            "item_count": len(items),
        }
