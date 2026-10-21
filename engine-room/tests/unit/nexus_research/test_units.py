"""Unit tests for nexus_research — topic, workflow request, brief projection, recovery outlook.

These exercise the pure, fast parts of the research consumer: the topic decomposition, the
platform ``WorkflowRequest`` the topic builds (no planning logic), the ``ResearchBrief``
properties, and the recovery outlook driven through the *existing* Recovery engine.
"""

from __future__ import annotations

from nexus_execution.signals import TerminalOutcome
from nexus_research import (
    RESEARCH_CAPABILITY,
    RESEARCH_PHASES,
    RecoveryOutlook,
    ResearchBrief,
    ResearchTopic,
    ResearchWorkflow,
    recovery_outlook,
    reference_topic,
)
from nexus_validation.vocabulary import ValidationDecision
from tests.unit.nexus_recovery.helpers import execution_result
from tests.unit.nexus_recovery.helpers import report as make_report

# -- topic ------------------------------------------------------------------ #


def test_reference_topic_is_the_mcp_example() -> None:
    topic = reference_topic()
    assert "Model Context Protocol" in topic.subject
    assert topic.question.endswith("technical briefing.")
    assert topic.phases == RESEARCH_PHASES


def test_phases_are_the_four_research_stages() -> None:
    keys = [p.key for p in RESEARCH_PHASES]
    assert keys == ["gather-sources", "summarize-evidence", "compare-findings", "generate-briefing"]


def test_phase_objective_interpolates_subject() -> None:
    phase = RESEARCH_PHASES[0]
    assert phase.objective("X") == "gather primary and secondary sources on X"


# -- workflow request (Milestone 2 decomposition input) --------------------- #


def test_request_declares_one_work_item_per_phase() -> None:
    request = ResearchWorkflow(reference_topic()).request(run="u1")
    assert tuple(w.key for w in request.work_items) == tuple(p.key for p in RESEARCH_PHASES)
    for item in request.work_items:
        assert item.capability_requirements == (RESEARCH_CAPABILITY,)
    assert request.goal.identity == "goal-research-u1"
    assert request.knowledge_subject == reference_topic().knowledge_subject
    assert request.scope == "research-goal-research-u1"


def test_request_fail_flag_selects_failure_path() -> None:
    assert ResearchWorkflow(reference_topic()).request(fail=True).fail is True
    assert ResearchWorkflow(reference_topic()).request().fail is False


def test_request_scope_falls_back_to_corpus_key_without_scope_terms() -> None:
    topic = ResearchTopic(
        subject="S", question="Q?", knowledge_subject="ks", corpus_key="the-corpus", scope_terms=()
    )
    request = ResearchWorkflow(topic).request()
    assert request.goal.scope.included == ("the-corpus",)


def test_workflow_exposes_its_topic() -> None:
    topic = reference_topic()
    assert ResearchWorkflow(topic).topic is topic


# -- brief projection properties -------------------------------------------- #


def _brief(**overrides: object) -> ResearchBrief:
    base: dict[str, object] = {
        "subject": "S",
        "question": "Q?",
        "runtime_identity": "claude-code",
        "work_packages": ("wp-a",),
        "source_artifacts": ("wp-a-gather-sources-main.py",),
        "briefing_artifacts": ("wp-a-generate-briefing-main.py",),
        "evidence_refs": ("ev-1",),
        "validation_decisions": ("passed",),
        "recovery_decisions": ("complete",),
        "findings": ("f",),
        "knowledge_item_ids": ("ki-1",),
        "knowledge_consumed": 0,
    }
    base.update(overrides)
    return ResearchBrief(**base)  # type: ignore[arg-type]


def test_brief_is_validated_only_when_all_passed() -> None:
    assert _brief().is_validated is True
    assert _brief(validation_decisions=("passed", "failed")).is_validated is False
    assert _brief(validation_decisions=()).is_validated is False


def test_brief_recovered_when_any_decision_is_not_complete() -> None:
    assert _brief().recovered is False
    assert _brief(recovery_decisions=("complete", "retry")).recovered is True


def test_brief_is_actionable_requires_validation_and_a_briefing() -> None:
    assert _brief().is_actionable is True
    assert _brief(briefing_artifacts=()).is_actionable is False
    assert _brief(validation_decisions=("failed",)).is_actionable is False


# -- recovery outlook (Milestone 5, existing engine) ------------------------ #


def _failed_pair() -> tuple[object, object]:
    report = make_report(decision=ValidationDecision.FAILED)
    result = execution_result(
        outcome=TerminalOutcome.FAILED,
        exit_status=1,
        error_class="provider-failure",
        error_owner="provider",
    )
    return report, result


def test_recovery_outlook_reaches_retry_escalate_resume() -> None:
    report, result = _failed_pair()
    outlook = recovery_outlook(report, result)  # type: ignore[arg-type]
    assert outlook.on_first_failure == "retry"
    assert outlook.on_exhausted_retries == "escalate"
    assert outlook.on_partial_progress == "resume"
    assert outlook.covers_all_governed_continuations is True


def test_recovery_outlook_property_is_strict() -> None:
    assert RecoveryOutlook("retry", "escalate", "resume").covers_all_governed_continuations
    assert not RecoveryOutlook("retry", "retry", "resume").covers_all_governed_continuations


def test_recovery_outlook_accepts_an_explicit_checkpoint() -> None:
    from nexus_core.contracts.base import Reference

    report, result = _failed_pair()
    ckpt = Reference(target_type="checkpoint", identifier="cp-explicit")
    outlook = recovery_outlook(report, result, checkpoint_ref=ckpt)  # type: ignore[arg-type]
    assert outlook.on_partial_progress == "resume"
