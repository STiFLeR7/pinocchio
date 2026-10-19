"""Onboarding flow — read-only stage checks (no network, no external sends).

Covers the safety-relevant invariants: fail-closed on missing owner ids (A-001 surfaced),
runtime + back-compat alias resolution, and the pure helpers. DB-backed stages
(memory/scheduler) are exercised by the live onboarding run, not here.
"""

from __future__ import annotations

from nexus import onboarding as ob
from nexus.config import DiscordConfig, EmailConfig, NexusSettings, OpenRouterConfig
from nexus.onboarding import Status


def test_present_helper() -> None:
    assert ob._present("x")
    assert not ob._present("")
    assert not ob._present("   ")
    assert ob._present([1])
    assert not ob._present([])
    assert ob._present(5)
    assert not ob._present(0)
    assert not ob._present(None)


def test_config_stage_fails_closed_without_owner_ids() -> None:
    """A-001: empty owner ids must surface as a FAIL (startup fails closed)."""
    settings = NexusSettings(discord=DiscordConfig(token="t", guild_id=1, owner_ids=[]))
    stage = ob.stage_configuration(settings)
    owner = next(c for c in stage.checks if "Owner ids" in c.name)
    assert owner.status is Status.FAIL
    assert stage.status is Status.FAIL


def test_config_stage_owner_ids_present_ok() -> None:
    settings = NexusSettings(
        discord=DiscordConfig(token="t", guild_id=1, owner_ids=[111222333]),
        openrouter=OpenRouterConfig(api_key="k"),
        email=EmailConfig(smtp_host="h", from_address="f@x", username="u", password="p"),
    )
    stage = ob.stage_configuration(settings)
    owner = next(c for c in stage.checks if "Owner ids" in c.name)
    assert owner.status is Status.OK


def test_runtime_stage_resolves_all_runtimes_and_legacy_alias() -> None:
    stage = ob.stage_runtime(NexusSettings())
    by_name = {c.name: c for c in stage.checks}
    assert by_name["runtime 'nexus'"].status is Status.OK
    assert by_name["runtime 'gemini'"].status is Status.OK
    assert by_name["runtime 'claude'"].status is Status.OK
    assert by_name["legacy alias 'hermes'"].status is Status.OK


def test_summarize_counts() -> None:
    stages = [
        ob.Stage("a", [ob.Check("x", Status.OK)]),
        ob.Stage("b", [ob.Check("y", Status.FAIL)]),
        ob.Stage("c", [ob.Check("z", Status.WARN)]),
    ]
    assert ob.summarize(stages) == {"ok": 1, "warn": 1, "fail": 1}
