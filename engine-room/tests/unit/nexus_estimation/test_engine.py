"""The Estimation Engine (``nexus_estimation.engine``) — report shape, determinism, wiring."""

from __future__ import annotations

from nexus_estimation import (
    ComplexityEstimate,
    ConfidenceEstimate,
    CostEstimate,
    DurationEstimate,
    EstimationInputs,
    ResourceEstimate,
    build_estimation,
)
from nexus_estimation.events import ESTIMATION_ESTIMATED
from nexus_infra import build_infrastructure
from tests.unit.nexus_estimation.fixtures import SAMPLE_SIGNALS, make_work_package


def _ctx():
    return build_estimation(build_infrastructure(), now=lambda: "2026-01-01T00:00:00Z")


def _inputs(subject="wp-1", correlation="cor-1"):
    return EstimationInputs(subject, correlation, SAMPLE_SIGNALS)


def test_report_bundles_the_five_estimates() -> None:
    report = _ctx().engine.estimate(_inputs())
    assert isinstance(report.complexity, ComplexityEstimate)
    assert isinstance(report.duration, DurationEstimate)
    assert isinstance(report.cost, CostEstimate)
    assert isinstance(report.confidence, ConfidenceEstimate)
    assert isinstance(report.resource, ResourceEstimate)


def test_every_estimate_carries_the_required_shape() -> None:
    report = _ctx().engine.estimate(_inputs())
    for estimate in (
        report.complexity,
        report.duration,
        report.cost,
        report.confidence,
        report.resource,
    ):
        assert estimate.identity  # deterministic identity
        assert estimate.reasoning_trace  # reasoning trace
        assert estimate.factors  # contributing factors
        assert 0.0 <= estimate.confidence <= 1.0  # confidence
        assert estimate.model_version == "1"


def test_determinism_identical_inputs_identical_estimates() -> None:
    engine = _ctx().engine
    a = engine.estimate(_inputs(), persist=False)
    b = engine.estimate(_inputs(), persist=False)
    assert a == b


def test_estimate_from_work_package() -> None:
    ctx = _ctx()
    wp = make_work_package("wp-42", dependencies=4, skills=3)
    report = ctx.engine.estimate_work_package(wp, "cor-42")
    assert report.subject_identifier == "wp-42"
    assert report.complexity.score > 0


def test_estimation_persists_and_emits_one_event() -> None:
    infra = build_infrastructure()
    ctx = build_estimation(infra, now=lambda: "t")
    report = ctx.engine.estimate(_inputs())
    assert ctx.repositories.reports.get(report.identity) == report
    events = [e for e in infra.event_store.read_all() if e.type == ESTIMATION_ESTIMATED]
    assert len(events) == 1
    assert events[0].correlation_identifier == "cor-1"


def test_estimate_without_persist_records_nothing() -> None:
    infra = build_infrastructure()
    ctx = build_estimation(infra, now=lambda: "t")
    ctx.engine.estimate(_inputs(), persist=False)
    assert list(infra.event_store.read_all()) == []
    assert ctx.repositories.reports.count == 0
