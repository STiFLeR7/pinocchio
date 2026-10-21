"""Unit tests for the operator primitives (submission, history, analysis, timeline, search, dash)."""

from __future__ import annotations

from nexus_operator import (
    OPERATOR_CAPABILITY,
    GoalSubmission,
    SearchDomain,
    SessionHistory,
    SubmissionKind,
    build_dashboard,
    reference_submission,
    submission_request,
)
from nexus_operator.search import SearchHit, SearchResults, search

# --- submission builder (Milestone 1) --------------------------------------- #


def test_submission_declares_one_work_item_per_step() -> None:
    submission = reference_submission()
    request = submission_request(submission, run="u1")
    assert request.goal.identity == "goal-op-ship-feature-u1"
    assert tuple(item.key for item in request.work_items) == ("step-1", "step-2", "step-3")
    assert all(OPERATOR_CAPABILITY in item.capability_requirements for item in request.work_items)
    assert len(request.skills) == 3
    assert request.fail is False


def test_submission_failure_flag_selects_failing_path() -> None:
    request = submission_request(reference_submission(), run="u2", fail=True)
    assert request.fail is True


def test_custom_submission_carries_its_fields() -> None:
    submission = GoalSubmission(
        identifier="x",
        outcome="do x",
        steps=("a",),
        knowledge_subject="subject x",
        scope_terms=("s",),
    )
    request = submission_request(submission, run="u3")
    assert request.knowledge_subject == "subject x"
    assert request.work_items[0].objective == "a"


# --- history projections ---------------------------------------------------- #


def test_empty_history_is_empty() -> None:
    history = SessionHistory()
    assert len(history) == 0
    assert history.get("nope") is None
    assert history.goals() == ()
    assert history.briefings() == ()
    assert list(history) == []


# --- search over empty state (Milestone 4) ---------------------------------- #


def test_search_empty_query_returns_no_hits() -> None:
    results = search("   ", history=SessionHistory())
    assert len(results) == 0
    assert results.identifiers == ()


def test_search_over_empty_history_returns_no_hits() -> None:
    results = search("anything", history=SessionHistory(), knowledge=None)
    assert results.hits == ()


def test_search_results_group_by_domain() -> None:
    hits = (
        SearchHit(SearchDomain.KNOWLEDGE, "k1", "t", "s"),
        SearchHit(SearchDomain.GOAL, "g1", "t", "s"),
    )
    results = SearchResults(query="q", hits=hits)
    assert results.in_domain(SearchDomain.GOAL) == (hits[1],)
    assert results.in_domain(SearchDomain.VALIDATION) == ()


# --- dashboard over empty state (Milestone 5) ------------------------------- #


def test_dashboard_over_empty_state_is_all_zero() -> None:
    dashboard = build_dashboard(SessionHistory(), knowledge=None)
    assert dashboard.running_workflows == 0
    assert dashboard.completed_workflows == 0
    assert dashboard.failed_workflows == 0
    assert dashboard.validation_passed == 0
    assert dashboard.recovery_breakdown == ()
    assert dashboard.knowledge_items == 0
    assert dashboard.briefings_generated == 0
    assert dashboard.total_workflows == 0


# --- kinds ------------------------------------------------------------------ #


def test_submission_kinds() -> None:
    assert SubmissionKind.GOAL.value == "goal"
    assert SubmissionKind.BRIEFING.value == "briefing"
