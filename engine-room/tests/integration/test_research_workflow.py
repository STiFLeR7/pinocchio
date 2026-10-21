"""Capability Program 3 -- the autonomous research workflow (end-to-end).

Proves Nexus autonomously executes a complete research workflow using only its existing control
plane: Context -> Knowledge -> Planning -> Orchestration -> Harness -> Runtime -> Execution ->
Validation -> Recovery -> Reflection -> Knowledge -> Research Brief. Covers the coordinator
(Milestone 1), Planning decomposition (2), multi-runtime execution (3), Validation (4), failure
injection + recovery (5), and Reflection/Knowledge feedback (6), plus replay and determinism.
"""

from __future__ import annotations

import pathlib

from nexus_execution.signals import TerminalOutcome
from nexus_research import ResearchCoordinator, recovery_outlook, reference_topic
from nexus_validation.vocabulary import ValidationDecision
from tests.unit.nexus_recovery.helpers import execution_result
from tests.unit.nexus_recovery.helpers import report as make_report

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


# --- Milestone 1/2: coordinator drives the full pipeline; Planning decomposes -- #


def test_research_invokes_every_engine_and_decomposes_into_phases() -> None:
    session = ResearchCoordinator().research(reference_topic(), run="e1")
    assert set(session.timeline.distinct_engines()) == _ALL_ENGINES
    # Planning (not a special-case planner) produced one Work Package per research phase.
    assert len(session.brief.work_packages) == 4
    assert any("gather-sources" in w for w in session.brief.work_packages)
    assert any("generate-briefing" in w for w in session.brief.work_packages)
    assert session.succeeded


def test_research_produces_an_actionable_validated_brief() -> None:
    brief = ResearchCoordinator().research(reference_topic(), run="e2").brief
    assert brief.is_validated  # Milestone 4: every output passed Validation
    assert brief.source_artifacts  # sources gathered
    assert brief.briefing_artifacts  # briefing produced
    assert brief.evidence_refs  # Validation evidence collected
    assert brief.is_actionable
    assert brief.findings  # Reflection surfaced a reusable pattern
    assert brief.knowledge_item_ids  # Knowledge persisted it


def test_default_topic_is_the_reference_topic() -> None:
    session = ResearchCoordinator().research(run="e3")
    assert "Model Context Protocol" in session.brief.subject


def test_coordinator_uses_the_shipped_adapter_registry_by_default() -> None:
    from nexus_runtime_adapters import build_default_adapter_registry

    registry = build_default_adapter_registry()
    coordinator = ResearchCoordinator(adapters=registry)
    assert coordinator.adapters is registry
    assert ResearchCoordinator().adapters.identities() == _RUNTIMES


# --- Milestone 3: multi-runtime execution ----------------------------------- #


def test_research_executes_across_every_runtime() -> None:
    sessions = ResearchCoordinator().research_across(reference_topic(), run="m3")
    assert tuple(s.runtime_identity for s in sessions) == _RUNTIMES
    for s in sessions:
        assert s.succeeded
        assert s.brief.is_validated
        assert s.brief.work_packages == sessions[0].brief.work_packages  # same research plan


def test_multi_runtime_briefings_differ_only_in_artifacts() -> None:
    sessions = ResearchCoordinator().research_across(reference_topic(), run="m3b")
    briefs = {s.runtime_identity: s.brief for s in sessions}
    # Same governance decisions everywhere; only the produced briefing artifact differs.
    assert briefs["claude-code"].validation_decisions == briefs["shell"].validation_decisions
    assert any("main.py" in a for a in briefs["claude-code"].briefing_artifacts)
    assert any("output.txt" in a for a in briefs["shell"].briefing_artifacts)


def test_runtime_selection_uses_the_existing_deterministic_funnel() -> None:
    coordinator = ResearchCoordinator()
    assert coordinator.select_runtime({}).chosen.identity == "claude-code"
    assert (
        coordinator.select_runtime({"preferred_runtimes": ("gemini-cli",)}).chosen.identity
        == "gemini-cli"
    )
    assert (
        coordinator.select_runtime({}, candidate_ids=("gemini-cli", "shell")).chosen.identity
        == "gemini-cli"
    )


# --- Milestone 5: failure injection + recovery ------------------------------ #


def test_failed_research_run_recovers_via_retry() -> None:
    session = ResearchCoordinator().research(reference_topic(), run="m5", fail=True)
    assert session.brief.validation_decisions == ("failed", "failed", "failed", "failed")
    assert session.brief.recovery_decisions == ("retry", "retry", "retry", "retry")
    assert session.brief.recovered is True
    assert not session.succeeded


def test_recovery_offers_retry_escalation_and_resume() -> None:
    # Failure injection at the Recovery engine: the research pipeline reaches every governed
    # continuation (retry -> escalate as budget exhausts; resume on partial progress).
    report = make_report(decision=ValidationDecision.FAILED)
    result = execution_result(
        outcome=TerminalOutcome.FAILED,
        exit_status=1,
        error_class="provider-failure",
        error_owner="provider",
    )
    outlook = recovery_outlook(report, result)
    assert (
        outlook.on_first_failure,
        outlook.on_exhausted_retries,
        outlook.on_partial_progress,
    ) == (
        "retry",
        "escalate",
        "resume",
    )


# --- replay + determinism --------------------------------------------------- #


def test_research_replays_from_the_log_without_information_loss() -> None:
    session = ResearchCoordinator().research(reference_topic(), run="rp")
    replay = session.replay()
    assert replay.total_events == len(session.events)
    assert replay.event_ids == tuple(e.identifier for e in session.events)


def test_research_is_byte_identical_across_repeat_runs() -> None:
    s1 = ResearchCoordinator().research(reference_topic(), run="det")
    s2 = ResearchCoordinator().research(reference_topic(), run="det")
    assert [(e.identifier, e.type, e.payload) for e in s1.events] == [
        (e.identifier, e.type, e.payload) for e in s2.events
    ]


# --- Milestone 6: knowledge feedback (INV-26) ------------------------------- #


def test_second_run_consumes_knowledge_from_the_first() -> None:
    coordinator = ResearchCoordinator()
    topic = reference_topic()
    first = coordinator.research(topic, run="k1")
    assert first.knowledge_consumed == 0  # nothing learned yet
    second = coordinator.research(
        topic, run="k2", knowledge_repositories=first.knowledge_repositories
    )
    assert second.knowledge_consumed >= 1  # run 2's Planning read run 1's Knowledge


def test_knowledge_feedback_crosses_a_runtime_switch() -> None:
    # Knowledge written on Claude informs a later Gemini run's Planning (learning is runtime-free).
    coordinator = ResearchCoordinator()
    topic = reference_topic()
    first = coordinator.research(topic, runtime_identity="claude-code", run="x1")
    second = coordinator.research(
        topic,
        runtime_identity="gemini-cli",
        run="x2",
        knowledge_repositories=first.knowledge_repositories,
    )
    assert second.knowledge_consumed >= 1


# --- structural guardrail: research is a consumer, imported by nothing ------- #

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _package_source(package: str) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in (_REPO_ROOT / package).glob("*.py"))


def test_no_engine_imports_the_research_layer() -> None:
    for package in ("nexus_planning", "nexus_recovery", "nexus_knowledge", "nexus_workflows"):
        assert "nexus_research" not in _package_source(package)
