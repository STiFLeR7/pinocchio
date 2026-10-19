"""Deterministic scoring rules — the estimation engine's pure arithmetic core.

Every scorer is a **pure function** of the signals and the versioned model: no randomness, no
clock, no time-varying heuristic, no reasoning, no LLM. Identical signals + model version →
identical score. Each scorer returns its value plus the explainability trail (contributing
:class:`~nexus_estimation.model.Factor` s and a human-readable reasoning trace, INV-31).
"""

from __future__ import annotations

from collections.abc import Mapping

from nexus_estimation.baseline import RESOURCE_CLASS_FOR_BAND, EstimationModel
from nexus_estimation.model import Factor
from nexus_estimation.vocabulary import ComplexityBand, ResourceClass


def _band_for(score: float, bands: tuple[tuple[float, ComplexityBand], ...]) -> ComplexityBand:
    chosen = bands[0][1]
    for lower, band in bands:
        if score >= lower:
            chosen = band
        else:
            break
    return chosen


def score_complexity(
    signals: Mapping[str, float], model: EstimationModel
) -> tuple[float, ComplexityBand, tuple[Factor, ...], tuple[str, ...]]:
    """Weighted-sum complexity over the model's weighted signals (deterministic, explainable)."""
    factors: list[Factor] = []
    total = 0.0
    for name in sorted(model.complexity_weights):
        weight = model.complexity_weights[name]
        value = float(signals.get(name, 0.0))
        contribution = round(weight * value, 6)
        total += contribution
        factors.append(Factor(name=name, value=value, weight=weight, contribution=contribution))
    score = round(total, 4)
    band = _band_for(score, model.complexity_bands)
    trace = (
        *(f"{f.name}: {f.value} * {f.weight} = {f.contribution}" for f in factors),
        f"complexity score = {score} -> band {band.value}",
    )
    return score, band, tuple(factors), trace


def estimate_duration(
    complexity_score: float, model: EstimationModel
) -> tuple[float, tuple[Factor, ...], tuple[str, ...]]:
    """Duration = base + per-complexity * score, blended with the versioned historical mean."""
    raw = model.duration_base_seconds + model.duration_per_complexity * complexity_score
    factors = [
        Factor(
            name="duration_base",
            value=model.duration_base_seconds,
            weight=1.0,
            contribution=model.duration_base_seconds,
        ),
        Factor(
            name="duration_per_complexity",
            value=complexity_score,
            weight=model.duration_per_complexity,
            contribution=round(model.duration_per_complexity * complexity_score, 6),
        ),
    ]
    trace = [
        f"raw duration = {model.duration_base_seconds} + {model.duration_per_complexity} * {complexity_score} = {round(raw, 4)}s"
    ]
    seconds = round(raw, 4)
    hist = model.historical.get("duration")
    if hist is not None and hist.samples > 0 and model.confidence_full_samples > 0:
        blend = min(hist.samples, model.confidence_full_samples) / model.confidence_full_samples
        seconds = round(raw * (1 - blend) + hist.mean * blend, 4)
        factors.append(
            Factor(
                name="historical_duration_mean",
                value=hist.mean,
                weight=blend,
                contribution=round(hist.mean * blend, 6),
            )
        )
        trace.append(
            f"blended with historical mean {hist.mean}s (samples={hist.samples}, weight={round(blend, 4)}) → {seconds}s"
        )
    return seconds, tuple(factors), tuple(trace)


def estimate_cost(
    duration_seconds: float, signals: Mapping[str, float], model: EstimationModel
) -> tuple[float, str, tuple[Factor, ...], tuple[str, ...]]:
    """Cost = duration * cost rate (runtime rate signal if declared, else the model rate)."""
    rate = float(signals.get("runtime_cost_per_second", model.cost_per_second))
    amount = round(duration_seconds * rate, 6)
    factors = (
        Factor(name="duration_seconds", value=duration_seconds, weight=rate, contribution=amount),
        Factor(name="cost_rate", value=rate, weight=1.0, contribution=rate),
    )
    trace = (f"cost = {duration_seconds}s * {rate}/{model.currency}/s = {amount} {model.currency}",)
    return amount, model.currency, factors, trace


def estimate_resource(
    complexity_score: float,
    band: ComplexityBand,
    signals: Mapping[str, float],
    model: EstimationModel,
) -> tuple[ResourceClass, dict[str, object], tuple[Factor, ...], tuple[str, ...]]:
    """Execution footprint: a resource class from the complexity band + a deterministic profile."""
    resource_class = RESOURCE_CLASS_FOR_BAND[band]
    concurrency = max(1, int(signals.get("work_package_count", 1.0)))
    profile: dict[str, object] = {
        "footprint_score": complexity_score,
        "memory_class": resource_class.value,
        "concurrency_hint": concurrency,
    }
    factors = (
        Factor(
            name="footprint_score",
            value=complexity_score,
            weight=1.0,
            contribution=complexity_score,
        ),
        Factor(
            name="concurrency_hint",
            value=float(concurrency),
            weight=1.0,
            contribution=float(concurrency),
        ),
    )
    trace = (
        f"complexity band {band.value} → resource class {resource_class.value}; concurrency hint {concurrency}",
    )
    return resource_class, profile, factors, trace
