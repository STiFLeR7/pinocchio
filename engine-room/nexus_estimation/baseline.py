"""The versioned estimation model — historical statistics and weights as versioned inputs.

Determinism requires that any historical statistics used are **versioned inputs**, not
ambient state that drifts over time (task: "If historical statistics are used, they must be
versioned inputs"). :class:`EstimationModel` captures every tunable — the scoring weights,
band thresholds, duration/cost baselines, and historical means — behind a ``version`` string.
Same model version + same signals → same estimate, forever; a change is a new version, itself
deterministic. The model is immutable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from nexus_estimation.vocabulary import ComplexityBand, ResourceClass


@dataclass(frozen=True, slots=True)
class HistoricalStat:
    """A versioned historical statistic (a recorded fact, not a live read)."""

    mean: float
    samples: int


@dataclass(frozen=True, slots=True)
class EstimationModel:
    """The immutable, versioned scoring model (weights + historical baselines)."""

    version: str
    complexity_weights: Mapping[str, float]
    # Ascending ``(inclusive_lower_bound, band)`` thresholds over the complexity score.
    complexity_bands: tuple[tuple[float, ComplexityBand], ...]
    duration_base_seconds: float
    duration_per_complexity: float
    cost_per_second: float
    currency: str
    expected_signals: tuple[str, ...]
    confidence_full_samples: int
    historical: Mapping[str, HistoricalStat] = field(default_factory=dict)


#: The default deterministic model (version 1). Weights and baselines are illustrative but
#: fixed: they are inputs, and any change ships as a new version.
DEFAULT_MODEL = EstimationModel(
    version="1",
    complexity_weights={
        "objective_size": 0.02,
        "skill_count": 1.5,
        "input_count": 1.0,
        "output_count": 1.0,
        "constraint_count": 0.5,
        "dependency_count": 2.0,
        "resource_count": 0.5,
        "repo_file_count": 0.001,
    },
    complexity_bands=(
        (0.0, ComplexityBand.TRIVIAL),
        (5.0, ComplexityBand.LOW),
        (15.0, ComplexityBand.MODERATE),
        (30.0, ComplexityBand.HIGH),
        (60.0, ComplexityBand.VERY_HIGH),
    ),
    duration_base_seconds=60.0,
    duration_per_complexity=30.0,
    cost_per_second=0.0004,
    currency="USD",
    expected_signals=(
        "objective_size",
        "skill_count",
        "input_count",
        "output_count",
        "constraint_count",
        "dependency_count",
    ),
    confidence_full_samples=30,
    historical={},
)

RESOURCE_CLASS_FOR_BAND: dict[ComplexityBand, ResourceClass] = {
    ComplexityBand.TRIVIAL: ResourceClass.MINIMAL,
    ComplexityBand.LOW: ResourceClass.MINIMAL,
    ComplexityBand.MODERATE: ResourceClass.STANDARD,
    ComplexityBand.HIGH: ResourceClass.INTENSIVE,
    ComplexityBand.VERY_HIGH: ResourceClass.INTENSIVE,
}
