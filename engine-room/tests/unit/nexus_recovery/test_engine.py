"""Unit tests for the Recovery Engine — decisions, events, determinism, persistence."""

from __future__ import annotations

from nexus_execution.signals import TerminalOutcome
from nexus_infra import InMemoryObservability, build_infrastructure
from nexus_recovery import (
    FailureCategory,
    RecoveryDecision,
    RecoveryEngine,
    RecoveryPolicy,
    RetryPolicy,
    build_recovery,
)
from nexus_recovery.vocabulary import RecoveryStage
from nexus_runtime.events import FixedTimestampSource
from nexus_validation.vocabulary import ValidationDecision
from tests.unit.nexus_recovery.helpers import checkpoint_ref, execution_result, report
from tests.unit.nexus_validation.helpers import artifact_event


def _infra():  # type: ignore[no-untyped-def]
    return build_infrastructure(observability=InMemoryObservability())


def _recovery_events(infra):  # type: ignore[no-untyped-def]
    return [e for e in infra.event_store.read_all() if e.type.startswith("recovery.")]


def _failed_result():  # type: ignore[no-untyped-def]
    return execution_result(
        outcome=TerminalOutcome.FAILED, error_class="provider-failure", error_owner="provider"
    )


# --- decision paths --------------------------------------------------------- #


def test_passed_verdict_completes() -> None:
    ctx = build_recovery(_infra(), timestamps=FixedTimestampSource())
    plan = ctx.engine.recover(report(decision=ValidationDecision.PASSED), execution_result())
    assert plan.decision is RecoveryDecision.COMPLETE
    assert plan.stage is RecoveryStage.COMPLETE
    assert plan.recovered is True
    assert plan.failure_category is FailureCategory.NONE
    assert plan.escalation_target is None


def test_runtime_failure_retries() -> None:
    ctx = build_recovery(_infra(), timestamps=FixedTimestampSource())
    plan = ctx.engine.recover(report(decision=ValidationDecision.FAILED), _failed_result())
    assert plan.decision is RecoveryDecision.RETRY
    assert plan.retry_eligible is True
    assert plan.attempts_used == 1
    assert plan.attempts_remaining == 2
    assert plan.checkpoint_ref is None


def test_partial_with_checkpoint_resumes() -> None:
    ctx = build_recovery(_infra(), timestamps=FixedTimestampSource())
    plan = ctx.engine.recover(
        report(decision=ValidationDecision.PARTIAL),
        execution_result(),
        checkpoint_ref=checkpoint_ref(),
    )
    assert plan.decision is RecoveryDecision.RESUME
    assert plan.resumable is True
    assert plan.checkpoint_ref == checkpoint_ref()


def test_requires_review_awaits_approval_with_target() -> None:
    ctx = build_recovery(_infra(), timestamps=FixedTimestampSource())
    plan = ctx.engine.recover(
        report(decision=ValidationDecision.REQUIRES_REVIEW), execution_result()
    )
    assert plan.decision is RecoveryDecision.AWAIT_APPROVAL
    assert plan.escalation_target == "operator"


def test_exhausted_retries_escalate() -> None:
    ctx = build_recovery(_infra(), timestamps=FixedTimestampSource())
    plan = ctx.engine.recover(
        report(decision=ValidationDecision.FAILED),
        _failed_result(),
        policy=RecoveryPolicy(retry=RetryPolicy(max_attempts=1)),
    )
    assert plan.decision is RecoveryDecision.ESCALATE
    assert plan.escalation_target == "operator"


def test_policy_fatal_category_aborts_and_emits_failed() -> None:
    infra = _infra()
    ctx = build_recovery(infra, timestamps=FixedTimestampSource())
    plan = ctx.engine.recover(
        report(decision=ValidationDecision.FAILED),
        _failed_result(),
        policy=RecoveryPolicy(abort_on=(FailureCategory.RUNTIME,)),
    )
    assert plan.decision is RecoveryDecision.ABORT
    assert plan.aborted is True
    assert "recovery.failed" in [e.type for e in _recovery_events(infra)]


