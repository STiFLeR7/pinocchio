"""Milestone 5 — end-to-end Execution → Validation integration (deterministic).

Extends the runtime vertical slice with the Validation Engine:

    RuntimeIntake → RM (Ready) → Execution Engine → Execution Result
        → Validation Engine → Evidence → Validation Report → Event Store / Persistence

Proves the governance verdict is produced from deterministic evidence (PASSED for a clean,
corroborated run; FAILED when Claude errors), that validation events share the operation's
correlation and only *append* to the log (Runtime and Execution events are untouched), that
identical runs yield identical reports, and — structurally — that Runtime and Execution do
not depend on Validation (validation is strictly downstream).
"""

from __future__ import annotations

import pathlib

from nexus_execution import build_execution
from nexus_execution.signals import TerminalOutcome
from nexus_infra import InMemoryObservability, build_infrastructure
from nexus_runtime import FixedTimestampSource, build_runtime
from nexus_runtime.vocabulary import RuntimeLifecycleState
from nexus_runtime_claude import ClaudeRuntimeAdapter, StubClaudeInvoker
from nexus_validation import ValidationDecision, build_validation
from tests.unit.nexus_runtime.helpers import intake, preparation_request


def _run_pipeline(*, fail: bool = False):  # type: ignore[no-untyped-def]
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

    pre_validation_events = tuple(infra.event_store.read_all())
    validation = build_validation(infra, timestamps=ts)
    report = validation.engine.validate(result, itk.work_package, events=pre_validation_events)
    return infra, result, report, pre_validation_events, validation


# --- happy path ------------------------------------------------------------- #


def test_clean_run_is_validated_passed() -> None:
    _infra, result, report, _pre, _val = _run_pipeline()
    assert result.outcome is TerminalOutcome.COMPLETED
    assert result.final_state is RuntimeLifecycleState.DESTROYED
    assert report.decision is ValidationDecision.PASSED
    assert report.confidence == 1.0


def test_verdict_is_evidence_backed_not_self_report() -> None:
    _infra, _result, report, _pre, _val = _run_pipeline()
    # The Passed verdict is corroborated by an independent artifact (INV-20), not the
    # runtime's "completed" self-report alone.
    assert "artifact_corroboration" in report.satisfied_requirements
    assert len(report.evidence_refs) >= 1


def test_report_and_evidence_persisted() -> None:
    _infra, _result, report, _pre, validation = _run_pipeline()
    assert validation.repositories.reports.get(report.identity) == report
    assert report.evidence_refs
    for ref in report.evidence_refs:
        assert validation.repositories.evidence.get(ref.identifier) is not None


# --- failure path ----------------------------------------------------------- #


def test_claude_failure_is_validated_failed() -> None:
    infra, result, report, _pre, _val = _run_pipeline(fail=True)
    assert result.outcome is TerminalOutcome.FAILED
    assert report.decision is ValidationDecision.FAILED
    assert "validation.failed" in [e.type for e in infra.event_store.read_all()]


# --- integration invariants ------------------------------------------------- #


def test_validation_only_appends_to_the_log() -> None:
    infra, _result, _report, pre, _val = _run_pipeline()
    post = tuple(infra.event_store.read_all())
    # Every pre-validation (runtime + execution) event is unchanged; validation appended.
    assert post[: len(pre)] == pre
    assert len(post) > len(pre)


def test_validation_shares_the_operation_correlation() -> None:
    infra, _result, report, _pre, _val = _run_pipeline()
    runtime_events = [e for e in infra.event_store.read_all() if e.type.startswith("runtime.")]
    correlations = {e.correlation_identifier for e in runtime_events}
    assert report.correlation_identifier in correlations


def test_full_pipeline_is_deterministic() -> None:
    infra1, _r1, report1, _p1, _v1 = _run_pipeline()
    infra2, _r2, report2, _p2, _v2 = _run_pipeline()
    assert report1 == report2
    e1 = [(e.identifier, e.type, e.payload, e.timestamp) for e in infra1.event_store.read_all()]
    e2 = [(e.identifier, e.type, e.payload, e.timestamp) for e in infra2.event_store.read_all()]
    assert e1 == e2


# --- structural guardrails (validation is strictly downstream) --------------- #

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _package_source(package: str) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in (_REPO_ROOT / package).glob("*.py"))


def test_runtime_does_not_depend_on_validation() -> None:
    assert "nexus_validation" not in _package_source("nexus_runtime")


def test_execution_does_not_depend_on_validation() -> None:
    assert "nexus_validation" not in _package_source("nexus_execution")
