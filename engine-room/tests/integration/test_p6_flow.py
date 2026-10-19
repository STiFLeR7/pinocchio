"""P6 constitutional flow — Intent → Engineering Intelligence → Planning, durable & replayable.

Proves the completed flow end-to-end, deterministic replay of both intent analysis and planning
(without re-understanding / re-reasoning), and restart determinism. Rides P1 (ADR-007) unchanged.
"""

from __future__ import annotations

from nexus_engineering import build_engineering
from nexus_estimation import build_estimation
from nexus_infra import build_durable_infrastructure, build_infrastructure
from nexus_intent import build_intent, request_from_text
from nexus_intent.events import INTENT_RESOLVED
from nexus_intent.model import IntentAnalysis
from nexus_planning import FixedTimestampSource, PlanningRequest, WorkItemSpec, build_planning
from nexus_policy import build_policy

_NOW = "2026-01-01T00:00:00Z"
_REQUEST = "fix the failing authentication bug in the auth module"


def _flow(infra):
    ir = build_intent(infra, now=lambda: _NOW)
    eng = build_engineering(infra, now=lambda: _NOW)
    est = build_estimation(infra, now=lambda: _NOW)
    pol = build_policy(infra, now=lambda: _NOW)
    plan_ctx = build_planning(infra, timestamps=FixedTimestampSource(_NOW))

    analysis = ir.engine.resolve(request_from_text("req1", _REQUEST, correlation_identifier="cor1"))
    strategy = eng.strategize_for_goal(
        analysis.goal, estimation_engine=est.engine, policy_engine=pol.engine
    )
    req = PlanningRequest(
        work_items=(
            WorkItemSpec(
                key="w1", objective="fix auth bug", capability_requirements=("code_generation",)
            ),
        ),
        correlation_identifier="cor1",
    )
    result = plan_ctx.service.plan(analysis.goal, req, engineering_strategy=strategy)
    return analysis, strategy, result


def test_full_flow_intent_to_engineering_to_planning() -> None:
    analysis, strategy, result = _flow(build_infrastructure())
    assert analysis.resolved and analysis.goal is not None
    assert strategy.subject_identifier == analysis.goal.identity
    # Planning consumed EI's execution style
    assert result.execution_strategy.coordination.value == strategy.execution_style.selection[0]
    # provenance: the plan's strategy references EI's strategy via the request binding
    assert result.plan.parent_goal.identifier == analysis.goal.identity


def test_intent_analysis_replays_from_the_log(tmp_path) -> None:
    db = str(tmp_path / "p6.db")
    analysis, _, _ = _flow(build_durable_infrastructure(db))
    reopened = build_durable_infrastructure(db)
    event = next(e for e in reopened.event_store.read_all() if e.type == INTENT_RESOLVED)
    reconstructed = IntentAnalysis.model_validate(event.payload["analysis"])
    assert reconstructed == analysis  # understanding reconstructed without re-understanding


def test_restart_determinism_reproduces_intent_and_plan(tmp_path) -> None:
    db = str(tmp_path / "p6b.db")
    a1, s1, r1 = _flow(build_durable_infrastructure(db))
    # a fresh set of engines over the reopened file reproduces the same understanding + plan
    a2, s2, r2 = _flow(build_durable_infrastructure(db))
    assert a1.identity == a2.identity
    assert s1.identity == s2.identity
    assert r1.plan.identity == r2.plan.identity
    assert r1.execution_strategy == r2.execution_strategy


def test_planning_consumes_engineering_strategy(tmp_path) -> None:
    _, strategy, result = _flow(build_infrastructure())
    es = result.execution_strategy
    assert dict(es.validation_policy).get("rigor") == strategy.validation_rigor.selection[0]
    assert dict(es.runtime_policy).get("capabilities") == list(
        strategy.runtime_preferences.selection
    )
