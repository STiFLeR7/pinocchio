"""The confidence model (``nexus_estimation.confidence``) — reproducible trust scoring."""

from __future__ import annotations

from dataclasses import replace

from nexus_estimation import DEFAULT_MODEL
from nexus_estimation.baseline import HistoricalStat
from nexus_estimation.confidence import score_confidence
from nexus_estimation.vocabulary import ConfidenceBand
from tests.unit.nexus_estimation.fixtures import SAMPLE_SIGNALS


def test_full_coverage_no_history_is_medium() -> None:
    value, band, factors, _ = score_confidence(SAMPLE_SIGNALS, DEFAULT_MODEL)
    # coverage 6/6 = 1.0, sample adequacy 0 → 0.6*1 + 0.4*0 = 0.6
    assert value == 0.6
    assert band is ConfidenceBand.MEDIUM
    assert {f.name for f in factors} == {"signal_coverage", "sample_adequacy"}


def test_partial_coverage_lowers_confidence() -> None:
    value, band, _, _ = score_confidence({"skill_count": 1.0}, DEFAULT_MODEL)
    assert value < 0.6
    assert band is ConfidenceBand.LOW


def test_historical_samples_raise_confidence() -> None:
    model = replace(DEFAULT_MODEL, historical={"duration": HistoricalStat(mean=300.0, samples=30)})
    value, band, _, _ = score_confidence(SAMPLE_SIGNALS, model)
    assert value == 1.0  # coverage 1.0 + full samples → 0.6 + 0.4
    assert band is ConfidenceBand.HIGH


def test_confidence_is_reproducible() -> None:
    assert score_confidence(SAMPLE_SIGNALS, DEFAULT_MODEL) == score_confidence(
        SAMPLE_SIGNALS, DEFAULT_MODEL
    )
