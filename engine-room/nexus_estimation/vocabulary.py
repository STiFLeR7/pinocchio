"""Estimation vocabularies — the closed enumerations of the subsystem.

Estimation is a first-class Operations-plane subsystem (Constitution: "PROMOTE … Estimation
… to first-class … EI mathematically needs Estimation"; Estimation/Cost Intelligence *feeds
EI*). Its contract is a declared void (Constitution Object Model: "Estimation … Void"), so —
following the platform's own INV-07 discipline (freeze only when a second consumer needs the
shape) — its estimate types are **subsystem value objects**, not new frozen core contracts,
exactly as ``ValidationReport`` is a validation-layer object. Only the closed vocabularies
live here.
"""

from __future__ import annotations

from enum import StrEnum


class EstimateKind(StrEnum):
    """The five quantitative assessments Estimation owns (and only Estimation owns)."""

    COMPLEXITY = "complexity"
    DURATION = "duration"
    COST = "cost"
    CONFIDENCE = "confidence"
    RESOURCE = "resource"


class ComplexityBand(StrEnum):
    """A deterministic band over the complexity score (ascending difficulty)."""

    TRIVIAL = "trivial"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class ConfidenceBand(StrEnum):
    """A deterministic band over the confidence value."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ResourceClass(StrEnum):
    """The execution-footprint class an estimate projects."""

    MINIMAL = "minimal"
    STANDARD = "standard"
    INTENSIVE = "intensive"


# --- canonical Reference target_type strings ---------------------------------- #
ESTIMATION_REPORT_TARGET_TYPE = "estimation_report"
