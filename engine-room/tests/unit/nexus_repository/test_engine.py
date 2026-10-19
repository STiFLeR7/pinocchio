"""Engine behavior — one scan, one recorded fact, persistence, scanner version."""

from __future__ import annotations

from nexus_repository.events import REPOSITORY_PROFILED
from tests.unit.nexus_repository.fixtures import make_repo, wired


def test_profile_produces_one_fact_and_persists(tmp_path) -> None:
    infra, ri = wired()
    profile = ri.engine.profile(make_repo(tmp_path), correlation_identifier="cor-r")

    events = [e for e in infra.event_store.read_all() if e.type == REPOSITORY_PROFILED]
    assert len(events) == 1
    assert events[0].correlation_identifier == "cor-r"
    assert events[0].payload["profile"]["identity"] == profile.identity
    assert ri.repositories.profiles.get(profile.identity) == profile


def test_repeated_scan_is_idempotent_in_the_log(tmp_path) -> None:
    infra, ri = wired()
    root = make_repo(tmp_path)
    ri.engine.profile(root, correlation_identifier="cor-r")
    ri.engine.profile(root, correlation_identifier="cor-r")  # identical → idempotent, no error
    events = [e for e in infra.event_store.read_all() if e.type == REPOSITORY_PROFILED]
    assert len(events) == 1


def test_scanner_version_recorded(tmp_path) -> None:
    _, ri = wired()
    assert ri.engine.scanner_version == "1"
    assert ri.engine.profile(make_repo(tmp_path), persist=False).scanner_version == "1"
