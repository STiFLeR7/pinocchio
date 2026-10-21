"""Estimation value objects — the immutable, explainable estimates Estimation produces.

Every estimate is a frozen :class:`~nexus_core.contracts.base.ValueObject` (value equality,
serializable, storable, durable) carrying, per the task's required shape: a **value**, a
**reasoning trace**, its **contributing factors**, a **confidence**, and a **deterministic
identity**. These are subsystem value objects (the same pattern as ``ValidationReport``), not
frozen core contracts — the estimation contract is a declared void (INV-07 discipline).

Estimation *produces* these; it makes no decision (INV-02: the estimate-consuming engineering
decision is Engineering Intelligence's). Identical inputs → identical estimate → identical id.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar

from nexus_core.contracts.base import Struct, ValueObject
from nexus_estimation.vocabulary import (
    ComplexityBand,
    ConfidenceBand,
    EstimateKind,
    ResourceClass,
)


class Factor(ValueObject):
    """One contributing factor of an estimate — a signal, its weight, and its contribution."""

    name: str
    value: float
    weight: float
    contribution: float


class Estimate(ValueObject):
    """Common shape of every estimate: identity, subject, confidence, factors, trace, version."""

    identity: str
    subject_identifier: str
    confidence: float
    factors: tuple[Factor, ...]
    reasoning_trace: tuple[str, ...]
    model_version: str


class ComplexityEstimate(Estimate):
    """The projected complexity of the work (a dimensionless score + a band)."""

    KIND: ClassVar[EstimateKind] = EstimateKind.COMPLEXITY
    score: float
    band: ComplexityBand


class DurationEstimate(Estimate):
    """The projected wall-clock duration, in seconds."""

    KIND: ClassVar[EstimateKind] = EstimateKind.DURATION
    seconds: float


class CostEstimate(Estimate):
    """The projected monetary cost, in the model's currency."""

    KIND: ClassVar[EstimateKind] = EstimateKind.COST
    amount: float
    currency: str


class ConfidenceEstimate(Estimate):
    """The meta-estimate: how much to trust the other estimates (a value + a band)."""

    KIND: ClassVar[EstimateKind] = EstimateKind.CONFIDENCE
    value: float
    band: ConfidenceBand


class ResourceEstimate(Estimate):
    """The projected execution footprint / resource profile."""

    KIND: ClassVar[EstimateKind] = EstimateKind.RESOURCE
    resource_class: ResourceClass
    profile: Struct


class EstimationReport(ValueObject):
    """The immutable bundle of all five estimates for one subject (deterministic identity)."""

    identity: str
    subject_identifier: str
    correlation_identifier: str
    model_version: str
    complexity: ComplexityEstimate
    duration: DurationEstimate
    cost: CostEstimate
    confidence: ConfidenceEstimate
    resource: ResourceEstimate
    timestamp: str = ""


@dataclass(frozen=True, slots=True)
class EstimationInputs:
    """The immutable factual inputs to one estimation (never mutable state, never AI opinions).

    ``signals`` are extracted numeric facts (work-package metadata, dependency-graph counts,
    repository metrics, versioned historical statistics, runtime capabilities, declared
    constraints) — see :mod:`nexus_estimation.signals`. The engine is a pure function of
    ``signals`` and the versioned model.
    """

    subject_identifier: str
    correlation_identifier: str
    signals: Mapping[str, float] = field(default_factory=dict)

    def normalized(self) -> dict[str, Any]:
        """A deterministic, JSON-safe view of the signals (sorted) for identity hashing."""
        return {name: self.signals[name] for name in sorted(self.signals)}
