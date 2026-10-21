"""Unit tests for the deterministic pattern analyzers (pure aggregation, no learning)."""

from __future__ import annotations

from nexus_recovery.vocabulary import FailureCategory, RecoveryDecision
from nexus_reflection import (
    AnalysisContext,
    BottleneckAnalyzer,
    ExecutionDurationAnalyzer,
    RecoveryDecisionAnalyzer,
    ReflectionCollector,
    RepeatedFailureAnalyzer,
    RepeatedSuccessAnalyzer,
    RetryFrequencyAnalyzer,
    RuntimeUtilizationAnalyzer,
    ValidationOutcomeAnalyzer,
)
from nexus_reflection.vocabulary import ConfidenceLevel, PatternKind
from nexus_validation.vocabulary import ValidationDecision
from tests.unit.nexus_reflection.helpers import (
    execution_result,
    recovery_plan,
    validation_report,
)


def _ctx(execution_results=(), validation_reports=(), recovery_plans=()):  # type: ignore[no-untyped-def]
    history = ReflectionCollector().collect(
        "op-window-1",
        execution_results=execution_results,
        validation_reports=validation_reports,
        recovery_plans=recovery_plans,
    )
    return AnalysisContext(history=history)


def _failed(session, category=FailureCategory.RUNTIME, runtime="claude-code"):  # type: ignore[no-untyped-def]
    return (
        validation_report(session, decision=ValidationDecision.FAILED, runtime=runtime),
        recovery_plan(
            session,
            decision=RecoveryDecision.RETRY,
            failure_category=category,
            runtime=runtime,
            retry_eligible=True,
        ),
    )


def _passed(session, runtime="claude-code"):  # type: ignore[no-untyped-def]
    return (
        validation_report(session, decision=ValidationDecision.PASSED, runtime=runtime),
        recovery_plan(session, decision=RecoveryDecision.COMPLETE, runtime=runtime),
    )


# --- repeated failure / success --------------------------------------------- #


def test_repeated_failure_groups_by_category() -> None:
    r1, p1 = _failed("s1")
    r2, p2 = _failed("s2")
    r3, p3 = _passed("s3")
    ctx = _ctx(validation_reports=(r1, r2, r3), recovery_plans=(p1, p2, p3))
    patterns = RepeatedFailureAnalyzer().analyze(ctx)
    assert len(patterns) == 1
    assert patterns[0].kind is PatternKind.REPEATED_FAILURE
    assert patterns[0].subject == "runtime"
    assert patterns[0].occurrences == 2
    assert patterns[0].confidence is ConfidenceLevel.OBSERVED
    assert patterns[0].is_confirmed is True


def test_repeated_failure_none_when_all_passed() -> None:
    r1, p1 = _passed("s1")
    ctx = _ctx(validation_reports=(r1,), recovery_plans=(p1,))
    assert RepeatedFailureAnalyzer().analyze(ctx) == ()


def test_repeated_success_groups_by_runtime() -> None:
    r1, p1 = _passed("s1", runtime="claude-code")
    r2, p2 = _passed("s2", runtime="claude-code")
    ctx = _ctx(validation_reports=(r1, r2), recovery_plans=(p1, p2))
    patterns = RepeatedSuccessAnalyzer().analyze(ctx)
    assert patterns[0].kind is PatternKind.REPEATED_SUCCESS
    assert patterns[0].subject == "claude-code"
    assert patterns[0].occurrences == 2


# --- retry frequency -------------------------------------------------------- #


def test_retry_frequency_measures_rate() -> None:
    r1, p1 = _failed("s1")
    r2, p2 = _passed("s2")
    ctx = _ctx(validation_reports=(r1, r2), recovery_plans=(p1, p2))
    patterns = RetryFrequencyAnalyzer().analyze(ctx)
    assert patterns[0].kind is PatternKind.RETRY_FREQUENCY
    assert patterns[0].occurrences == 1
    assert patterns[0].detail["rate"] == 0.5
    assert patterns[0].detail["retry_eligible"] == 1


