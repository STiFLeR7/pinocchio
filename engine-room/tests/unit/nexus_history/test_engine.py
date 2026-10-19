"""Engine behavior — one recorded fact, persistence, idempotency, projector version, RI/EI seams."""

from __future__ import annotations

from nexus_history import EXECUTION_HISTORY_PROJECTED, HistoryQuery
from tests.unit.nexus_history.fixtures import seed_episode, wired


def _history_events(infra):
    return [e for e in infra.event_store.read_all() if e.type == EXECUTION_HISTORY_PROJECTED]


def test_profile_produces_one_fact_and_persists() -> None:
    infra, hist = wired()
    seed_episode(infra, "op-1")
    profile = hist.engine.profile(HistoryQuery(correlation_identifier="op-1"))

    events = _history_events(infra)
    assert len(events) == 1
    assert events[0].correlation_identifier == "op-1"
    assert events[0].payload["profile"]["identity"] == profile.identity
    assert hist.repositories.profiles.get(profile.identity) == profile


def test_repeated_projection_is_idempotent_in_the_log() -> None:
    infra, hist = wired()
    seed_episode(infra, "op-1")
    q = HistoryQuery(correlation_identifier="op-1")
    first = hist.engine.profile(q)
    second = hist.engine.profile(q)  # its own prior fact is excluded → identical → idempotent
    assert first.identity == second.identity
    assert len(_history_events(infra)) == 1


def test_projector_version_recorded() -> None:
    infra, hist = wired()
    assert hist.engine.projector_version == "1"
    assert hist.engine.profile(persist=False).projector_version == "1"


def test_repository_seam_exposes_prior_executions() -> None:
    infra, hist = wired()
    seed_episode(infra, "op-1")
    seam = hist.engine.profile(persist=False).repository_seam()
    assert seam.available and seam.prior_executions == 1
