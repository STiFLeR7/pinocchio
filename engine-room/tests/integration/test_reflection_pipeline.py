"""Milestone 5 — end-to-end Execution → Validation → Recovery → Reflection (deterministic).

Extends the recovery pipeline with the Reflection Engine:

    RuntimeIntake → RM (Ready) → Execution Engine → Execution Result
        → Validation Engine → Validation Report
        → Recovery Engine → Recovery Plan
        → Reflection Engine → Reflection Report → Event Store / Persistence

Proves the analytical layer explains the completed operation from its immutable history (a
report with deterministic patterns and advisory Knowledge Candidates), that reflection events
share the operation's correlation and only *append* to the log (Runtime, Execution, Validation,
and Recovery events are untouched), that identical history yields identical reports, and —
structurally — that Runtime, Execution, Validation, and Recovery do not depend on Reflection
(reflection is strictly downstream).
"""

from __future__ import annotations

import pathlib

from nexus_execution import build_execution
from nexus_infra import InMemoryObservability, build_infrastructure
from nexus_recovery import build_recovery
from nexus_reflection import ReflectionStage, build_reflection
from nexus_runtime import FixedTimestampSource, build_runtime
from nexus_runtime_claude import ClaudeRuntimeAdapter, StubClaudeInvoker
from nexus_validation import build_validation
from tests.unit.nexus_runtime.helpers import intake, preparation_request


def _pipeline(*, fail: bool = False):  # type: ignore[no-untyped-def]
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
    report = build_validation(infra, timestamps=ts).engine.validate(
        result, itk.work_package, events=all_events
    )
    plan = build_recovery(infra, timestamps=ts).engine.recover(report, result, events=all_events)

    pre_reflection_events = tuple(infra.event_store.read_all())
    reflection = build_reflection(infra, timestamps=ts)
    scope = result.session_ref.identifier
    reflection_report = reflection.engine.reflect(
        scope,
        execution_results=(result,),
        validation_reports=(report,),
        recovery_plans=(plan,),
        events=pre_reflection_events,
    )
    return infra, reflection_report, pre_reflection_events, reflection


# --- analytical output ------------------------------------------------------ #


def test_clean_operation_is_reflected() -> None:
    _infra, report, _pre, _refl = _pipeline()
    assert report.stage is ReflectionStage.COMPLETED
    assert report.episode_count == 1
    assert report.patterns  # validation/recovery/runtime patterns at minimum
    assert report.confidence is not None


def test_failed_operation_surfaces_a_failure_pattern() -> None:
    _infra, report, _pre, _refl = _pipeline(fail=True)
    kinds = {p.kind.value for p in report.patterns}
    assert "repeated_failure" in kinds or "recovery_decision" in kinds


# --- integration invariants ------------------------------------------------- #


def test_reflection_only_appends_to_the_log() -> None:
    infra, _report, pre, _refl = _pipeline()
    post = tuple(infra.event_store.read_all())
    assert post[: len(pre)] == pre
    assert len(post) > len(pre)


def test_reflection_shares_the_operation_correlation() -> None:
    infra, report, _pre, _refl = _pipeline()
    runtime_events = [e for e in infra.event_store.read_all() if e.type.startswith("runtime.")]
    correlations = {e.correlation_identifier for e in runtime_events}
    assert report.correlation_identifier in correlations


def test_report_and_patterns_persisted() -> None:
    _infra, report, _pre, reflection = _pipeline()
    assert reflection.repositories.reports.get(report.identity) == report
    for pattern in report.patterns:
        assert reflection.repositories.patterns.get(pattern.identity) is not None


def test_full_pipeline_is_deterministic() -> None:
    infra1, report1, _p1, _r1 = _pipeline()
    infra2, report2, _p2, _r2 = _pipeline()
    assert report1 == report2
    e1 = [(e.identifier, e.type, e.payload, e.timestamp) for e in infra1.event_store.read_all()]
    e2 = [(e.identifier, e.type, e.payload, e.timestamp) for e in infra2.event_store.read_all()]
    assert e1 == e2


# --- structural guardrails (reflection is strictly downstream) -------------- #

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _package_source(package: str) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in (_REPO_ROOT / package).glob("*.py"))


def test_runtime_does_not_depend_on_reflection() -> None:
    assert "nexus_reflection" not in _package_source("nexus_runtime")


def test_execution_does_not_depend_on_reflection() -> None:
    assert "nexus_reflection" not in _package_source("nexus_execution")


def test_validation_does_not_depend_on_reflection() -> None:
    assert "nexus_reflection" not in _package_source("nexus_validation")


def test_recovery_does_not_depend_on_reflection() -> None:
    assert "nexus_reflection" not in _package_source("nexus_recovery")