def test_retry_frequency_empty_history_yields_nothing() -> None:
    assert RetryFrequencyAnalyzer().analyze(_ctx()) == ()


# --- outcome / decision / utilization --------------------------------------- #


def test_validation_outcome_counts_by_decision() -> None:
    r1, p1 = _failed("s1")
    r2, p2 = _passed("s2")
    ctx = _ctx(validation_reports=(r1, r2), recovery_plans=(p1, p2))
    patterns = ValidationOutcomeAnalyzer().analyze(ctx)
    subjects = {p.subject: p.occurrences for p in patterns}
    assert subjects == {"failed": 1, "passed": 1}


def test_recovery_decision_counts_by_decision() -> None:
    r1, p1 = _failed("s1")
    r2, p2 = _passed("s2")
    ctx = _ctx(validation_reports=(r1, r2), recovery_plans=(p1, p2))
    patterns = RecoveryDecisionAnalyzer().analyze(ctx)
    subjects = {p.subject: p.occurrences for p in patterns}
    assert subjects == {"retry": 1, "complete": 1}


def test_runtime_utilization_counts_by_runtime() -> None:
    r1, p1 = _passed("s1", runtime="claude-code")
    r2, p2 = _passed("s2", runtime="gemini-cli")
    ctx = _ctx(validation_reports=(r1, r2), recovery_plans=(p1, p2))
    patterns = RuntimeUtilizationAnalyzer().analyze(ctx)
    subjects = {p.subject: p.occurrences for p in patterns}
    assert subjects == {"claude-code": 1, "gemini-cli": 1}


# --- execution duration ----------------------------------------------------- #


def test_execution_duration_aggregates_metric() -> None:
    ctx = _ctx(
        execution_results=(
            execution_result("s1", metrics={"duration_ms": 100}),
            execution_result("s2", metrics={"duration_ms": 300}),
        )
    )
    patterns = ExecutionDurationAnalyzer().analyze(ctx)
    assert patterns[0].kind is PatternKind.EXECUTION_DURATION
    assert patterns[0].detail["mean"] == 200.0
    assert patterns[0].detail["max"] == 300.0
    assert patterns[0].detail["samples"] == 2


def test_execution_duration_none_without_metric() -> None:
    ctx = _ctx(execution_results=(execution_result("s1", metrics={"other": 1}),))
    assert ExecutionDurationAnalyzer().analyze(ctx) == ()


# --- bottleneck ------------------------------------------------------------- #


def test_bottleneck_picks_dominant_friction_category() -> None:
    r1, p1 = _failed("s1", category=FailureCategory.RUNTIME)
    r2, p2 = _failed("s2", category=FailureCategory.RUNTIME)
    r3, p3 = _failed("s3", category=FailureCategory.RESOURCE)
    ctx = _ctx(validation_reports=(r1, r2, r3), recovery_plans=(p1, p2, p3))
    patterns = BottleneckAnalyzer().analyze(ctx)
    assert patterns[0].kind is PatternKind.BOTTLENECK
    assert patterns[0].subject == "runtime"
    assert patterns[0].occurrences == 2


def test_bottleneck_none_when_no_friction() -> None:
    r1, p1 = _passed("s1")
    ctx = _ctx(validation_reports=(r1,), recovery_plans=(p1,))
    assert BottleneckAnalyzer().analyze(ctx) == ()


def test_bottleneck_none_when_friction_has_no_category() -> None:
    # A retry recovery decision on a passed validation with no failure category: friction
    # exists (recovery decision) but there is no category to attribute a bottleneck to.
    report = validation_report("s1", decision=ValidationDecision.PASSED)
    plan = recovery_plan(
        "s1", decision=RecoveryDecision.RETRY, failure_category=FailureCategory.NONE
    )
    ctx = _ctx(validation_reports=(report,), recovery_plans=(plan,))
    assert BottleneckAnalyzer().analyze(ctx) == ()
