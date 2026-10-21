"""Unit tests for reflection synthesis — summaries, confidence, Knowledge Candidates."""

from __future__ import annotations

from nexus_recovery.vocabulary import FailureCategory, RecoveryDecision
from nexus_reflection import (
    DEFAULT_ANALYZERS,
    AnalysisContext,
    ReflectionCollector,
    ReflectionSynthesizer,
)
from nexus_reflection.vocabulary import ConfidenceLevel
from nexus_validation.vocabulary import ValidationDecision
from tests.unit.nexus_reflection.helpers import recovery_plan, validation_report


def _history(reports, plans, *, scope="op-window-1", metrics=None):  # type: ignore[no-untyped-def]
    return ReflectionCollector().collect(
        scope, validation_reports=reports, recovery_plans=plans, metrics=metrics
    )


def _patterns(history):  # type: ignore[no-untyped-def]
    ctx = AnalysisContext(history=history)
    out = []
    for analyzer in DEFAULT_ANALYZERS:
        out.extend(analyzer.analyze(ctx))
    return tuple(out)


def _failed(session, category=FailureCategory.RUNTIME):  # type: ignore[no-untyped-def]
    return (
        validation_report(session, decision=ValidationDecision.FAILED),
        recovery_plan(
            session, decision=RecoveryDecision.RETRY, failure_category=category, retry_eligible=True
        ),
    )


def _passed(session):  # type: ignore[no-untyped-def]
    return (
        validation_report(session, decision=ValidationDecision.PASSED),
        recovery_plan(session, decision=RecoveryDecision.COMPLETE),
    )


def _synthesize(reports, plans, **kwargs):  # type: ignore[no-untyped-def]
    history = _history(reports, plans, **kwargs)
    return history, ReflectionSynthesizer().synthesize(history, _patterns(history))


def test_summaries_count_outcomes() -> None:
    r1, p1 = _failed("s1")
    r2, p2 = _passed("s2")
    _history_, insight = _synthesize((r1, r2), (p1, p2))
    assert insight.execution_summary["total"] == 2
    assert insight.execution_summary["succeeded"] == 1
    assert insight.execution_summary["failed"] == 1
    assert insight.validation_summary["by_decision"] == {"failed": 1, "passed": 1}
    assert insight.recovery_summary["by_decision"] == {"retry": 1, "complete": 1}
    assert insight.recovery_summary["retry_eligible"] == 1


def test_confidence_scales_with_history_size() -> None:
    one = _synthesize((validation_report("s1"),), (recovery_plan("s1"),))[1]
    assert one.confidence is ConfidenceLevel.EXPERIMENTAL
    reports = tuple(validation_report(f"s{i}") for i in range(5))
    plans = tuple(recovery_plan(f"s{i}") for i in range(5))
    five = ReflectionSynthesizer().synthesize(
        _history(reports, plans), _patterns(_history(reports, plans))
    )
    assert five.confidence is ConfidenceLevel.PROVEN


def test_confirmed_repeated_failure_becomes_a_candidate() -> None:
    r1, p1 = _failed("s1")
    r2, p2 = _failed("s2")
    _history_, insight = _synthesize((r1, r2), (p1, p2))
    summaries = [c.summary for c in insight.knowledge_candidates]
    assert any("recurring runtime failures" in s for s in summaries)
    assert insight.recommendations == tuple(c.summary for c in insight.knowledge_candidates)
    # candidates carry a deterministic id and reference the source pattern.
    assert insight.knowledge_candidates[0].identity.startswith("kc-op-window-1-")
    assert insight.knowledge_candidates[0].source_pattern_ref is not None


def test_single_failure_is_not_actionable_yet() -> None:
    r1, p1 = _failed("s1")
    r2, p2 = _passed("s2")
    _history_, insight = _synthesize((r1, r2), (p1, p2))
    # One runtime failure is Experimental (occurrences 1) → not confirmed → no candidate.
    assert all("recurring runtime failures" not in c.summary for c in insight.knowledge_candidates)


def test_metrics_appear_in_execution_summary() -> None:
    r1, p1 = _passed("s1")
    _history_, insight = _synthesize((r1,), (p1,), metrics={"window_ms": 42})
    assert insight.execution_summary["metrics"] == {"window_ms": 42}


def test_evidence_refs_are_deduplicated() -> None:
    r1, p1 = _failed("s1")
    _history_, insight = _synthesize((r1,), (p1,))
    keys = [(r.target_type, r.identifier) for r in insight.evidence_refs]
    assert len(keys) == len(set(keys))
