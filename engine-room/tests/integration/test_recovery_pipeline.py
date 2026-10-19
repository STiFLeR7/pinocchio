"""Milestone 5 — end-to-end Execution → Validation → Recovery integration (deterministic).

Extends the validation pipeline with the Recovery Engine:

    RuntimeIntake → RM (Ready) → Execution Engine → Execution Result
        → Validation Engine → Validation Report
        → Recovery Engine → Recovery Plan → Event Store / Persistence

Proves the governed continuation is decided from the validated outcome alone (Complete for a
clean corroborated run; Retry when Claude errors; Resume from a checkpoint when validation is
Partial), that recovery events share the operation's correlation and only *append* to the log
(Runtime, Execution, and Validation events are untouched), that identical runs yield identical
plans, and — structurally — that Runtime, Execution, and Validation do not depend on Recovery
(recovery is strictly downstream).
"""

from __future__ import annotations

import pathlib

from nexus_core.contracts.base import Reference
from nexus_execution import build_execution
from nexus_execution.signals import TerminalOutcome
from nexus_infra import InMemoryObservability, build_infrastructure
from nexus_recovery import RecoveryDecision, build_recovery
from nexus_runtime import FixedTimestampSource, build_runtime
from nexus_runtime_claude import ClaudeRuntimeAdapter, StubClaudeInvoker
from nexus_validation import ValidationDecision, build_validation
from tests.unit.nexus_runtime.helpers import intake, preparation_request


def _run_pipeline(*, fail: bool = False, corroborate: bool = True, checkpoint: str | None = None):  # type: ignore[no-untyped-def]
    infra = build_infrastructure(observability=InMemoryObservability())
    ts = FixedTimestampSource()
    runtime = build_runtime(infra, timestamps=ts)
    adapter = ClaudeRuntimeAdapter(invoker=StubClaudeInvoker(fail=fail))
    runtime.manager.register_runtime(adapter.descriptor())
    itk = intake(candidates=("claude-code",), required=("code_generation",))
    session = runtime.manager.prepare(preparation_request(itk)).sessions[0]

    result = build_execution(infra, timestamps=ts).engine.execute(
        session, adapter, itk.work_package
    )

    all_events = tuple(infra.event_store.read_all())
    validation = build_validation(infra, timestamps=ts)
    # Withholding the event log from validation removes independent corroboration → Partial.
    report = validation.engine.validate(
        result, itk.work_package, events=all_events if corroborate else ()
    )

    pre_recovery_events = tuple(infra.event_store.read_all())
    recovery = build_recovery(infra, timestamps=ts)
    plan = recovery.engine.recover(
        report,
        result,
        events=pre_recovery_events,
        checkpoint_ref=Reference(target_type="checkpoint", identifier=checkpoint)
        if checkpoint
        else None,
    )
    return infra, result, report, plan, pre_recovery_events, recovery


# --- decision paths --------------------------------------------------------- #


def test_clean_run_is_recovered_complete() -> None:
    _infra, result, report, plan, _pre, _rec = _run_pipeline()
    assert result.outcome is TerminalOutcome.COMPLETED
    assert report.decision is ValidationDecision.PASSED
    assert plan.decision is RecoveryDecision.COMPLETE
    assert plan.recovered is True


def test_claude_failure_is_recovered_retry() -> None:
    infra, _result, report, plan, _pre, _rec = _run_pipeline(fail=True)
    assert report.decision is ValidationDecision.FAILED
    assert plan.decision is RecoveryDecision.RETRY
    assert plan.retry_eligible is True
    assert "recovery.completed" in [e.type for e in infra.event_store.read_all()]


def test_partial_validation_is_recovered_resume_from_checkpoint() -> None:
    _infra, _result, report, plan, _pre, _rec = _run_pipeline(
        corroborate=False, checkpoint="cp-0003"
    )
    assert report.decision is ValidationDecision.PARTIAL
    assert plan.decision is RecoveryDecision.RESUME
    assert plan.checkpoint_ref == Reference(target_type="checkpoint", identifier="cp-0003")


def test_abort_emits_recovery_failed() -> None:
    from nexus_recovery import FailureCategory, RecoveryPolicy

    infra = build_infrastructure(observability=InMemoryObservability())
    ts = FixedTimestampSource()
    runtime = build_runtime(infra, timestamps=ts)
    adapter = ClaudeRuntimeAdapter(invoker=StubClaudeInvoker(fail=True))
    runtime.manager.register_runtime(adapter.descriptor())
    itk = intake(candidates=("claude-code",), required=("code_generation",))
    session = runtime.manager.prepare(preparation_request(itk)).sessions[0]
    result = build_execution(infra, timestamps=ts).engine.execute(
        session, adapter, itk.work_package
    )
    events = tuple(infra.event_store.read_all())
    report = build_validation(infra, timestamps=ts).engine.validate(
        result, itk.work_package, events=events
    )
    plan = build_recovery(infra, timestamps=ts).engine.recover(
        report, result, policy=RecoveryPolicy(abort_on=(FailureCategory.RUNTIME,))
    )
    assert plan.decision is RecoveryDecision.ABORT
    assert "recovery.failed" in [e.type for e in infra.event_store.read_all()]


# --- integration invariants ------------------------------------------------- #


def test_recovery_only_appends_to_the_log() -> None:
    infra, _result, _report, _plan, pre, _rec = _run_pipeline()
    post = tuple(infra.event_store.read_all())
    # Every pre-recovery (runtime + execution + validation) event is unchanged; recovery appended.
    assert post[: len(pre)] == pre
    assert len(post) > len(pre)


def test_recovery_shares_the_operation_correlation() -> None:
    infra, _result, _report, plan, _pre, _rec = _run_pipeline()
    runtime_events = [e for e in infra.event_store.read_all() if e.type.startswith("runtime.")]
    correlations = {e.correlation_identifier for e in runtime_events}
    assert plan.correlation_identifier in correlations


def test_plan_is_persisted() -> None:
    _infra, _result, _report, plan, _pre, recovery = _run_pipeline()
    assert recovery.repositories.plans.get(plan.identity) == plan


def test_full_pipeline_is_deterministic() -> None:
    infra1, _r1, _rep1, plan1, _p1, _v1 = _run_pipeline()
    infra2, _r2, _rep2, plan2, _p2, _v2 = _run_pipeline()
    assert plan1 == plan2
    e1 = [(e.identifier, e.type, e.payload, e.timestamp) for e in infra1.event_store.read_all()]
    e2 = [(e.identifier, e.type, e.payload, e.timestamp) for e in infra2.event_store.read_all()]
    assert e1 == e2


# --- structural guardrails (recovery is strictly downstream) ---------------- #

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _package_source(package: str) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in (_REPO_ROOT / package).glob("*.py"))


def test_runtime_does_not_depend_on_recovery() -> None:
    assert "nexus_recovery" not in _package_source("nexus_runtime")


def test_execution_does_not_depend_on_recovery() -> None:
    assert "nexus_recovery" not in _package_source("nexus_execution")


def test_validation_does_not_depend_on_recovery() -> None:
    assert "nexus_recovery" not in _package_source("nexus_validation")
