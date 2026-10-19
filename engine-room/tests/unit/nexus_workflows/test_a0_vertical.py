"""Unit tests for the A0 vertical -- deterministic (StubClaudeInvoker), no real claude/network.

These cover the *reusable* A0 seams: thin Repository Intelligence, the fail-closed approval gate,
request construction, independent on-disk validation, and the vertical wired over a stub adapter.
The real-claude path is exercised only by ``scripts/a0_run.py`` (an opt-in, rate-limited run).
"""

from __future__ import annotations

import pathlib

from nexus_runtime_claude import ClaudeRuntimeAdapter, StubClaudeInvoker
from nexus_workflows.a0 import (
    A0TaskSpec,
    ApprovalGate,
    Authorization,
    build_a0_request,
    run_a0_vertical,
)
from nexus_workflows.repo_intelligence import read_repository, to_context_fragments


def _task() -> A0TaskSpec:
    return A0TaskSpec(
        objective="Create A0_PROOF.txt containing exactly: NEXUS-A0-OK",
        knowledge_subject="a0 test",
        verify_relpath="A0_PROOF.txt",
        verify_expected="NEXUS-A0-OK",
    )


def _stub_factory(_request: object) -> ClaudeRuntimeAdapter:
    return ClaudeRuntimeAdapter(invoker=StubClaudeInvoker())


# --- Repository Intelligence ----------------------------------------------- #


def test_read_repository_surfaces_inventory_and_languages(tmp_path: pathlib.Path) -> None:
    (tmp_path / "README.md").write_text("# hi", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('x')", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.js").write_text("//", encoding="utf-8")

    snapshot = read_repository(str(tmp_path))

    assert snapshot.exists
    assert "README.md" in snapshot.key_documents
    assert "python" in snapshot.languages
    assert "javascript" not in snapshot.languages  # node_modules is skipped
    fragments = to_context_fragments(snapshot)
    assert fragments[0].key == "repository"
    assert fragments[0].payload["file_count"] == snapshot.file_count


def test_read_repository_missing_dir_is_honest() -> None:
    snapshot = read_repository(r"D:\definitely-not-here-a0")
    assert snapshot.exists is False
    assert snapshot.file_count == 0


# --- Approval gate: fail-closed (INV-30) ----------------------------------- #


def test_approval_gate_denies_without_authorization() -> None:
    decision = ApprovalGate().evaluate(operation="git_commit", authorization=None)
    assert decision.granted is False
    assert "fail-closed" in decision.reason


def test_approval_gate_grants_only_for_the_named_operation() -> None:
    auth = Authorization(approver="owner", reason="ok", granted_operations=("git_commit",))
    assert ApprovalGate().evaluate(operation="git_commit", authorization=auth).granted is True
    assert ApprovalGate().evaluate(operation="git_push", authorization=auth).granted is False


# --- request construction --------------------------------------------------- #


def test_build_a0_request_is_single_work_item_carrying_the_objective() -> None:
    request = build_a0_request(_task(), ())
    assert len(request.work_items) == 1
    assert request.work_items[0].objective == _task().objective
    assert request.goal.outcome == _task().objective


# --- the vertical over a stub adapter (deterministic) ----------------------- #


def test_vertical_runs_pipeline_and_gates_commit_fail_closed(tmp_path: pathlib.Path) -> None:
    result = run_a0_vertical(_task(), working_dir=str(tmp_path), adapter_factory=_stub_factory)

    # The full pipeline ran and produced durable knowledge.
    assert result.run.execution_outcomes  # execution happened
    assert result.run.events  # events recorded
    # The stub does not write A0_PROOF.txt, so independent validation is honestly negative.
    assert result.independent_validation_ok is False
    assert "was not created" in result.independent_validation_detail
    # Dangerous op stays fail-closed; nothing committed.
    assert result.commit_decision.granted is False
    assert result.committed is False
    assert result.remaining_stubs  # honestly enumerated


def test_vertical_validates_when_the_effect_is_present(tmp_path: pathlib.Path) -> None:
    # Simulate the on-disk effect a real claude session would produce.
    (tmp_path / "A0_PROOF.txt").write_text("NEXUS-A0-OK\n", encoding="utf-8")
    result = run_a0_vertical(_task(), working_dir=str(tmp_path), adapter_factory=_stub_factory)
    assert result.independent_validation_ok is True
    assert "expected marker" in result.independent_validation_detail
