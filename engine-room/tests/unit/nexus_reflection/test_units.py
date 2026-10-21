"""Unit tests for the small Reflection building blocks — ids, patterns, report, wiring."""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_infra import InMemoryObservability, build_infrastructure
from nexus_reflection import (
    ConfidenceLevel,
    KnowledgeCandidate,
    OperationalEpisode,
    OperationalPattern,
    PatternKind,
    ReflectionObservability,
    build_reflection,
    build_reflection_repositories,
    confidence_for,
    ids,
)
from nexus_reflection.analyzers import _share
from nexus_reflection.events import REFLECTION_STARTED, build_event
from nexus_reflection.report import ReflectionReport
from nexus_reflection.vocabulary import (
    OPERATIONAL_PATTERN_TARGET_TYPE,
    REFLECTION_REPORT_TARGET_TYPE,
    ReflectionStage,
)
from nexus_runtime.events import FixedTimestampSource
from nexus_validation.vocabulary import ValidationDecision
from tests.unit.nexus_reflection.helpers import recovery_plan, validation_report

# --- ids -------------------------------------------------------------------- #


def test_ids_are_pure_functions_of_scope() -> None:
    assert ids.report_id("w1") == "rr-w1"
    assert ids.pattern_id("w1", "bottleneck", 0) == "pat-w1-bottleneck-0000"
    assert ids.candidate_id("w1", 2) == "kc-w1-0002"
    assert ids.event_id("w1", "started", 0) == "evt-w1-refl-started-0000"


# --- confidence ------------------------------------------------------------- #


def test_confidence_mapping_is_deterministic() -> None:
    assert confidence_for(0) is ConfidenceLevel.EXPERIMENTAL
    assert confidence_for(1) is ConfidenceLevel.EXPERIMENTAL
    assert confidence_for(2) is ConfidenceLevel.OBSERVED
    assert confidence_for(3) is ConfidenceLevel.VALIDATED
    assert confidence_for(5) is ConfidenceLevel.PROVEN


def test_share_handles_empty_population() -> None:
    assert _share(1, 0) == 0.0
    assert _share(1, 2) == 0.5


# --- patterns / candidates -------------------------------------------------- #


def test_pattern_reference_and_confirmation() -> None:
    pattern = OperationalPattern(
        identity="pat-w1-repeated_failure-0000",
        kind=PatternKind.REPEATED_FAILURE,
        subject="runtime",
        description="two runtime failures",
        occurrences=2,
        population=3,
        confidence=ConfidenceLevel.OBSERVED,
    )
    assert pattern.reference() == Reference(
        target_type=OPERATIONAL_PATTERN_TARGET_TYPE, identifier="pat-w1-repeated_failure-0000"
    )
    assert pattern.is_confirmed is True
    candidate = KnowledgeCandidate(
        identity="kc-w1-0000", summary="investigate", confidence=ConfidenceLevel.OBSERVED
    )
    assert candidate.reference().target_type == "knowledge_candidate"


def test_episode_reference_and_failure_flag() -> None:
    episode = OperationalEpisode(session="s1", validation_decision=ValidationDecision.FAILED)
    assert episode.reference().target_type == "operational_episode"
    assert episode.is_failure is True
    assert OperationalEpisode(session="s2").is_failure is False


# --- report ----------------------------------------------------------------- #


def test_report_reference_and_empty_flag() -> None:
    report = ReflectionReport(
        identity="rr-w1",
        scope="w1",
        stage=ReflectionStage.FAILED,
        confidence=ConfidenceLevel.EXPERIMENTAL,
    )
    assert report.reference() == Reference(
        target_type=REFLECTION_REPORT_TARGET_TYPE, identifier="rr-w1"
    )
    assert report.is_empty is True


# --- events ----------------------------------------------------------------- #


def test_build_event_is_a_canonical_reflection_event() -> None:
    event = build_event("evt-w1-refl-started-0000", REFLECTION_STARTED, "cor", {"k": "v"}, "t")
    assert event.producer == "reflection"
    assert event.source == "nexus_reflection"
    assert event.type == REFLECTION_STARTED


# --- observability ---------------------------------------------------------- #


def test_observability_increments_named_counters() -> None:
    sink = InMemoryObservability()
    obs = ReflectionObservability(sink)
    obs.started()
    obs.analysis_completed(3)
    obs.report_created()
    obs.completed()
    obs.failed()
    assert sink.counters["reflection.started"] == 1
    assert sink.counters["reflection.analysis_completed"] == 1
    assert sink.counters["reflection.report_created"] == 1
    assert sink.counters["reflection.completed"] == 1
    assert sink.counters["reflection.failed"] == 1
    assert sink.observations["reflection.pattern_count"] == [3.0]


def test_observability_defaults_to_null_sink() -> None:
    ReflectionObservability().started()  # no sink → NullObservability, no error


# --- persistence + composition --------------------------------------------- #


def test_build_reflection_reuses_supplied_repositories() -> None:
    infra = build_infrastructure(observability=InMemoryObservability())
    repos = build_reflection_repositories(infra.observability)
    ctx = build_reflection(infra, repositories=repos, timestamps=FixedTimestampSource())
    assert ctx.repositories is repos
    report = ctx.engine.reflect(
        "w1",
        validation_reports=(validation_report("s1"),),
        recovery_plans=(recovery_plan("s1"),),
    )
    assert repos.reports.get(report.identity) == report


def test_build_reflection_defaults_wire_a_working_engine() -> None:
    infra = build_infrastructure(observability=InMemoryObservability())
    ctx = build_reflection(infra)  # no timestamps → SystemTimestampSource
    report = ctx.engine.reflect(
        "w1",
        validation_reports=(validation_report("s1"),),
        recovery_plans=(recovery_plan("s1"),),
    )
    assert report.timestamp  # a system timestamp was recorded
