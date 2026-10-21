"""A0 real-run entrypoint -- the first production-grade v2 bridge, driven end-to-end.

Prepares an **isolated, throwaway copy** of a real repository (so the operator's working tree is
never touched), runs the A0 engineering vertical against a **real** Claude Code session over that
copy, prints the evidence, and (unless ``--keep``) removes the copy.

Usage:
    python -m scripts.a0_run                 # default: copy D:/port -> D:/port-a0-run, real claude
    python -m scripts.a0_run --keep          # leave the isolated workspace for inspection
    python -m scripts.a0_run --source X --workspace Y

Safety: edits land only in the isolated workspace; the commit/push step is gated fail-closed and
never writes back to the source repository (see nexus_workflows.a0).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys

from nexus_workflows.a0 import A0TaskSpec, run_a0_vertical

_DEFAULT_SOURCE = r"D:\port"
_DEFAULT_WORKSPACE = r"D:\port-a0-run"
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

# A trivial, safe, independently-verifiable engineering task -- exercises the full vertical without
# requiring judgement about the target project's domain.
_TASK = A0TaskSpec(
    objective=(
        "Create a file named A0_PROOF.txt in the current working directory containing exactly "
        "one line: NEXUS-A0-OK"
    ),
    knowledge_subject="a0 engineering vertical",
    verify_relpath="A0_PROOF.txt",
    verify_expected="NEXUS-A0-OK",
)


def _prepare_workspace(source: str, workspace: str) -> None:
    shutil.rmtree(workspace, ignore_errors=True)
    shutil.copytree(source, workspace, ignore=_IGNORE)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the A0 real engineering vertical.")
    parser.add_argument("--source", default=_DEFAULT_SOURCE)
    parser.add_argument("--workspace", default=_DEFAULT_WORKSPACE)
    parser.add_argument("--keep", action="store_true", help="keep the isolated workspace")
    args = parser.parse_args(argv)

    print(f"[a0] isolating {args.source} -> {args.workspace} (excluding node_modules/.git/assets)")
    _prepare_workspace(args.source, args.workspace)

    print("[a0] running vertical against a REAL claude session ...")
    result = run_a0_vertical(_TASK, working_dir=args.workspace)

    print("\n" + result.briefing + "\n")
    evidence = {
        "independent_validation_ok": result.independent_validation_ok,
        "independent_validation_detail": result.independent_validation_detail,
        "execution_outcomes": list(result.run.execution_outcomes),
        "validation_decisions": list(result.run.validation_decisions),
        "recovery_decisions": list(result.run.recovery_decisions),
        "commit_gate_granted": result.commit_decision.granted,
        "commit_gate_reason": result.commit_decision.reason,
        "committed": result.committed,
        "knowledge_item_ids": list(result.knowledge_item_ids),
        "event_count": len(result.run.events),
        "remaining_stubs": list(result.remaining_stubs),
    }
    print("[a0] evidence:\n" + json.dumps(evidence, indent=2))

    if not args.keep:
        shutil.rmtree(args.workspace, ignore_errors=True)
        print(f"[a0] removed isolated workspace {args.workspace}")

    return 0 if result.independent_validation_ok else 1


if __name__ == "__main__":
    sys.exit(main())
