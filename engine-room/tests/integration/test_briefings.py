"""Product Program 1 -- the Nexus Briefings system (end-to-end).

Proves Nexus generates production-quality operational briefings using only its existing control
plane: Brief Request -> Context -> Knowledge -> Planning -> Execution -> Validation -> Recovery ->
Reflection -> Knowledge Update -> Brief Composer -> Rendered Brief. Covers the coordinator
(Milestone 1), configuration-driven brief types (2), composition from validated evidence (3),
multi-format rendering (4), and Reflection/Knowledge feedback (5), plus multi-runtime generation,
replay, and determinism.
"""

from __future__ import annotations

import json
import pathlib

from nexus_briefings import (
    BriefComposer,
    BriefingCoordinator,
    operational_digest,
    project_brief,
    research_brief,
)

_ALL_ENGINES = {
    "context_engineering",
    "knowledge",
    "planning",
    "orchestration",
    "harness",
    "runtime",
    "execution",
    "validation",
    "recovery",
    "reflection",
}
_RUNTIMES = ("claude-code", "gemini-cli", "shell")


# --- Milestone 1/2: coordinator drives the full pipeline; config-driven ------ #


def test_briefing_invokes_every_engine_and_decomposes_into_sections() -> None:
    session = BriefingCoordinator().generate(operational_digest(), run="e1")
    assert set(session.timeline.distinct_engines()) == _ALL_ENGINES
    # Planning (not a special-case planner) produced one Work Package per declared section.
    assert len(session.brief.sections) == 4
    assert tuple(s.key for s in session.brief.sections) == (
        "survey-signals",
        "summarize-health",
        "highlight-incidents",
        "compose-digest",
    )
    assert session.succeeded


def test_default_brief_type_is_the_operational_digest() -> None:
    session = BriefingCoordinator().generate(run="e2")
    assert session.brief.title == "Morning Operational Digest"


def test_coordinator_uses_the_shipped_adapter_registry_by_default() -> None:
    from nexus_runtime_adapters import build_default_adapter_registry

    registry = build_default_adapter_registry()
    coordinator = BriefingCoordinator(adapters=registry)
    assert coordinator.adapters is registry
    assert BriefingCoordinator().adapters.identities() == _RUNTIMES


# --- Milestone 3: composed from validated evidence, never raw output --------- #


def test_brief_is_composed_from_validated_evidence_only() -> None:
    brief = BriefingCoordinator().generate(operational_digest(), run="e3").brief
    assert brief.is_validated  # every section passed Validation (INV-20)
    assert brief.is_publishable
    for section in brief.sections:
        assert section.validated_artifacts  # a validated deliverable
        assert section.evidence_refs  # Validation evidence substantiating it
        # Milestone 3: the raw runtime output stream is never composed into a brief.
        assert not any("captured-output" in artifact for artifact in section.validated_artifacts)
    assert brief.findings  # Reflection surfaced a reusable pattern
    assert brief.knowledge_item_ids  # Knowledge persisted it


def test_absent_sections_are_withheld_when_the_run_lacks_them() -> None:
    # Compose an operational digest over a research run: none of the digest's sections ran, so the
    # composer withholds them all (its per-section gate, no raw fallback).
    research_run = BriefingCoordinator().generate(research_brief(), run="e4").run
    brief = BriefComposer().compose(operational_digest(), "claude-code", research_run)
    assert not brief.is_validated
    assert all(section.decision == "absent" for section in brief.sections)
    assert all(not section.validated_artifacts for section in brief.sections)


# --- Milestone 4: rendering (markdown / html / json) ------------------------ #


def test_session_renders_every_supported_format() -> None:
    session = BriefingCoordinator().generate(operational_digest(), run="e5")
    markdown = session.render("markdown")
    html = session.render("html")
    payload = json.loads(session.render("json"))
    assert "Morning Operational Digest" in markdown
    assert html.startswith("<!DOCTYPE html>")
    assert payload["brief_type"] == "operational-digest"
    assert len(payload["sections"]) == 4


