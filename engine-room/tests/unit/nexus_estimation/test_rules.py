"""Deterministic scoring rules (``nexus_estimation.rules``)."""

from __future__ import annotations

from nexus_estimation import DEFAULT_MODEL
from nexus_estimation.rules import (
    estimate_cost,
    estimate_duration,
    estimate_resource,
    score_complexity,
)
from nexus_estimation.vocabulary import ComplexityBand, ResourceClass
from tests.unit.nexus_estimation.fixtures import SAMPLE_SIGNALS


def test_complexity_is_weighted_sum_with_factors() -> None:
    score, band, factors, trace = score_complexity(SAMPLE_SIGNALS, DEFAULT_MODEL)
    # 40*.02 + 3*1.5 + 2*1 + 1*1 + 2*.5 + 4*2 + 1*.5 = 0.8+4.5+2+1+1+8+0.5 = 17.8
    assert score == 17.8
    assert band is ComplexityBand.MODERATE
    assert any(f.name == "dependency_count" and f.contribution == 8.0 for f in factors)
    assert trace[-1].endswith("band moderate")


def test_complexity_bands_are_monotonic() -> None:
    trivial, band0, *_ = score_complexity({}, DEFAULT_MODEL)
    assert band0 is ComplexityBand.TRIVIAL
    big, band_big, *_ = score_complexity({"dependency_count": 100.0}, DEFAULT_MODEL)
    assert band_big is ComplexityBand.VERY_HIGH
    assert big > trivial


def test_duration_is_base_plus_per_complexity() -> None:
    seconds, factors, trace = estimate_duration(17.8, DEFAULT_MODEL)
    assert seconds == round(60.0 + 30.0 * 17.8, 4)  # 594.0
    assert any(f.name == "duration_per_complexity" for f in factors)


def test_cost_uses_runtime_rate_when_declared() -> None:
    default_amount, currency, *_ = estimate_cost(100.0, {}, DEFAULT_MODEL)
    assert default_amount == round(100.0 * DEFAULT_MODEL.cost_per_second, 6)
    assert currency == "USD"
    override_amount, _, _, _ = estimate_cost(
        100.0, {"runtime_cost_per_second": 0.01}, DEFAULT_MODEL
    )
    assert override_amount == 1.0


def test_resource_class_follows_complexity_band() -> None:
    rclass, profile, _, _ = estimate_resource(
        17.8, ComplexityBand.MODERATE, {"work_package_count": 3.0}, DEFAULT_MODEL
    )
    assert rclass is ResourceClass.STANDARD
    assert profile["concurrency_hint"] == 3


def test_scorers_are_pure_and_repeatable() -> None:
    assert score_complexity(SAMPLE_SIGNALS, DEFAULT_MODEL) == score_complexity(
        SAMPLE_SIGNALS, DEFAULT_MODEL
    )
    assert estimate_duration(17.8, DEFAULT_MODEL) == estimate_duration(17.8, DEFAULT_MODEL)
