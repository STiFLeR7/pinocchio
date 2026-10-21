"""Pattern analysis — deterministic aggregation over operational history (no learning).

Milestone 2. Each analyzer is a pure function of the :class:`AnalysisContext` (the collected
:class:`~nexus_reflection.collector.OperationalHistory`). It performs **pure deterministic
aggregation** — counting, grouping, ratios — with *no statistical learning, no heuristics, and
no AI* (doc 26 *Evidence First*). Every emitted :class:`~nexus_reflection.patterns.
OperationalPattern` references the episodes it was derived from by id (INV-12) and carries a
confidence derived solely from its repetition count.

Grouping preserves first-seen order over the (already deterministic) episode sequence, so
identical history yields identical patterns.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from nexus_core.contracts.base import Reference, Struct
from nexus_recovery.vocabulary import FailureCategory, RecoveryDecision
from nexus_reflection import ids
from nexus_reflection.collector import OperationalHistory
from nexus_reflection.episode import OperationalEpisode
from nexus_reflection.patterns import OperationalPattern, confidence_for
from nexus_reflection.vocabulary import PatternKind

_FRICTION_DECISIONS = (
    RecoveryDecision.RETRY,
    RecoveryDecision.ESCALATE,
    RecoveryDecision.ABORT,
    RecoveryDecision.AWAIT_APPROVAL,
)
_DURATION_METRIC = "duration_ms"


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    """The immutable input to every analyzer — the collected history and its scope."""

    history: OperationalHistory

    @property
    def scope(self) -> str:
        return self.history.scope

    @property
    def correlation(self) -> str:
        return self.history.correlation_identifier

    @property
    def episodes(self) -> tuple[OperationalEpisode, ...]:
        return self.history.episodes


def _episode_ref(episode: OperationalEpisode) -> Reference:
    """The most specific persisted reference for an episode (plan > report > result)."""
    return (
        episode.recovery_plan_ref
        or episode.validation_report_ref
        or episode.execution_result_ref
        or episode.reference()
    )


def _pattern(
    ctx: AnalysisContext,
    kind: PatternKind,
    seq: int,
    *,
    subject: str,
    description: str,
    occurrences: int,
    detail: Struct,
    episodes: tuple[OperationalEpisode, ...],
) -> OperationalPattern:
    return OperationalPattern(
        identity=ids.pattern_id(ctx.scope, kind.value, seq),
        kind=kind,
        subject=subject,
        description=description,
        occurrences=occurrences,
        population=len(ctx.episodes),
        confidence=confidence_for(occurrences),
        detail=detail,
        evidence_refs=tuple(_episode_ref(e) for e in episodes),
        correlation_identifier=ctx.correlation,
    )


@runtime_checkable
class OperationalAnalyzer(Protocol):
    """A deterministic aggregation over the operational history."""

    analyzer_id: str

    def analyze(self, context: AnalysisContext) -> tuple[OperationalPattern, ...]:
        """Return the immutable patterns this analyzer finds (deterministic, evidence-backed)."""
        ...


def _grouped(
    episodes: tuple[OperationalEpisode, ...],
    key: Callable[[OperationalEpisode], str | None],
) -> dict[str, list[OperationalEpisode]]:
    """Group episodes by a string key, preserving first-seen order."""
    groups: dict[str, list[OperationalEpisode]] = {}
    for episode in episodes:
        value = key(episode)
        if value is None:
            continue
        groups.setdefault(value, []).append(episode)
    return groups


class RepeatedFailureAnalyzer:
    """Groups failing episodes by failure category (failure factors)."""

    analyzer_id = "repeated_failure"

    def analyze(self, context: AnalysisContext) -> tuple[OperationalPattern, ...]:
        failures = tuple(
            e
            for e in context.episodes
            if e.is_failure and e.failure_category not in (None, FailureCategory.NONE)
        )
        groups = _grouped(
            failures, lambda e: e.failure_category.value if e.failure_category else None
        )
        return tuple(
            _pattern(
                context,
                PatternKind.REPEATED_FAILURE,
                seq,
                subject=category,
                description=f"{len(items)} {category} failure(s) across the history",
                occurrences=len(items),
                detail={"category": category, "share": _share(len(items), len(context.episodes))},
                episodes=tuple(items),
            )
            for seq, (category, items) in enumerate(groups.items())
        )


class RepeatedSuccessAnalyzer:
    """Groups passing episodes by runtime (reusable, successful approaches)."""

    analyzer_id = "repeated_success"

    def analyze(self, context: AnalysisContext) -> tuple[OperationalPattern, ...]:
        successes = tuple(e for e in context.episodes if e.succeeded)
        groups = _grouped(successes, lambda e: e.runtime or "unknown")
        return tuple(
            _pattern(
                context,
                PatternKind.REPEATED_SUCCESS,
                seq,
                subject=runtime,
                description=f"{len(items)} successful operation(s) on {runtime}",
                occurrences=len(items),
                detail={"runtime": runtime, "share": _share(len(items), len(context.episodes))},
                episodes=tuple(items),
            )
            for seq, (runtime, items) in enumerate(groups.items())
        )


class RetryFrequencyAnalyzer:
    """Measures how often operations were routed to a retry (retry frequency)."""

    analyzer_id = "retry_frequency"

    def analyze(self, context: AnalysisContext) -> tuple[OperationalPattern, ...]:
        if not context.episodes:
            return ()
        retried = tuple(
            e for e in context.episodes if e.recovery_decision is RecoveryDecision.RETRY
        )
        eligible = sum(1 for e in context.episodes if e.retry_eligible)
        return (
            _pattern(
                context,
                PatternKind.RETRY_FREQUENCY,
                0,
                subject="retry",
                description=f"{len(retried)} of {len(context.episodes)} operation(s) retried",
                occurrences=len(retried),
                detail={
                    "retried": len(retried),
                    "retry_eligible": eligible,
                    "rate": _share(len(retried), len(context.episodes)),
                },
                episodes=retried,
            ),
        )


class ValidationOutcomeAnalyzer:
    """Counts operations by validation verdict (validation outcomes)."""

    analyzer_id = "validation_outcome"

    def analyze(self, context: AnalysisContext) -> tuple[OperationalPattern, ...]:
        groups = _grouped(
            context.episodes,
            lambda e: e.validation_decision.value if e.validation_decision else None,
        )
        return tuple(
            _pattern(
                context,
                PatternKind.VALIDATION_OUTCOME,
                seq,
                subject=decision,
                description=f"{len(items)} operation(s) validated {decision}",
                occurrences=len(items),
                detail={"decision": decision},
                episodes=tuple(items),
            )
            for seq, (decision, items) in enumerate(groups.items())
        )


class RecoveryDecisionAnalyzer:
    """Counts operations by recovery decision (recovery decisions)."""

    analyzer_id = "recovery_decision"

    def analyze(self, context: AnalysisContext) -> tuple[OperationalPattern, ...]:
        groups = _grouped(
            context.episodes,
            lambda e: e.recovery_decision.value if e.recovery_decision else None,
        )
        return tuple(
            _pattern(
                context,
                PatternKind.RECOVERY_DECISION,
                seq,
                subject=decision,
                description=f"{len(items)} operation(s) resolved to recovery '{decision}'",
                occurrences=len(items),
                detail={"decision": decision},
                episodes=tuple(items),
            )
            for seq, (decision, items) in enumerate(groups.items())
        )


class RuntimeUtilizationAnalyzer:
    """Counts operations by runtime (runtime utilization)."""

    analyzer_id = "runtime_utilization"

    def analyze(self, context: AnalysisContext) -> tuple[OperationalPattern, ...]:
        groups = _grouped(context.episodes, lambda e: e.runtime or "unknown")
        return tuple(
            _pattern(
                context,
                PatternKind.RUNTIME_UTILIZATION,
                seq,
                subject=runtime,
                description=f"{runtime} ran {len(items)} operation(s)",
                occurrences=len(items),
                detail={"runtime": runtime, "share": _share(len(items), len(context.episodes))},
                episodes=tuple(items),
            )
            for seq, (runtime, items) in enumerate(groups.items())
        )


class ExecutionDurationAnalyzer:
    """Aggregates a numeric duration metric across operations (execution duration)."""

    analyzer_id = "execution_duration"

    def analyze(self, context: AnalysisContext) -> tuple[OperationalPattern, ...]:
        samples = [
            (e, float(e.metrics[_DURATION_METRIC]))
            for e in context.episodes
            if isinstance(e.metrics.get(_DURATION_METRIC), (int, float))
        ]
        if not samples:
            return ()
        values = [v for _e, v in samples]
        detail: Struct = {
            "metric": _DURATION_METRIC,
            "samples": len(values),
            "total": round(sum(values), 4),
            "min": min(values),
            "max": max(values),
            "mean": round(sum(values) / len(values), 4),
        }
        return (
            _pattern(
                context,
                PatternKind.EXECUTION_DURATION,
                0,
                subject=_DURATION_METRIC,
                description=f"{len(values)} duration sample(s); mean {detail['mean']}",
                occurrences=len(values),
                detail=detail,
                episodes=tuple(e for e, _v in samples),
            ),
        )


class BottleneckAnalyzer:
    """Identifies the dominant friction category (bottlenecks)."""

    analyzer_id = "bottleneck"

    def analyze(self, context: AnalysisContext) -> tuple[OperationalPattern, ...]:
        friction = tuple(
            e
            for e in context.episodes
            if e.is_failure or e.recovery_decision in _FRICTION_DECISIONS
        )
        if not friction:
            return ()
        categories = [
            e.failure_category.value
            for e in friction
            if e.failure_category is not None and e.failure_category is not FailureCategory.NONE
        ]
        if not categories:
            return ()
        counts: Counter[str] = Counter(categories)
        # Deterministic: highest count, ties broken by first-seen order (max returns the
        # first key reaching the maximum when iterating a first-seen-ordered sequence).
        order = list(dict.fromkeys(categories))
        subject = max(order, key=lambda c: counts[c])
        contributing = tuple(
            e
            for e in friction
            if e.failure_category is not None and e.failure_category.value == subject
        )
        return (
            _pattern(
                context,
                PatternKind.BOTTLENECK,
                0,
                subject=subject,
                description=f"'{subject}' is the dominant friction ({counts[subject]} occurrence(s))",
                occurrences=counts[subject],
                detail={"category": subject, "friction_total": len(friction)},
                episodes=contributing,
            ),
        )


def _share(count: int, population: int) -> float:
    """A deterministic ratio in [0,1] (0.0 when the population is empty)."""
    return round(count / population, 4) if population else 0.0


DEFAULT_ANALYZERS: tuple[OperationalAnalyzer, ...] = (
    RepeatedFailureAnalyzer(),
    RepeatedSuccessAnalyzer(),
    RetryFrequencyAnalyzer(),
    ValidationOutcomeAnalyzer(),
    RecoveryDecisionAnalyzer(),
    RuntimeUtilizationAnalyzer(),
    ExecutionDurationAnalyzer(),
    BottleneckAnalyzer(),
)