# --- multi-runtime generation ----------------------------------------------- #


def test_briefing_generates_across_every_runtime() -> None:
    sessions = BriefingCoordinator().generate_across(research_brief(), run="m4")
    assert tuple(s.runtime_identity for s in sessions) == _RUNTIMES
    for s in sessions:
        assert s.succeeded
        assert s.brief.is_validated
        # Same briefing plan everywhere; only the produced artifact differs by runtime.
        assert tuple(sec.key for sec in s.brief.sections) == tuple(
            sec.key for sec in sessions[0].brief.sections
        )


def test_runtime_selection_uses_the_existing_deterministic_funnel() -> None:
    coordinator = BriefingCoordinator()
    assert coordinator.select_runtime({}).chosen.identity == "claude-code"
    assert coordinator.select_runtime({"preferred_runtimes": ("shell",)}).chosen.identity == "shell"
    assert (
        coordinator.select_runtime({}, candidate_ids=("gemini-cli", "shell")).chosen.identity
        == "gemini-cli"
    )


# --- validation integration + recovery -------------------------------------- #


def test_failed_generation_withholds_the_brief_and_recovers() -> None:
    session = BriefingCoordinator().generate(operational_digest(), run="m5", fail=True)
    assert session.brief.validation_decisions == ("failed", "failed", "failed", "failed")
    assert session.brief.recovery_decisions == ("retry", "retry", "retry", "retry")
    assert session.brief.recovered is True
    assert not session.brief.is_publishable
    # No validated deliverable survives a failed generation (nothing unvalidated is composed).
    assert all(not section.validated_artifacts for section in session.brief.sections)
    assert not session.succeeded


# --- replay + determinism --------------------------------------------------- #


def test_briefing_replays_from_the_log_without_information_loss() -> None:
    session = BriefingCoordinator().generate(project_brief(), run="rp")
    replay = session.replay()
    assert replay.total_events == len(session.events)
    assert replay.event_ids == tuple(e.identifier for e in session.events)


def test_briefing_is_byte_identical_across_repeat_runs() -> None:
    s1 = BriefingCoordinator().generate(operational_digest(), run="det")
    s2 = BriefingCoordinator().generate(operational_digest(), run="det")
    assert s1.render("json") == s2.render("json")
    assert [(e.identifier, e.type, e.payload) for e in s1.events] == [
        (e.identifier, e.type, e.payload) for e in s2.events
    ]


# --- Milestone 5: knowledge feedback (INV-26) ------------------------------- #


def test_second_generation_consumes_knowledge_from_the_first() -> None:
    coordinator = BriefingCoordinator()
    bt = operational_digest()
    first = coordinator.generate(bt, run="k1")
    assert first.knowledge_consumed == 0  # nothing learned yet
    second = coordinator.generate(bt, run="k2", knowledge_repositories=first.knowledge_repositories)
    assert second.knowledge_consumed >= 1  # generation 2's Planning read generation 1's Knowledge


def test_knowledge_feedback_crosses_a_runtime_switch() -> None:
    coordinator = BriefingCoordinator()
    bt = research_brief()
    first = coordinator.generate(bt, runtime_identity="claude-code", run="x1")
    second = coordinator.generate(
        bt,
        runtime_identity="gemini-cli",
        run="x2",
        knowledge_repositories=first.knowledge_repositories,
    )
    assert second.knowledge_consumed >= 1


# --- structural guardrail: briefings is a consumer, imported by nothing ------ #

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _package_source(package: str) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in (_REPO_ROOT / package).glob("*.py"))


def test_no_engine_imports_the_briefings_layer() -> None:
    for package in ("nexus_planning", "nexus_recovery", "nexus_knowledge", "nexus_workflows"):
        assert "nexus_briefings" not in _package_source(package)
