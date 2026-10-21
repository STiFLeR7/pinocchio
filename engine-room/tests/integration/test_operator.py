"""Productization Program 1 -- the Nexus Operator Experience (end-to-end).

Proves a human can operate Nexus as a complete control plane through one coherent
:class:`OperatorSession` without invoking engines directly: submit a Goal, monitor a unified
timeline, inspect every operational object, search persisted state, and review an aggregate
dashboard. Covers the operator session (Milestone 1), timeline (2), explorers (3), search (4), and
dashboard (5), plus replay and determinism.
"""

from __future__ import annotations

import pathlib

from nexus_briefings import operational_digest
from nexus_operator import GoalSubmission, OperatorSession, SearchDomain, reference_submission

_TIMELINE_PHASES = (
    "Context",
    "Knowledge",
    "Planning",
    "Runtime",
    "Execution",
    "Validation",
    "Recovery",
    "Reflection",
)


def _seeded_session() -> OperatorSession:
    op = OperatorSession()
    op.submit_goal(reference_submission())  # sub-1 (goal)
    op.submit_goal(  # sub-2 (goal)
        GoalSubmission(
            identifier="tune-perf",
            outcome="Improve request latency.",
            steps=("profile the hot path", "optimize the hot path"),
            knowledge_subject="performance tuning",
            scope_terms=("performance",),
        )
    )
    op.generate_briefing(operational_digest())  # sub-3 (briefing)
    op.submit_goal(  # sub-4 (goal, fails)
        GoalSubmission(
            identifier="risky",
            outcome="Attempt a risky change.",
            steps=("attempt the change",),
            knowledge_subject="risky work",
        ),
        fail=True,
    )
    return op


# --- Milestone 1: operator session ------------------------------------------ #


def test_operator_submits_goals_and_briefings_through_one_interface() -> None:
    op = _seeded_session()
    assert [r.submission_id for r in op.history.records] == ["sub-1", "sub-2", "sub-3", "sub-4"]
    assert [r.status for r in op.history.records] == [
        "completed",
        "completed",
        "completed",
        "failed",
    ]
    assert len(op.history.goals()) == 3
    assert len(op.history.briefings()) == 1


def test_default_goal_submission_is_the_reference() -> None:
    op = OperatorSession()
    assert op.knowledge_repositories is None  # nothing persisted before the first submission
    record = op.submit_goal()
    assert "feature" in record.title.lower()
    assert record.succeeded
    assert op.knowledge_repositories is not None  # the durable store now exists


# --- Milestone 2: operational timeline -------------------------------------- #


def test_timeline_shows_operator_phases_linked_to_persisted_evidence() -> None:
    op = _seeded_session()
    timeline = op.timeline("sub-1")
    assert timeline is not None
    assert timeline.phases() == _TIMELINE_PHASES
    # Every entry links back to the persisted event log; execution entries carry artifact evidence.
    assert timeline.total_events == len(op.history.get("sub-1").run.events)
    execution_entries = [e for e in timeline.entries if e.phase == "Execution"]
    assert execution_entries and all(e.evidence_refs for e in execution_entries)


def test_briefing_timeline_includes_a_briefings_phase() -> None:
    op = _seeded_session()
    timeline = op.timeline("sub-3")
    assert timeline is not None
    assert "Briefings" in timeline.phases()
    briefings_entry = next(e for e in timeline.entries if e.phase == "Briefings")
    assert briefings_entry.evidence_refs  # links to the validated briefing artifacts


def test_timeline_for_unknown_submission_is_none() -> None:
    assert OperatorSession().timeline("nope") is None


# --- Milestone 3: operational explorer -------------------------------------- #


