"""Phase 4 governance matrix for the A1 vertical -- deterministic, no network/real human.

Every governance outcome the benchmark requires is asserted here against the thin approval core and
the real git dangerous-action, over an isolated tmp repo:
approved->commit, rejected->no commit, timeout->fail-closed, duplicate->idempotent, late->ignored,
unauthorized approver->denied. The real-human path is exercised only by ``scripts/a1_run.py``.
"""

from __future__ import annotations

import pathlib

from nexus_workflows.a1 import A1TaskSpec, run_a1_vertical
from nexus_workflows.human_approval import (
    ApprovalGateway,
    ApprovalOutcome,
    ApprovalRequest,
    ApprovalResponse,
    CallableApprovalChannel,
    parse_discord_decision,
)


def _task() -> A1TaskSpec:
    return A1TaskSpec(
        fix_relpath="FIX.txt",
        fix_content="approved-fix\n",
        branch="a1/approved-fix",
        authority="owner-1",
    )


def _channel(granted: bool | None):
    def responder(request: ApprovalRequest):
        if granted is None:
            return None  # timeout / no answer
        return ApprovalResponse(
            correlation_id=request.correlation_id,
            granted=granted,
            approver=request.authority,
            reason="test",
        )

    return CallableApprovalChannel(responder, name="test")


# --- benchmark governance matrix (over the real git action) ----------------- #


def test_approved_commits_the_fix(tmp_path: pathlib.Path) -> None:
    result = run_a1_vertical(
        _task(), working_dir=str(tmp_path), channel=_channel(True), correlation_id="c1"
    )
    assert result.outcome is ApprovalOutcome.GRANTED
    assert result.dangerous_action_performed is True
    assert result.independent_branch_sha is not None  # git confirms the commit
    assert result.governance_consistent is True


def test_rejected_never_commits(tmp_path: pathlib.Path) -> None:
    result = run_a1_vertical(
        _task(), working_dir=str(tmp_path), channel=_channel(False), correlation_id="c2"
    )
    assert result.outcome is ApprovalOutcome.DENIED
    assert result.dangerous_action_performed is False
    assert result.independent_branch_sha is None
    assert result.governance_consistent is True


def test_timeout_is_fail_closed(tmp_path: pathlib.Path) -> None:
    result = run_a1_vertical(
        _task(), working_dir=str(tmp_path), channel=_channel(None), correlation_id="c3"
    )
    assert result.outcome is ApprovalOutcome.TIMED_OUT
    assert result.dangerous_action_performed is False  # silence never grants (INV-30)
    assert any(e.type == "interaction.timed_out" for e in result.events)


# --- core semantics: idempotency, late, authority (INV-16/30) --------------- #


def test_duplicate_answer_is_idempotent() -> None:
    gw = ApprovalGateway()
    req = ApprovalRequest(correlation_id="d1", operation="git_commit", detail="", authority="owner")
    ch = _channel(True)
    first = gw.request_approval(req, ch)
    # A duplicate of the same governed loop returns the settled outcome, never re-delivers.
    second = gw.request_approval(req, ch)
    third = gw.submit(ApprovalResponse("d1", granted=True, approver="owner"))
    assert first is second is third is ApprovalOutcome.GRANTED


def test_late_answer_after_timeout_is_ignored() -> None:
    gw = ApprovalGateway()
    req = ApprovalRequest(correlation_id="l1", operation="git_commit", detail="", authority="owner")
    assert gw.time_out("l1") if gw.outcome_of("l1") else gw.request_approval(req, _channel(None))
    # Gate closed as timeout; a late 'approve' must NOT flip it.
    late = gw.submit(ApprovalResponse("l1", granted=True, approver="owner"))
    assert late is ApprovalOutcome.TIMED_OUT
    assert gw.outcome_of("l1") is ApprovalOutcome.TIMED_OUT


def test_answer_for_unknown_gate_is_ignored_late() -> None:
    gw = ApprovalGateway()
    assert (
        gw.submit(ApprovalResponse("ghost", granted=True, approver="o"))
        is ApprovalOutcome.IGNORED_LATE
    )


def test_unauthorized_approver_is_denied() -> None:
    gw = ApprovalGateway()
    req = ApprovalRequest(
        correlation_id="u1", operation="git_commit", detail="", authority="owner-1"
    )

    def impostor(request: ApprovalRequest):
        return ApprovalResponse(request.correlation_id, granted=True, approver="stranger")

    assert gw.request_approval(req, CallableApprovalChannel(impostor)) is ApprovalOutcome.DENIED


# --- Discord bridge decision parsing (pure; no network) --------------------- #


def test_discord_parser_reads_owner_decision() -> None:
    messages = [
        {"author": {"id": "999"}, "content": "noise"},
        {"author": {"id": "owner-7"}, "content": "approve corr-abc please"},
    ]
    resp = parse_discord_decision(messages, correlation_id="corr-abc", authority_id="owner-7")
    assert resp is not None and resp.granted is True and resp.approver == "owner-7"


def test_discord_parser_ignores_non_owner_and_is_fail_closed() -> None:
    messages = [{"author": {"id": "stranger"}, "content": "approve corr-abc"}]
    assert (
        parse_discord_decision(messages, correlation_id="corr-abc", authority_id="owner-7") is None
    )
