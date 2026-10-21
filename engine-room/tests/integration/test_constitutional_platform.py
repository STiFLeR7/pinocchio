"""P12 — Constitutional Platform Integration & Readiness.

End-to-end validation that the P0-P11 constitutional subsystems operate as one deterministic platform.
No mocked constitutional stages: every engine is the real one, wired over a shared infrastructure.

The platform is validated as two composable, deterministic chains that together exercise every
constitutional capability (see docs/v2/P12_PLATFORM_READINESS_REPORT.md, Integration Matrix):

* the **grounded front-to-execution chain** — Intent → Engineering (+Estimation+Policy) → Context →
  Planning → Execution Actuation (which drives Orchestration + Runtime + Execution) — where each stage
  *consumes* its predecessor's output, with durable replay + restart; and
* the **incumbent back chain** (``nexus_workflows`` WorkflowCoordinator) — Context → Planning →
  Orchestration → Runtime → Execution → Validation → Recovery → Reflection → Knowledge — the proven
  path that reaches evidence-backed Knowledge.

That the two are not yet fused into a single Goal→Knowledge driver (and that full-pipeline durable
restart is unbuilt) is the platform's headline readiness finding — documented, not silently fixed.
"""

from __future__ import annotations

from nexus_context import ContextRequest, build_context_engineering
from nexus_core.contracts.enums import PolicyDecision
from nexus_engineering import build_engineering
from nexus_estimation import build_estimation
from nexus_execution.actuation import (
    ActuationControl,
    ActuationInputs,
    ActuationStatus,
    build_execution_actuation,
    reconstruct_execution_state,
)
from nexus_infra import build_durable_infrastructure, build_infrastructure
from nexus_intent import build_intent, request_from_text
from nexus_intent.events import INTENT_RESOLVED
from nexus_intent.model import IntentAnalysis
from nexus_planning import FixedTimestampSource, WorkItemSpec
from nexus_planning.grounded import PlanningInputs, build_grounded_planning
from nexus_policy import DecisionRequest, build_policy
from nexus_runtime_claude import ClaudeRuntimeAdapter, StubClaudeInvoker
from nexus_workflows import reconstruct
from nexus_workflows.coordinator import WorkflowCoordinator
from nexus_workflows.executor import PipelineExecutor
from nexus_workflows.pipeline import PipelineBuilder
from nexus_workflows.reference import reference_request
from tests.unit.nexus_execution.actuation.fixtures import item, make_plan, to_inputs, wired

_NOW = "2026-01-01T00:00:00Z"
_REQUEST = "fix the failing authentication bug in the auth module"
_WORK_ITEMS = (
    WorkItemSpec(key="a", objective="analyze auth", capability_requirements=("code_generation",)),
    WorkItemSpec(
        key="b",
        objective="fix auth",
        depends_on=("a",),
        capability_requirements=("code_generation",),
    ),
)


# --------------------------------------------------------------------------- #
# The grounded front-to-execution chain (real engines, one shared log)          #
# --------------------------------------------------------------------------- #


def _front(infra):
    """Understand → Reason → Contextualize → Plan over one infra; returns the recorded decisions + plan."""
    ir = build_intent(infra, now=lambda: _NOW)
    eng = build_engineering(infra, now=lambda: _NOW)
    est = build_estimation(infra, now=lambda: _NOW)
    pol = build_policy(infra, now=lambda: _NOW)
    context_engineering = build_context_engineering(infra, timestamps=FixedTimestampSource(_NOW))
    grounded_planning = build_grounded_planning(infra, timestamps=FixedTimestampSource(_NOW))

    analysis = ir.engine.resolve(request_from_text("req1", _REQUEST, correlation_identifier="cor1"))
    goal = analysis.goal
    strategy = eng.strategize_for_goal(goal, estimation_engine=est.engine, policy_engine=pol.engine)
    context = context_engineering.service.engineer(goal, ContextRequest()).package
    plan = grounded_planning.planner.plan(
        PlanningInputs(
            goal=goal,
            engineering_strategy=strategy,
            context_package=context,
            work_items=_WORK_ITEMS,
        )
    )
    return analysis, strategy, context, plan


def _actuate(infra, plan, *, control=None):
    """Execution Actuation drives the plan through Orchestration + Runtime + Execution."""
    actuation = build_execution_actuation(
        infra,
        adapter=ClaudeRuntimeAdapter(invoker=StubClaudeInvoker()),
        timestamps=FixedTimestampSource(_NOW),
    )
    return actuation.actuator.actuate(
        ActuationInputs(
            plan=plan.plan,
            execution_graph=plan.execution_graph,
            execution_strategy=plan.execution_strategy,
            work_packages=plan.work_packages,
            context_references=plan.context_references,
        ),
        control=control,
    )


