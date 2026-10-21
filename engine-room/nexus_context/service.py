"""The Context Engineering Service — orchestrates the context pipeline.

Receives a Goal and a deterministic :class:`ContextRequest`, drives the pipeline
(collect → normalize → detect conflicts → rank → validate freshness → package),
persists the result through a Phase 2 repository, emits context events to the log,
and returns an immutable :class:`ContextResult`.

It coordinates only. It never plans, selects a runtime, executes, validates
execution, invokes an AI provider, or mutates Knowledge (doc 03 *Architectural
Boundaries*). A failure emits a ``context_engineering.failed`` event and raises.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from nexus_context import events, ids
from nexus_context.builder import ContextPackageBuilder
from nexus_context.collectors import ContextCollector
from nexus_context.conflict_detector import ConflictDetector
from nexus_context.events import SystemTimestampSource, TimestampSource
from nexus_context.freshness import FreshnessValidator
from nexus_context.normalizer import Normalizer
from nexus_context.relevance import RelevanceRanker
from nexus_context.requests import (
    Conflict,
    ContextItem,
    ContextRequest,
    ContextResult,
    RawContextFragment,
)
from nexus_context.validators import (
    ContextError,
    compute_validation_status,
    validate_goal,
    validate_outputs,
    validate_request,
)
from nexus_core.contracts.base import Struct
from nexus_core.domain.context_package import ContextPackage
from nexus_core.domain.goal import Goal
from nexus_core.events.interfaces import EventEmitter
from nexus_core.persistence.interfaces import Repository


@dataclass(frozen=True, slots=True)
class ContextRepositories:
    """The repository Context Engineering persists through (Phase 2 mechanism, reused)."""

    context_packages: Repository[ContextPackage]


class ContextEngineeringService:
    """Coordinates one context cycle from Goal to persisted, emitted Context Package."""

    def __init__(
        self,
        repositories: ContextRepositories,
        collectors: Iterable[ContextCollector],
        emitter: EventEmitter,
        *,
        normalizer: Normalizer | None = None,
        conflict_detector: ConflictDetector | None = None,
        ranker: RelevanceRanker | None = None,
        freshness: FreshnessValidator | None = None,
        builder: ContextPackageBuilder | None = None,
        timestamps: TimestampSource | None = None,
    ) -> None:
        self._repos = repositories
        self._collectors = tuple(collectors)
        self._emitter = emitter
        self._normalizer = normalizer or Normalizer()
        self._conflicts = conflict_detector or ConflictDetector()
        self._ranker = ranker or RelevanceRanker()
        self._freshness = freshness or FreshnessValidator()
        self._builder = builder or ContextPackageBuilder()
        self._timestamps = timestamps or SystemTimestampSource()

    def engineer(self, goal: Goal, request: ContextRequest) -> ContextResult:
        """Produce, persist, and announce a complete Context Package for ``goal``."""
        correlation = self._correlation(goal, request)
        context_identity = ids.context_id(goal.identity, request.package_version)
        try:
            validate_goal(goal)
            validate_request(request)
            self._emit(
                context_identity,
                events.CONTEXT_COLLECTION_STARTED,
                "started",
                0,
                correlation,
                {"goal": goal.identity, "collectors": len(self._collectors)},
            )
            fragments = self._collect(goal, request)
            self._emit(
                context_identity,
                events.CONTEXT_COLLECTED,
                "collected",
                1,
                correlation,
                {"goal": goal.identity, "fragments": len(fragments)},
            )
            items = self._normalizer.normalize(fragments)
            conflicts = self._conflicts.detect(items, request)
            items = self._ranker.rank(items, request)
            items = self._freshness.evaluate(items, request.freshness_policy)
            validation_status = compute_validation_status(items, conflicts)
            self._emit(
                context_identity,
                events.CONTEXT_VALIDATED,
                "validated",
                2,
                correlation,
                {
                    "context": context_identity,
                    "items": len(items),
                    "conflicts": len(conflicts),
                    "fit_for_planning": validation_status["fit_for_planning"],
                },
            )
            package = self._builder.build(
                goal,
                items,
                conflicts,
                request,
                validation_status,
                correlation_identifier=correlation,
            )
            validate_outputs(package, goal)
        except ContextError as exc:
            self._emit_failed(context_identity, goal, correlation, exc)
            raise
        self._persist(package)
        self._emit_success(context_identity, goal, package, items, conflicts, correlation)
        return ContextResult(package=package, items=items, conflicts=conflicts)

    # -- pipeline ------------------------------------------------------------ #

    def _collect(self, goal: Goal, request: ContextRequest) -> tuple[RawContextFragment, ...]:
        gathered: list[RawContextFragment] = []
        for collector in self._collectors:
            gathered.extend(collector.collect(goal, request))
        return tuple(gathered)

    # -- persistence --------------------------------------------------------- #

    def _persist(self, package: ContextPackage) -> None:
        self._repos.context_packages.add(package)

    # -- events -------------------------------------------------------------- #

    def _emit_success(
        self,
        context_identity: str,
        goal: Goal,
        package: ContextPackage,
        items: tuple[ContextItem, ...],
        conflicts: tuple[Conflict, ...],
        correlation: str,
    ) -> None:
        self._emit(
            context_identity,
            events.CONTEXT_PACKAGE_CREATED,
            "package",
            3,
            correlation,
            {
                "context": package.identity,
                "goal": goal.identity,
                "confidence": package.confidence.value,
            },
        )
        self._emit(
            context_identity,
            events.CONTEXT_ENGINEERING_COMPLETED,
            "completed",
            4,
            correlation,
            {
                "context": package.identity,
                "item_count": len(items),
                "conflict_count": len(conflicts),
                "fit_for_planning": package.validation_status["fit_for_planning"],
            },
        )

    def _emit_failed(
        self, context_identity: str, goal: Goal, correlation: str, exc: ContextError
    ) -> None:
        self._emit(
            context_identity,
            events.CONTEXT_ENGINEERING_FAILED,
            "failed",
            0,
            correlation,
            {"goal": goal.identity, "error": str(exc), "reason": type(exc).__name__},
        )

    def _emit(
        self,
        context_identity: str,
        event_type: str,
        kind: str,
        sequence: int,
        correlation: str,
        payload: Struct,
    ) -> None:
        self._emitter.emit(
            events.build_event(
                ids.event_id(context_identity, kind, sequence),
                event_type,
                correlation,
                payload,
                self._timestamps.now(),
            )
        )

    def _correlation(self, goal: Goal, request: ContextRequest) -> str:
        if request.correlation_identifier is not None:
            return request.correlation_identifier
        if goal.correlation is not None:
            return goal.correlation.correlation_identifier
        return ids.correlation_id(goal.identity)
