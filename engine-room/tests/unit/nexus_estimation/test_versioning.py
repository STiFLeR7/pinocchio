"""Version stability & versioned inputs (``nexus_estimation.baseline``).

Determinism requires historical statistics to be versioned inputs: a different model version
yields a different — but still deterministic — result, and the estimate carries the version.
"""

from __future__ import annotations

from dataclasses import replace

from nexus_estimation import DEFAULT_MODEL, EstimationInputs, build_estimation
from nexus_estimation.baseline import HistoricalStat
from nexus_infra import build_infrastructure
from tests.unit.nexus_estimation.fixtures import SAMPLE_SIGNALS


def _estimate(model):
    ec = build_estimation(build_infrastructure(), model=model, now=lambda: "t")
    return ec.engine.estimate(EstimationInputs("wp", "cor", SAMPLE_SIGNALS), persist=False)


def test_same_version_same_signals_is_identical() -> None:
    a = _estimate(DEFAULT_MODEL)
    b = _estimate(DEFAULT_MODEL)
    assert a == b
    assert a.model_version == "1"


def test_different_model_version_changes_result_deterministically() -> None:
    v2 = replace(
        DEFAULT_MODEL,
        version="2",
        complexity_weights={**DEFAULT_MODEL.complexity_weights, "dependency_count": 5.0},
    )
    a = _estimate(DEFAULT_MODEL)
    b = _estimate(v2)
    assert b.complexity.score != a.complexity.score  # weights changed
    assert b.model_version == "2"
    assert b.complexity.identity != a.complexity.identity  # identity encodes the version


def test_historical_baseline_is_a_versioned_input() -> None:
    with_history = replace(
        DEFAULT_MODEL, version="1h", historical={"duration": HistoricalStat(mean=300.0, samples=30)}
    )
    base = _estimate(DEFAULT_MODEL)
    blended = _estimate(with_history)
    assert blended.duration.seconds != base.duration.seconds  # blended toward the historical mean
    assert blended.confidence.value > base.confidence.value  # samples raise confidence