def test_grounded_spine_participates_end_to_end() -> None:
    infra = build_infrastructure()
    analysis, strategy, context, plan = _front(infra)
    state = _actuate(infra, plan)

    # Each constitutional stage produced its artifact, consuming the prior stage's output.
    assert analysis.resolved and analysis.goal is not None  # Understand → Goal
    assert strategy.subject_identifier == analysis.goal.identity  # Reason (Goal → Strategy)
    assert context.identity  # Contextualize
    assert plan.plan.identity and plan.execution_graph.nodes  # Plan (consumes Strategy + Context)
    assert state.status is ActuationStatus.COMPLETED  # Coordinate + Execute + Actuate
    assert state.completed_nodes == ("node-a", "node-b")

    # Every front-spine subsystem emitted its fact onto the one shared log (Policy governs throughout).
    kinds = {event.type.split(".")[0] for event in infra.event_store.read_all()}
    for stage in (
        "intent",
        "estimation",
        "engineering",
        "policy",
        "planning",
        "runtime",
        "execution",
    ):
        assert stage in kinds, f"missing stage on the shared log: {stage}"


def test_grounded_spine_is_deterministic() -> None:
    def run_once():
        infra = build_infrastructure()
        analysis, strategy, _context, plan = _front(infra)
        state = _actuate(infra, plan)
        return analysis.goal.identity, strategy.identity, plan.plan.identity, state

    first = run_once()
    second = run_once()
    assert first == second  # identical Goal → Strategy → Plan → ExecutionState, no divergence


def test_grounded_spine_replays_from_the_durable_log(tmp_path) -> None:
    db = str(tmp_path / "spine.db")
    infra = build_durable_infrastructure(db)
    analysis, _strategy, _context, plan = _front(infra)
    state = _actuate(infra, plan)

    reopened = build_durable_infrastructure(db)
    events = reopened.event_store.read_all()
    # Understanding reconstructs from the log without re-understanding (INV-17).
    intent_event = next(e for e in events if e.type == INTENT_RESOLVED)
    assert IntentAnalysis.model_validate(intent_event.payload["analysis"]) == analysis
    # Execution state reconstructs exactly from the log (INV-13/14).
    assert reconstruct_execution_state(events, session_identity=state.identity) == state


def test_execution_actuation_restarts_over_the_durable_log(tmp_path) -> None:
    db = str(tmp_path / "restart.db")
    infra_before = build_durable_infrastructure(db)
    _analysis, _strategy, _context, plan = _front(infra_before)

    partial = _actuate(infra_before, plan, control=ActuationControl(stop_after=1))
    assert partial.status is ActuationStatus.PAUSED
    assert partial.completed_nodes == ("node-a",)  # interrupted after the entry node

    infra_after = build_durable_infrastructure(db)  # fresh engines over the reopened file
    resumed = _actuate(infra_after, plan)  # same plan — never rebuilt (INV-18)
    assert resumed.status is ActuationStatus.COMPLETED
    assert resumed.completed_nodes == ("node-a", "node-b")


# --------------------------------------------------------------------------- #
# The incumbent back chain — reaches evidence-backed Knowledge                   #
# --------------------------------------------------------------------------- #


def test_back_spine_reaches_knowledge_with_real_engines() -> None:
    pipeline = PipelineBuilder().build()
    run = WorkflowCoordinator(pipeline).run(reference_request(run="r1"))

    assert run.succeeded
    assert run.execution_outcomes and all(o == "completed" for o in run.execution_outcomes)
    assert run.validation_decisions  # Validation decided completion
    assert run.recovery_decisions  # Recovery decided continuation
    assert run.reflection_ref.identifier  # Reflection produced a report
    assert run.knowledge_item_ids  # Knowledge recorded (evidence-backed, INV-24)

    engines = set(run.timeline.distinct_engines())
    for engine in (
        "context_engineering",
        "planning",
        "orchestration",
        "harness",
        "runtime",
        "execution",
        "validation",
        "recovery",
        "reflection",
        "knowledge",
    ):
        assert engine in engines, f"back-spine engine did not participate: {engine}"


def test_back_spine_is_deterministic_and_replays() -> None:
    executor = PipelineExecutor(PipelineBuilder().build())
    run1 = executor.execute(reference_request(run="r1"))
    run2 = PipelineExecutor(PipelineBuilder().build()).execute(reference_request(run="r1"))

    # Byte-identical event streams across independent runs.
    assert [(e.identifier, e.type, e.payload) for e in run1.events] == [
        (e.identifier, e.type, e.payload) for e in run2.events
    ]
    # Replay reconstructs the whole history from the log with no information loss.
    replay = executor.replay()
    assert replay.total_events == len(run1.events)
    assert replay.event_ids == tuple(e.identifier for e in run1.events)


