"""Unit tests for the briefing product primitives (brief types, workflow, composer, renderers)."""

from __future__ import annotations

import json

import pytest

from nexus_briefings import (
    BRIEF_CATALOG,
    BRIEFING_CAPABILITY,
    Brief,
    BriefSectionView,
    BriefType,
    architecture_brief,
    brief_type,
    operational_digest,
    project_brief,
    render,
    render_html,
    render_json,
    render_markdown,
    research_brief,
)
from nexus_briefings.brieftype import BriefSection
from nexus_briefings.composer import _at, _is_raw_output, _node, _section_view
from nexus_briefings.renderers import SUPPORTED_FORMATS
from nexus_briefings.workflow import BriefingWorkflow

# --- brief types (Milestone 2: configuration-driven catalogue) -------------- #


def test_catalogue_exposes_the_four_supported_products() -> None:
    assert set(BRIEF_CATALOG) == {
        "operational-digest",
        "research-brief",
        "architecture-brief",
        "project-brief",
    }
    assert brief_type("operational-digest").title == "Morning Operational Digest"


def test_every_brief_type_has_four_sections_and_a_compose_step() -> None:
    for factory in (operational_digest, research_brief, architecture_brief, project_brief):
        bt = factory()
        assert isinstance(bt, BriefType)
        assert len(bt.sections) == 4
        assert any(section.key.startswith(("compose", "generate")) for section in bt.sections)


def test_brief_type_resolver_rejects_unknown_product() -> None:
    with pytest.raises(KeyError):
        brief_type("no-such-brief")


def test_section_objective_fills_the_subject() -> None:
    section = BriefSection("k", "H", "summarize {subject}")
    assert section.objective("the system") == "summarize the system"


# --- workflow (Milestone 1/2: declares work, does not plan) ----------------- #


def test_workflow_declares_one_work_item_per_section() -> None:
    bt = operational_digest()
    request = BriefingWorkflow(bt).request(run="u1")
    assert BriefingWorkflow(bt).brief_type is bt
    assert tuple(item.key for item in request.work_items) == tuple(s.key for s in bt.sections)
    assert request.goal.identity == "goal-brief-operational-digest-u1"
    assert all(BRIEFING_CAPABILITY in item.capability_requirements for item in request.work_items)
    assert len(request.skills) == 4
    assert request.fail is False


def test_workflow_failure_flag_selects_the_failing_path() -> None:
    request = BriefingWorkflow(project_brief()).request(run="u2", fail=True)
    assert request.fail is True


# --- composer helpers (Milestone 3) ----------------------------------------- #


def test_raw_output_marker_is_excluded() -> None:
    assert _is_raw_output("rts-...-captured-output") is True
    assert _is_raw_output("wp-...-main.py") is False


def test_node_extraction_handles_labelled_and_bare() -> None:
    assert _node("validation:node-survey-signals") == "node-survey-signals"
    assert _node("node-bare") == "node-bare"


def test_decision_lookup_defaults_to_unknown_out_of_range() -> None:
    assert _at(("passed",), 0) == "passed"
    assert _at((), 3) == "unknown"


def test_absent_node_yields_an_empty_withheld_section() -> None:
    view = _section_view(BriefSection("missing", "Missing", "do {subject}"), None)
    assert view.decision == "absent"
    assert view.validated is False
    assert view.validated_artifacts == ()
    assert view.recovery_decision == "none"


# --- document projections --------------------------------------------------- #


def _section(
    decision: str, artifacts: tuple[str, ...] = ("a",), rec: str = "complete"
) -> BriefSectionView:
    return BriefSectionView(
        key="k",
        heading="H",
        decision=decision,
        validated_artifacts=artifacts,
        evidence_refs=("e1", "e2"),
        recovery_decision=rec,
    )


def _brief(sections: tuple[BriefSectionView, ...], findings: tuple[str, ...] = ("f",)) -> Brief:
    return Brief(
        brief_type="operational-digest",
        title="Morning Operational Digest",
        subject="ops",
        runtime_identity="claude-code",
        sections=sections,
        findings=findings,
        knowledge_item_ids=("ki-1",),
        knowledge_consumed=0,
    )


def test_validated_publishable_brief() -> None:
    brief = _brief((_section("passed"), _section("passed")))
    assert brief.is_validated is True
    assert brief.is_publishable is True
    assert brief.recovered is False
    assert brief.validation_decisions == ("passed", "passed")


def test_failed_brief_is_not_validated_and_records_recovery() -> None:
    brief = _brief((_section("failed", artifacts=(), rec="retry"),))
    assert brief.is_validated is False
    assert brief.is_publishable is False
    assert brief.recovered is True
    assert brief.recovery_decisions == ("retry",)


def test_validated_without_deliverable_is_not_publishable() -> None:
    brief = _brief((_section("passed", artifacts=()),))
    assert brief.is_validated is True
    assert brief.is_publishable is False
    assert brief.sections[0].is_present is False


def test_empty_brief_is_not_validated() -> None:
    assert _brief(()).is_validated is False


# --- renderers (Milestone 4) ------------------------------------------------ #


def test_markdown_renders_headings_status_and_findings() -> None:
    md = render_markdown(_brief((_section("passed"),)))
    assert "# Morning Operational Digest" in md
    assert "PUBLISHABLE" in md
    assert "- f" in md
    assert "Consumed: 0" in md


def test_markdown_reports_withheld_and_missing_findings() -> None:
    md = render_markdown(_brief((_section("failed", artifacts=(), rec="retry"),), findings=()))
    assert "withheld (failed)" in md
    assert "WITHHELD" in md
    assert "none surfaced" in md


def test_markdown_marks_validated_without_deliverable() -> None:
    md = render_markdown(_brief((_section("passed", artifacts=()),)))
    assert "no deliverable" in md


def test_html_renders_email_document() -> None:
    html = render_html(_brief((_section("passed"),)))
    assert html.startswith("<!DOCTYPE html>")
    assert "Morning Operational Digest" in html
    assert "claude-code" in html


def test_html_handles_missing_findings() -> None:
    html = render_html(_brief((_section("passed"),), findings=()))
    assert "<li>none</li>" in html


def test_json_is_canonical_and_round_trips() -> None:
    brief = _brief((_section("passed"),))
    payload = json.loads(render_json(brief))
    assert payload["brief_type"] == "operational-digest"
    assert payload["sections"][0]["decision"] == "passed"


def test_render_dispatcher_supports_every_format() -> None:
    brief = _brief((_section("passed"),))
    assert set(SUPPORTED_FORMATS) == {"markdown", "html", "json"}
    for fmt in SUPPORTED_FORMATS:
        assert render(brief, fmt)


def test_render_dispatcher_rejects_unknown_format() -> None:
    with pytest.raises(ValueError, match="unsupported briefing format"):
        render(_brief((_section("passed"),)), "pdf")