# --- events ----------------------------------------------------------------- #


def test_emits_full_recovery_event_sequence() -> None:
    infra = _infra()
    ctx = build_recovery(infra, timestamps=FixedTimestampSource())
    ctx.engine.recover(report(decision=ValidationDecision.FAILED), _failed_result())
    types = [e.type for e in _recovery_events(infra)]
    assert types[0] == "recovery.started"
    assert types.count("recovery.rule_evaluated") == 6
    assert types[-2] == "recovery.decision_created"
    assert types[-1] == "recovery.completed"


def test_terminal_payload_carries_decision_and_signals() -> None:
    infra = _infra()
    ctx = build_recovery(infra, timestamps=FixedTimestampSource())
    ctx.engine.recover(report(decision=ValidationDecision.FAILED), _failed_result())
    completed = next(e for e in _recovery_events(infra) if e.type == "recovery.completed")
    assert completed.payload["decision"] == "retry"
    assert completed.payload["failure_category"] == "runtime"
    assert completed.payload["retry_eligible"] is True


# --- determinism ------------------------------------------------------------ #


def test_two_runs_produce_identical_plans_and_events() -> None:
    infra1, infra2 = _infra(), _infra()
    ctx1 = build_recovery(infra1, timestamps=FixedTimestampSource())
    ctx2 = build_recovery(infra2, timestamps=FixedTimestampSource())
    p1 = ctx1.engine.recover(report(decision=ValidationDecision.FAILED), _failed_result())
    p2 = ctx2.engine.recover(report(decision=ValidationDecision.FAILED), _failed_result())
    assert p1 == p2
    triples1 = [(e.identifier, e.type, e.payload) for e in _recovery_events(infra1)]
    triples2 = [(e.identifier, e.type, e.payload) for e in _recovery_events(infra2)]
    assert triples1 == triples2


# --- persistence ------------------------------------------------------------ #


def test_plan_is_persisted() -> None:
    ctx = build_recovery(_infra(), timestamps=FixedTimestampSource())
    plan = ctx.engine.recover(report(decision=ValidationDecision.PASSED), execution_result())
    assert ctx.repositories.plans.get(plan.identity) == plan


def test_engine_without_repositories_still_returns_plan() -> None:
    engine = RecoveryEngine(_infra(), timestamps=FixedTimestampSource())  # no repositories
    plan = engine.recover(report(decision=ValidationDecision.PASSED), execution_result())
    assert plan.decision is RecoveryDecision.COMPLETE


def test_plan_references_report_and_evidence_without_duplication() -> None:
    ctx = build_recovery(_infra(), timestamps=FixedTimestampSource())
    plan = ctx.engine.recover(report(decision=ValidationDecision.FAILED), _failed_result())
    assert plan.validation_report_ref.target_type == "validation_report"
    assert plan.reference().target_type == "recovery_plan"
    assert all(ref.target_type == "evidence" for ref in plan.triggering_evidence_refs)


# --- correlation ------------------------------------------------------------ #


def test_correlation_comes_from_the_report() -> None:
    ctx = build_recovery(_infra(), timestamps=FixedTimestampSource())
    plan = ctx.engine.recover(report(decision=ValidationDecision.PASSED), execution_result())
    assert plan.correlation_identifier == "cor-val"


def test_correlation_falls_back_to_event_log() -> None:
    ctx = build_recovery(_infra(), timestamps=FixedTimestampSource())
    plan = ctx.engine.recover(
        report(decision=ValidationDecision.PASSED, correlation=""),
        execution_result(),
        events=(artifact_event("a.py"),),
    )
    assert plan.correlation_identifier == "cor-val"


def test_correlation_falls_back_to_session_identity() -> None:
    ctx = build_recovery(_infra(), timestamps=FixedTimestampSource())
    plan = ctx.engine.recover(
        report(decision=ValidationDecision.PASSED, correlation=""), execution_result()
    )
    assert plan.correlation_identifier == plan.session_ref.identifier
