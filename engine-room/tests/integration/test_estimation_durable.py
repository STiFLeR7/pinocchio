"""Durable estimation integration (ADR-007 through P1) — the P4 acceptance gate.

Proves durable persistence, replay reconstruction of estimates from the log, identical
estimates across restart, and version stability across restart. Rides P1 unchanged.
"""

from __future__ import annotations

from nexus_estimation import EstimationInputs, EstimationReport, build_estimation
from nexus_estimation.events import ESTIMATION_ESTIMATED
from nexus_infra import build_durable_infrastructure
from tests.unit.nexus_estimation.fixtures import SAMPLE_SIGNALS

_NOW = "2026-01-01T00:00:00Z"


def _inputs(subject="wp-1", correlation="cor-1"):
    return EstimationInputs(subject, correlation, SAMPLE_SIGNALS)


def test_estimation_event_is_durable(tmp_path) -> None:
    db = str(tmp_path / "est.db")
    ctx = build_estimation(build_durable_infrastructure(db), now=lambda: _NOW)
    ctx.engine.estimate(_inputs())

    reopened = build_durable_infrastructure(db)
    events = [e for e in reopened.event_store.read_all() if e.type == ESTIMATION_ESTIMATED]
    assert len(events) == 1
    assert events[0].correlation_identifier == "cor-1"


def test_replay_reconstructs_estimates_from_the_log(tmp_path) -> None:
    db = str(tmp_path / "est.db")
    ctx = build_estimation(build_durable_infrastructure(db), now=lambda: _NOW)
    original = ctx.engine.estimate(_inputs())

    reopened = build_durable_infrastructure(db)
    event = next(e for e in reopened.event_store.read_all() if e.type == ESTIMATION_ESTIMATED)
    reconstructed = EstimationReport.model_validate(event.payload["report"])
    assert reconstructed == original  # full report reconstructed without re-computation


def test_identical_estimates_across_restart(tmp_path) -> None:
    db = str(tmp_path / "est.db")
    before = build_estimation(build_durable_infrastructure(db), now=lambda: _NOW).engine.estimate(
        _inputs("wp-x", "cor-x"), persist=False
    )
    after = build_estimation(build_durable_infrastructure(db), now=lambda: _NOW).engine.estimate(
        _inputs("wp-x", "cor-x"), persist=False
    )
    assert before == after  # determinism survives restart (pure function of signals + model)


def test_version_stable_across_restart(tmp_path) -> None:
    db = str(tmp_path / "est.db")
    ctx = build_estimation(build_durable_infrastructure(db), now=lambda: _NOW)
    report = ctx.engine.estimate(_inputs())
    reopened = build_estimation(build_durable_infrastructure(db), now=lambda: _NOW)
    assert reopened.engine.model_version == ctx.engine.model_version
    assert reopened.engine.estimate(_inputs(), persist=False).identity == report.identity
