"""A1 real-run entrypoint -- one governed approval loop against a real isolated repo.

The approval decision is supplied by ``--decision``, which carries a **real human answer** relayed
from the operator surface (the Claude Code operator collects the human's live Approve/Reject and
passes it here). This is the operator Channel adapter: a real human, a real channel, no fixture.
The dangerous action (commit to a throwaway branch) happens IFF the governed gate returns GRANTED.

Usage:
    python -m scripts.a1_run --decision approve --approver operator
    python -m scripts.a1_run --decision reject  --approver operator
    python -m scripts.a1_run --decision timeout
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys

from nexus_workflows.a1 import A1TaskSpec, run_a1_vertical
from nexus_workflows.human_approval import (
    ApprovalRequest,
    ApprovalResponse,
    CallableApprovalChannel,
)

_DEFAULT_SOURCE = r"D:\port"
_DEFAULT_WORKSPACE = r"D:\port-a1-run"
_IGNORE = shutil.ignore_patterns(
    "node_modules",
    ".git",
    "dist",
    "build",
    ".next",
    "coverage",
    "__pycache__",
    ".venv",
    "*.png",
    "*.jpg",
    "*.mp4",
)
_AUTHORITY = "operator"


def _prepare_workspace(source: str, workspace: str) -> None:
    shutil.rmtree(workspace, ignore_errors=True)
    shutil.copytree(source, workspace, ignore=_IGNORE)


def _operator_channel(decision: str, approver: str) -> CallableApprovalChannel:
    """Build the operator channel that returns the human's real, relayed decision."""

    def responder(request: ApprovalRequest) -> ApprovalResponse | None:
        if decision == "timeout":
            return None  # human did not answer within the gate
        return ApprovalResponse(
            correlation_id=request.correlation_id,
            granted=(decision == "approve"),
            approver=approver,
            reason=f"relayed operator decision: {decision}",
        )

    return CallableApprovalChannel(responder, name="operator-cli")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the A1 governed-approval vertical.")
    parser.add_argument("--decision", required=True, choices=["approve", "reject", "timeout"])
    parser.add_argument("--approver", default=_AUTHORITY)
    parser.add_argument("--source", default=_DEFAULT_SOURCE)
    parser.add_argument("--workspace", default=_DEFAULT_WORKSPACE)
    parser.add_argument("--correlation", default="a1-live-001")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args(argv)

    print(f"[a1] isolating {args.source} -> {args.workspace}")
    _prepare_workspace(args.source, args.workspace)

    task = A1TaskSpec(
        fix_relpath="A1_FIX.txt",
        fix_content="NEXUS-A1-APPROVED-FIX\n",
        branch="a1/approved-fix",
        authority=_AUTHORITY,
    )
    channel = _operator_channel(args.decision, args.approver)

    print(f"[a1] governed loop: real decision = '{args.decision}' by '{args.approver}'")
    result = run_a1_vertical(
        task, working_dir=args.workspace, channel=channel, correlation_id=args.correlation
    )

    print("\n" + result.briefing + "\n")
    evidence = {
        "approval_outcome": result.outcome.value,
        "dangerous_action_performed": result.dangerous_action_performed,
        "independent_branch_sha": result.independent_branch_sha,
        "governance_consistent": result.governance_consistent,
        "commit_detail": result.commit.detail,
        "interaction_events": [e.type for e in result.events],
        "remaining_stubs": list(result.remaining_stubs),
    }
    print("[a1] evidence:\n" + json.dumps(evidence, indent=2))

    if not args.keep:
        shutil.rmtree(args.workspace, ignore_errors=True)
        print(f"[a1] removed isolated workspace {args.workspace}")

    # Exit 0 only if governance stayed consistent (action <=> granted).
    return 0 if result.governance_consistent else 1


if __name__ == "__main__":
    sys.exit(main())
