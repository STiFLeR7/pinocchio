"""Unit tests for nexus_execution.results — the ExecutionResult value object."""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_execution.results import ExecutionResult
from nexus_execution.signals import TerminalOutcome
from nexus_runtime.vocabulary import RuntimeLifecycleState


def _result(outcome: TerminalOutcome) -> ExecutionResult:
    return ExecutionResult(
        session_ref=Reference(target_type="runtime_session", identifier="s"),
        work_package_ref=Reference(target_type="work_package", identifier="wp"),
        runtime_ref=Reference(target_type="harness", identifier="claude-code"),
        outcome=outcome,
        final_state=RuntimeLifecycleState.DESTROYED,
    )


def test_succeeded_true_only_for_completed() -> None:
    assert _result(TerminalOutcome.COMPLETED).succeeded is True
    assert _result(TerminalOutcome.FAILED).succeeded is False
    assert _result(TerminalOutcome.CANCELLED).succeeded is False


def test_result_defaults() -> None:
    result = _result(TerminalOutcome.COMPLETED)
    assert result.artifact_refs == ()
    assert result.event_ids == ()
    assert result.cleanup_ok is True
    assert result.stdout == ""


def test_result_is_immutable() -> None:
    result = _result(TerminalOutcome.COMPLETED)
    try:
        result.stdout = "x"  # type: ignore[misc]
    except (ValueError, AttributeError, TypeError):
        return
    raise AssertionError("ExecutionResult should be frozen")
