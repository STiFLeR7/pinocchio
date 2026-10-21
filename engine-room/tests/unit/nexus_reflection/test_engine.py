"""Unit tests for the Reflection Engine — report, events, determinism, persistence."""

from __future__ import annotations

from nexus_infra import InMemoryObservability, build_infrastructure
from nexus_recovery.vocabulary import FailureCategory, RecoveryDecision
from nexus_reflection import ReflectionEngine, build_reflection
from nexus_reflection.vocabulary import ReflectionStage
from nexus_runtime.events import FixedTimestampSource
from nexus_validation.vocabulary import ValidationDecision
from tests.unit.nexus_reflection.helpers import (
    execution_result,
    recovery_plan,
    validation_report,
)


def _infra():  # type: ignore[no-untyped-def]
    return build_infrastructure(observability=InMemoryObservability())


def _reflection_events(infra):  # type: ignore[no-untyped-def]
    return [e for e in infra.event_store.read_all() if e.type.startswith("reflection.")]


def _failed(session, category=FailureCategory.RUNTIME):  # type: ignore[no-untyped-def]
    return (
        execution_result(session),
        validation_report(session, decision=ValidationDecision.FAILED),
        recovery_plan(
            session, decision=RecoveryDecision.RETRY, failure_category=category, retry_eligible=True
        ),
    )


def _reflect(engine, sessions_specs, *, scope="op-window-1", metrics=None):  # type: ignore[no-untyped-def]
    results, reports, plans = [], [], []
    for r, v, p in sessions_specs:
        results.append(r)
        reports.append(v)
        plans.append(p)
    return engine.reflect(
        scope,
        execution_results=tuple(results),
        validation_reports=tuple(reports),
        recovery_plans=tuple(plans),
        metrics=metrics,
    )


# --- report ----------------------------------------------------------------- #


def test_reflect_produces_a_report_with_patterns() -> None:
    ctx = build_reflection(_infra(), timestamps=FixedTimestampSource())
    report = _reflect(ctx.engine, (_failed("s1"), _failed("s2")))
    assert report.stage is ReflectionStage.COMPLETED
    assert report.episode_count == 2
    assert report.patterns
    assert report.is_empty is False
    assert any("recurring runtime failures" in c.summary for c in report.knowledge_candidates)


def test_empty_history_reflects_but_fails() -> None:
    ctx = build_reflection(_infra(), timestamps=FixedTimestampSource())
    report = ctx.engine.reflect("empty-window")
    assert report.stage is ReflectionStage.FAILED
    assert report.is_empty is True
    assert report.patterns == ()


# --- events ----------------------------------------------------------------- #


def test_emits_full_reflection_event_sequence() -> None:
    infra = _infra()
    ctx = build_reflection(infra, timestamps=FixedTimestampSource())
    _reflect(ctx.engine, (_failed("s1"),))
    types = [e.type for e in _reflection_events(infra)]
    assert types == [
        "reflection.started",
        "reflection.analysis_completed",
        "reflection.report_created",
        "reflection.completed",
    ]


def test_empty_history_emits_reflection_failed() -> None:
    infra = _infra()
    ctx = build_reflection(infra, timestamps=FixedTimestampSource())
    ctx.engine.reflect("empty-window")
    assert "reflection.failed" in [e.type for e in _reflection_events(infra)]


def test_report_created_event_carries_candidate_count() -> None:
    infra = _infra()
    ctx = build_reflection(infra, timestamps=FixedTimestampSource())
    _reflect(ctx.engine, (_failed("s1"), _failed("s2")))
    created = next(e for e in _reflection_events(infra) if e.type == "reflection.report_created")
    assert created.payload["candidates"] >= 1


# --- determinism ------------------------------------------------------------ #


def test_two_runs_produce_identical_reports_and_events() -> None:
    infra1, infra2 = _infra(), _infra()
    c1 = build_reflection(infra1, timestamps=FixedTimestampSource())
    c2 = build_reflection(infra2, timestamps=FixedTimestampSource())
    r1 = _reflect(c1.engine, (_failed("s1"), _failed("s2")))
    r2 = _reflect(c2.engine, (_failed("s1"), _failed("s2")))
    assert r1 == r2
    t1 = [(e.identifier, e.type, e.payload) for e in _reflection_events(infra1)]
    t2 = [(e.identifier, e.type, e.payload) for e in _reflection_events(infra2)]
    assert t1 == t2


# --- persistence ------------------------------------------------------------ #


def test_report_and_patterns_are_persisted() -> None:
    ctx = build_reflection(_infra(), timestamps=FixedTimestampSource())
    report = _reflect(ctx.engine, (_failed("s1"), _failed("s2")))
    assert ctx.repositories.reports.get(report.identity) == report
    for pattern in report.patterns:
        assert ctx.repositories.patterns.get(pattern.identity) is not None


def test_engine_without_repositories_still_returns_report() -> None:
    engine = ReflectionEngine(_infra(), timestamps=FixedTimestampSource())  # no repositories
    report = _reflect(engine, (_failed("s1"),))
    assert report.episode_count == 1


def test_report_references_operations_without_duplicating() -> None:
    ctx = build_reflection(_infra(), timestamps=FixedTimestampSource())
    report = _reflect(ctx.engine, (_failed("s1"),))
    assert report.reference().target_type == "reflection_report"
    assert all(hasattr(ref, "identifier") for ref in report.evidence_refs)
    assert report.correlation_identifier == "cor-refl"
