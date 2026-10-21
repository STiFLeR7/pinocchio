"""The confidence model — a deterministic, reproducible measure of estimate trust.

Confidence is a pure function of two immutable facts: **signal coverage** (how many of the
model's expected signals the inputs actually provided) and **historical sample adequacy** (how
many recorded samples back the versioned model, relative to a "full-confidence" sample count).
No randomness, no clock — identical inputs reproduce the identical confidence and band.
"""

from __future__ import annotations

from collections.abc import Mapping

from nexus_estimation.baseline import EstimationModel
from nexus_estimation.model import Factor
from nexus_estimation.vocabulary import ConfidenceBand

_COVERAGE_WEIGHT = 0.6
_SAMPLE_WEIGHT = 0.4


def _band_for(value: float) -> ConfidenceBand:
    if value >= 0.8:
        return ConfidenceBand.HIGH
    if value >= 0.5:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW


def score_confidence(
    signals: Mapping[str, float], model: EstimationModel
) -> tuple[float, ConfidenceBand, tuple[Factor, ...], tuple[str, ...]]:
    """Confidence = 0.6·coverage + 0.4·sample_adequacy (deterministic, reproducible)."""
    expected = model.expected_signals
    present = sum(1 for name in expected if name in signals)
    coverage = round(present / len(expected), 4) if expected else 1.0

    hist = model.historical.get("duration")
    samples = hist.samples if hist is not None else 0
    sample_adequacy = (
        round(min(samples, model.confidence_full_samples) / model.confidence_full_samples, 4)
        if model.confidence_full_samples > 0
        else 0.0
    )

    value = round(_COVERAGE_WEIGHT * coverage + _SAMPLE_WEIGHT * sample_adequacy, 4)
    band = _band_for(value)
    factors = (
        Factor(
            name="signal_coverage",
            value=coverage,
            weight=_COVERAGE_WEIGHT,
            contribution=round(_COVERAGE_WEIGHT * coverage, 6),
        ),
        Factor(
            name="sample_adequacy",
            value=sample_adequacy,
            weight=_SAMPLE_WEIGHT,
            contribution=round(_SAMPLE_WEIGHT * sample_adequacy, 6),
        ),
    )
    trace = (
        f"signal coverage = {present}/{len(expected)} = {coverage}",
        f"historical sample adequacy = {sample_adequacy} (samples={samples}, full={model.confidence_full_samples})",
        f"confidence = {_COVERAGE_WEIGHT}·{coverage} + {_SAMPLE_WEIGHT}·{sample_adequacy} = {value} → band {band.value}",
    )
    return value, band, factors, trace
