"""A1 -- the governed human-approval engineering vertical (architecture validation).

Proves ONE real governed approval loop end-to-end:

    produce fix -> PAUSE -> request approval (real human, real channel) -> settle (fail-closed)
        -> if GRANTED: commit the fix to a throwaway branch
        -> else: the dangerous action never happens
        -> independent verification (git log, not self-report) -> briefing

It reuses A0's proven real-Claude actuation for *producing* the fix (validated in
``A0_IMPLEMENTATION_REPORT.md``); to keep the shared claude rate-budget for the parts A1 actually
validates, the default here writes the fix deterministically and focuses the proof on the **approval
governance**. The governance core is :mod:`nexus_workflows.human_approval`; the dangerous action is
:mod:`nexus_workflows.git_actions`. No engine, ADR, contract, or invariant is modified.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from nexus_workflows.git_actions import (
    CommitResult,
    branch_commit_sha,
    commit_to_throwaway_branch,
)
from nexus_workflows.human_approval import (
    ApprovalChannel,
    ApprovalGateway,
    ApprovalOutcome,
    ApprovalRequest,
    InteractionEvent,
)


@dataclass(frozen=True, slots=True)
class A1TaskSpec:
    """A dangerous engineering action gated by human approval."""

    fix_relpath: str
    fix_content: str
    branch: str
    operation: str = "git_commit"
    authority: str = "operator"


@dataclass(frozen=True, slots=True)
class A1Result:
    """The full evidence of one governed-approval run."""

    task: A1TaskSpec
    working_dir: str
    correlation_id: str
    outcome: ApprovalOutcome
    commit: CommitResult
    dangerous_action_performed: bool
    independent_branch_sha: str | None
    governance_consistent: bool
    events: tuple[InteractionEvent, ...]
    remaining_stubs: tuple[str, ...]
    briefing: str = ""


def _write_fix(working_dir: str, task: A1TaskSpec) -> None:
    """Produce the 'approved fix' on disk (reuses A0's real-Claude path in production; see module doc)."""
    target = os.path.join(working_dir, task.fix_relpath)
    os.makedirs(os.path.dirname(target) or working_dir, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(task.fix_content)


def run_a1_vertical(
    task: A1TaskSpec,
    *,
    working_dir: str,
    channel: ApprovalChannel,
    correlation_id: str,
    gateway: ApprovalGateway | None = None,
) -> A1Result:
    """Run the governed approval loop; commit only if a real human grants approval."""
    gateway = gateway or ApprovalGateway()

    # 1. Produce the fix (the change that must NOT be persisted without approval).
    _write_fix(working_dir, task)

    # 2. PAUSE and obtain a real human decision through the channel (fail-closed core).
    request = ApprovalRequest(
        correlation_id=correlation_id,
        operation=task.operation,
        detail=f"commit '{task.fix_relpath}' to throwaway branch '{task.branch}'",
        authority=task.authority,
    )
    outcome = gateway.request_approval(request, channel)

    # 3. The dangerous action happens IFF approval was granted.
    if outcome is ApprovalOutcome.GRANTED:
        commit = commit_to_throwaway_branch(
            working_dir,
            branch=task.branch,
            message=f"fix: {task.fix_relpath} (approved, corr={correlation_id})",
        )
    else:
        commit = CommitResult(
            committed=False,
            branch=task.branch,
            commit_sha=None,
            detail=f"not committed: approval outcome was '{outcome.value}' (fail-closed)",
        )

    # 4. Independent verification: read git, not the workflow's own claim (INV-20 analogue).
    independent_sha = branch_commit_sha(working_dir, task.branch)
    dangerous_performed = independent_sha is not None
    governance_consistent = dangerous_performed == (outcome is ApprovalOutcome.GRANTED)

    result = A1Result(
        task=task,
        working_dir=working_dir,
        correlation_id=correlation_id,
        outcome=outcome,
        commit=commit,
        dangerous_action_performed=dangerous_performed,
        independent_branch_sha=independent_sha,
        governance_consistent=governance_consistent,
        events=gateway.events,
        remaining_stubs=_remaining_stubs(),
    )
    return _with_briefing(result)


def _remaining_stubs() -> tuple[str, ...]:
    return (
        "push to a real remote (A1 commits to a local throwaway branch only; no outward push)",
        "full Human Interaction subsystem (conversations, reviews, notifications) -- only approval",
        "live v1 DB-backed ApprovalRecord persistence -- A1 uses the thin v2 governed core",
        "multi-channel routing / escalation chains -- single channel per run",
    )


def _with_briefing(result: A1Result) -> A1Result:
    verdict = "GOVERNED-OK" if result.governance_consistent else "GOVERNANCE-VIOLATION"
    lines = [
        f"# A1 Governed-Approval Briefing -- {verdict}",
        f"operation         : {result.task.operation} -> branch '{result.task.branch}'",
        f"correlation       : {result.correlation_id}",
        f"approval outcome  : {result.outcome.value}",
        f"dangerous action  : {'PERFORMED' if result.dangerous_action_performed else 'BLOCKED'}",
        f"commit detail     : {result.commit.detail}",
        f"independent sha   : {result.independent_branch_sha or '(none)'}",
        f"governance check  : action==granted ? {result.governance_consistent}",
        f"interaction events: {[e.type for e in result.events]}",
    ]
    briefing = "\n".join(lines)
    return A1Result(
        task=result.task,
        working_dir=result.working_dir,
        correlation_id=result.correlation_id,
        outcome=result.outcome,
        commit=result.commit,
        dangerous_action_performed=result.dangerous_action_performed,
        independent_branch_sha=result.independent_branch_sha,
        governance_consistent=result.governance_consistent,
        events=result.events,
        remaining_stubs=result.remaining_stubs,
        briefing=briefing,
    )
