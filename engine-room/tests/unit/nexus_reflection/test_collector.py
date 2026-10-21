"""Unit tests for the Reflection Collector — correlation, ordering, read-only projection."""

from __future__ import annotations

from nexus_recovery.vocabulary import FailureCategory, RecoveryDecision
from nexus_reflection import ReflectionCollector
from nexus_validation.vocabulary import ValidationDecision
from tests.unit.nexus_reflection.helpers import (
    execution_result,
    recovery_plan,
    validation_report,
)


def _collect(**kwargs):  # type: ignore[no-untyped-def]
    return ReflectionCollector().collect("op-window-1", **kwargs)


def test_correlates_the_three_outputs_by_session() -> None:
    history = _collect(
        execution_results=(execution_result("s1"),),
        validation_reports=(validation_report("s1", decision=ValidationDecision.PASSED),),
        recovery_plans=(recovery_plan("s1", decision=RecoveryDecision.COMPLETE),),
    )
    assert len(history.episodes) == 1
    episode = history.episodes[0]
    assert episode.session == "s1"
    assert episode.validation_decision is ValidationDecision.PASSED
    assert episode.recovery_decision is RecoveryDecision.COMPLETE
    assert episode.succeeded is True
    assert episode.runtime == "claude-code"


def test_unions_sessions_across_inputs_in_first_seen_order() -> None:
    history = _collect(
        execution_results=(execution_result("s1"),),
        validation_reports=(validation_report("s2"),),
        recovery_plans=(recovery_plan("s3"),),
    )
    assert [e.session for e in history.episodes] == ["s1", "s2", "s3"]


def test_episode_with_only_a_recovery_plan() -> None:
    history = _collect(
        recovery_plans=(
            recovery_plan(
                "s9",
                decision=RecoveryDecision.RETRY,
                failure_category=FailureCategory.RUNTIME,
                retry_eligible=True,
            ),
        )
    )
    episode = history.episodes[0]
    assert episode.validation_decision is None
    assert episode.recovery_decision is RecoveryDecision.RETRY
    assert episode.failure_category is FailureCategory.RUNTIME
    assert episode.retry_eligible is True
    assert episode.execution_result_ref is None
    assert episode.validation_report_ref is None


def test_empty_history_is_empty() -> None:
    history = _collect()
    assert history.is_empty is True
    assert history.correlation_identifier == ""


def test_correlation_is_taken_from_the_episodes() -> None:
    history = _collect(validation_reports=(validation_report("s1", correlation="cor-xyz"),))
    assert history.correlation_identifier == "cor-xyz"


def test_metrics_are_copied_not_referenced() -> None:
    source = {"k": 1}
    history = _collect(
        execution_results=(execution_result("s1"),),
        metrics=source,
    )
    assert history.metrics == {"k": 1}
    source["k"] = 2  # mutating the input must not affect the collected history
    assert history.metrics == {"k": 1}


def test_runtime_is_none_when_absent_everywhere() -> None:
    history = _collect(validation_reports=(validation_report("s1", runtime=None),))
    assert history.episodes[0].runtime is None


def test_runtime_falls_back_across_sources() -> None:
    # No execution result; runtime resolved from the validation report, then the plan.
    history = _collect(
        validation_reports=(validation_report("s1", runtime=None),),
        recovery_plans=(recovery_plan("s1", runtime="gemini-cli"),),
    )
    assert history.episodes[0].runtime == "gemini-cli"