def test_explorer_exposes_every_operational_entity_read_only() -> None:
    explorer = _seeded_session().explorer
    assert len(explorer.goals()) == 4
    assert len(explorer.plans()) == 4
    assert len(explorer.work_packages()) == 10  # 3 + 2 + 4 (briefing) + 1
    assert len(explorer.runtime_sessions()) == 10
    assert len(explorer.validation_reports()) == 10
    assert len(explorer.recovery_plans()) == 10
    assert len(explorer.reflection_reports()) == 4
    assert len(explorer.briefings()) == 1
    # Knowledge items accumulated across submissions with distinct subjects.
    assert len(explorer.knowledge_items()) >= 3


def test_explorer_navigates_goal_to_validation() -> None:
    explorer = _seeded_session().explorer
    goal = explorer.goal("goal-op-tune-perf-op2")
    assert goal is not None and goal.status == "completed"
    # The failed submission's work package reports a failed validation and a governed retry.
    failed = [v for v in explorer.validation_reports() if v.decision == "failed"]
    assert failed
    retried = [r for r in explorer.recovery_plans() if r.decision == "retry"]
    assert retried


def test_explorer_knowledge_items_come_from_the_durable_store() -> None:
    explorer = _seeded_session().explorer
    subjects = {item.identity for item in explorer.knowledge_items()}
    assert any("performance" in s for s in subjects)


# --- Milestone 4: deterministic search -------------------------------------- #


def test_search_is_deterministic_and_cross_domain() -> None:
    op = _seeded_session()
    latency = op.search("latency")
    assert latency.identifiers == ("goal-op-tune-perf-op2",)
    assert op.search("latency").hits == latency.hits  # deterministic

    failures = op.search("failed")
    assert {h.domain for h in failures.hits} == {SearchDomain.VALIDATION}

    digest = op.search("digest")
    assert any(h.domain is SearchDomain.BRIEFING for h in digest.hits)


def test_search_empty_query_returns_nothing() -> None:
    assert len(_seeded_session().search("   ")) == 0


# --- Milestone 5: operational dashboard ------------------------------------- #


def test_dashboard_aggregates_persisted_state() -> None:
    dashboard = _seeded_session().dashboard
    assert dashboard.running_workflows == 0  # synchronous execution: nothing in flight
    assert dashboard.completed_workflows == 3
    assert dashboard.failed_workflows == 1
    assert dashboard.validation_passed == 9
    assert dashboard.validation_failed == 1
    assert dict(dashboard.recovery_breakdown) == {"complete": 9, "retry": 1}
    assert dashboard.knowledge_items >= 3
    assert dashboard.briefings_generated == 1
    assert dashboard.briefings_publishable == 1
    assert dashboard.total_workflows == 4


# --- replay + determinism --------------------------------------------------- #


def test_submission_replays_from_the_log_without_information_loss() -> None:
    op = OperatorSession()
    record = op.submit_goal(reference_submission())
    replay = op.replay(record.submission_id)
    assert replay is not None
    assert replay.total_events == len(record.run.events)
    assert replay.event_ids == tuple(e.identifier for e in record.run.events)
    assert op.replay("nope") is None


def test_operator_runs_are_byte_identical_across_sessions() -> None:
    r1 = OperatorSession().submit_goal(reference_submission()).run
    r2 = OperatorSession().submit_goal(reference_submission()).run
    assert [(e.identifier, e.type, e.payload) for e in r1.events] == [
        (e.identifier, e.type, e.payload) for e in r2.events
    ]


# --- knowledge growth across submissions ------------------------------------ #


def test_knowledge_grows_and_is_consumed_across_submissions() -> None:
    op = OperatorSession()
    first = op.submit_goal(reference_submission())
    assert first.run.knowledge_consumed == 0
    second = op.submit_goal(reference_submission())
    assert second.run.knowledge_consumed >= 1  # later Planning consumed earlier Knowledge (INV-26)


# --- structural guardrail: operator is a consumer, imported by nothing ------- #

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _package_source(package: str) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in (_REPO_ROOT / package).glob("*.py"))


def test_no_engine_or_product_imports_the_operator_layer() -> None:
    for package in ("nexus_planning", "nexus_knowledge", "nexus_workflows", "nexus_briefings"):
        assert "nexus_operator" not in _package_source(package)
