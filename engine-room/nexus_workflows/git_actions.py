"""The dangerous engineering action A1 gates: committing an approved fix to a throwaway branch.

Deliberately small and reusable. It is the *only* code that mutates a repository, and it is only
ever called after :class:`~nexus_workflows.human_approval.ApprovalGateway` returns ``GRANTED``. It
operates on an isolated working directory (never a real remote), so the proof is fully contained.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommitResult:
    """The outcome of a governed commit (or a refusal to commit)."""

    committed: bool
    branch: str
    commit_sha: str | None
    detail: str


def _git(working_dir: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=working_dir,
        capture_output=True,
        text=True,
        check=False,
    )


def ensure_repository(working_dir: str) -> None:
    """Make ``working_dir`` a git repo (isolated copies exclude ``.git``), with a local identity."""
    if _git(working_dir, "rev-parse", "--is-inside-work-tree").returncode != 0:
        _git(working_dir, "init")
    # Local, throwaway identity so the commit succeeds without touching global config.
    _git(working_dir, "config", "user.email", "a1@nexus.local")
    _git(working_dir, "config", "user.name", "Nexus A1")


def commit_to_throwaway_branch(working_dir: str, *, branch: str, message: str) -> CommitResult:
    """Commit all changes in ``working_dir`` onto ``branch`` (created fresh). Never pushes."""
    ensure_repository(working_dir)
    checkout = _git(working_dir, "checkout", "-B", branch)
    if checkout.returncode != 0:
        return CommitResult(False, branch, None, f"checkout failed: {checkout.stderr.strip()}")
    _git(working_dir, "add", "-A")
    commit = _git(working_dir, "commit", "-m", message)
    if commit.returncode != 0:
        return CommitResult(
            False, branch, None, f"commit failed: {(commit.stderr or commit.stdout).strip()}"
        )
    sha = _git(working_dir, "rev-parse", "HEAD").stdout.strip() or None
    return CommitResult(True, branch, sha, "committed to throwaway branch")


def branch_commit_sha(working_dir: str, branch: str) -> str | None:
    """Return the HEAD sha of ``branch`` (independent verification), or None if it has no commit."""
    result = _git(working_dir, "rev-parse", "--verify", f"{branch}")
    sha = result.stdout.strip()
    return sha if result.returncode == 0 and sha else None
