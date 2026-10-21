"""``nexus_estimation`` — the constitutional Estimation Foundation (P4).

The **single owner of quantitative execution assessment**: given immutable facts, the
:class:`~nexus_estimation.engine.EstimationEngine` produces a deterministic, explainable
:class:`~nexus_estimation.model.EstimationReport` — complexity, duration, cost, confidence, and
resource estimates, each with a value, a reasoning trace, contributing factors, a confidence,
and a deterministic identity. Estimation is a first-class Operations-plane subsystem that
**feeds Engineering Intelligence** (Constitution: "Estimation/Cost Intelligence … feeds EI");
its contract is a declared void, so its estimates are subsystem value objects (INV-07
discipline), not new frozen core contracts.

It **estimates only** — it makes no decision, plans nothing, chooses no runtime or skill,
classifies no intent, schedules nothing, approves nothing, recovers nothing, validates nothing,
and **invokes no LLM**. Estimation is a pure function of (immutable signals, versioned model):
identical input → identical estimate → identical replay. It reuses the P1/P2/P3 substrate and
integrates through additive composition (:func:`build_estimation`).
"""

from __future__ import annotations

from nexus_estimation.baseline import (
    DEFAULT_MODEL,
    EstimationModel,
    HistoricalStat,
)
from nexus_estimation.composition import EstimationContext, build_estimation
from nexus_estimation.confidence import score_confidence
from nexus_estimation.engine import EstimationEngine
from nexus_estimation.events import ESTIMATION_ESTIMATED
from nexus_estimation.model import (
    ComplexityEstimate,
    ConfidenceEstimate,
    CostEstimate,
    DurationEstimate,
    Estimate,
    EstimationInputs,
    EstimationReport,
    Factor,
    ResourceEstimate,
)
from nexus_estimation.observability import EstimationObservability
from nexus_estimation.persistence import EstimationRepositories, build_estimation_repositories
from nexus_estimation.rules import (
    estimate_cost,
    estimate_duration,
    estimate_resource,
    score_complexity,
)
from nexus_estimation.signals import merge_signals, signals_from_work_package
from nexus_estimation.vocabulary import (
    ComplexityBand,
    ConfidenceBand,
    EstimateKind,
    ResourceClass,
)

__version__ = "2.5.0"

__all__ = [
    "DEFAULT_MODEL",
    "ESTIMATION_ESTIMATED",
    "ComplexityBand",
    "ComplexityEstimate",
    "ConfidenceBand",
    "ConfidenceEstimate",
    "CostEstimate",
    "DurationEstimate",
    "Estimate",
    "EstimateKind",
    "EstimationContext",
    "EstimationEngine",
    "EstimationInputs",
    "EstimationModel",
    "EstimationObservability",
    "EstimationReport",
    "EstimationRepositories",
    "Factor",
    "HistoricalStat",
    "ResourceClass",
    "ResourceEstimate",
    "__version__",
    "build_estimation",
    "build_estimation_repositories",
    "estimate_cost",
    "estimate_duration",
    "estimate_resource",
    "merge_signals",
    "score_complexity",
    "score_confidence",
    "signals_from_work_package",
]