def test_failure_propagates_to_recovery_without_accepting_unvalidated_knowledge() -> None:
    run = WorkflowCoordinator(PipelineBuilder().build()).run(reference_request(fail=True))
    assert not run.succeeded
    assert all(o == "failed" for o in run.execution_outcomes)  # execution reports failure
    assert all(d == "failed" for d in run.validation_decisions)  # Validation declines completion
    assert all(
        d == "retry" for d in run.recovery_decisions
    )  # Recovery decides continuation, bounded
    assert run.reflection_candidates  # Reflection still proposes a lesson.
    assert not run.knowledge_item_ids  # Failed outcomes cannot become accepted guidance.
    assert any(event.type == "knowledge.candidate_rejected" for event in run.events)


def test_knowledge_learned_in_one_run_feeds_a_second() -> None:
    first_pipeline = PipelineBuilder().build()
    run1 = WorkflowCoordinator(first_pipeline).run(reference_request(run="r1"))
    assert run1.knowledge_consumed == 0  # nothing to learn from yet

    # Share only the Knowledge store (learning flows across time via the record — INV-26).
    second_pipeline = PipelineBuilder(
        knowledge_repositories=first_pipeline.knowledge.repositories
    ).build()
    run2 = WorkflowCoordinator(second_pipeline).run(reference_request(run="r2"))
    assert run2.knowledge_consumed >= 1  # run one's Knowledge grounded run two's Planning


# --------------------------------------------------------------------------- #
# Governance, checkpoint/approval boundaries, and event-lineage integrity       #
# --------------------------------------------------------------------------- #


def test_policy_engine_governs_and_fails_closed() -> None:
    infra = build_infrastructure()
    policy = build_policy(infra, now=lambda: _NOW)

    # A governed action with no matching policy falls to the default, which denies (INV-30).
    verdict = policy.engine.evaluate(
        DecisionRequest(
            action_class="unmapped-governed-action", correlation_identifier="cor1", governed=True
        )
    )
    assert verdict.default_applied
    assert verdict.decision is PolicyDecision.DENY
    assert not verdict.allowed
    assert verdict.reasoning_trace  # every governed decision is explainable (INV-31)
    # The evaluation is recorded on the log — governance authorizes and audits (INV-29).
    assert any(e.type.startswith("policy.") for e in infra.event_store.read_all())


def test_checkpoint_and_approval_boundaries_are_honored() -> None:
    # Checkpoint boundary: entering and completing emit their events; the checkpoint is recorded.
    infra, ctx = wired()
    checkpointed = ctx.actuator.actuate(to_inputs(make_plan((item("a", is_checkpoint=True),))))
    assert checkpointed.checkpoint_state == ("node-a",)
    checkpoint_types = [
        e.type for e in infra.event_store.read_all() if e.type.startswith("execution.")
    ]
    assert "execution.checkpoint_entered" in checkpoint_types
    assert "execution.checkpoint_completed" in checkpoint_types

    # Approval boundary: an ungranted gate pauses the node; a granted gate lets it proceed.
    gated = make_plan((item("a"), item("b", depends_on=("a",), requires_approval=True)))
    _infra_wait, ctx_wait = wired()
    waiting = ctx_wait.actuator.actuate(to_inputs(gated))
    assert "node-b" in waiting.waiting_nodes and "node-b" not in waiting.completed_nodes

    _infra_grant, ctx_grant = wired()
    granted = ctx_grant.actuator.actuate(to_inputs(gated, granted_gates=("node-b",)))
    assert granted.status is ActuationStatus.COMPLETED
    assert granted.approval_received == ("node-b",)


def test_event_lineage_has_one_producer_per_event_and_reconstructs() -> None:
    infra = build_infrastructure()
    _analysis, _strategy, _context, plan = _front(infra)
    _actuate(infra, plan)
    events = infra.event_store.read_all()

    identifiers = [e.identifier for e in events]
    assert len(identifiers) == len(set(identifiers))  # no duplicated producer of the same fact
    assert all(e.producer for e in events)  # every event names exactly one producer
    assert all(e.correlation_identifier for e in events)  # every cross-subsystem fact is correlated

    timeline = reconstruct(events)  # lineage reconstructs the full history, no loss
    assert timeline.total_events == len(events)
    assert timeline.event_ids == tuple(identifiers)
    assert timeline.event_types == tuple(e.type for e in events)
