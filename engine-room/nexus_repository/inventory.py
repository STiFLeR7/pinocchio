"""Constitutional-artifact, issue, git, and health inventories — deterministic facts.

Discovers the architecture's own records (ADRs, contracts, invariant documents), on-disk issue
tracking (templates/config — no remote fetch, so it stays deterministic and replayable), the git
snapshot facts, and repository **health signals** (factual presence indicators only — no grade, no
opinion). All pure functions of the tree.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from nexus_repository.profile import (
    ConstitutionalArtifacts,
    GitSummary,
    HealthSignals,
    IssueInventory,
    TestProfile,
)
from nexus_repository.scanner import RepositorySnapshot

_IGNORE_DIRS = frozenset(
    {
        "node_modules",
        ".git",
        "dist",
        "build",
        ".next",
        "coverage",
        "__pycache__",
        ".venv",
        ".ruff_cache",
    }
)
_LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING")
_LOCKFILES = (
    "uv.lock",
    "poetry.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.lock",
    "go.sum",
)


def constitutional_artifacts(root: str, *, max_hits: int = 400) -> ConstitutionalArtifacts:
    """Discover ADR, contract, and invariant files (facts). Bounded and sorted."""
    adr = _collect(
        root,
        ("adr", "docs/adr", "docs/adrs", "doc/adr"),
        lambda n: n.lower().endswith(".md"),
        max_hits,
    )
    contracts = _collect(
        root, ("contracts", "docs/contracts"), lambda n: n.lower().endswith(".md"), max_hits
    )
    invariants = _find_invariants(root, max_hits)
    return ConstitutionalArtifacts(
        adr_files=adr, contract_files=contracts, invariant_files=invariants
    )


def issue_inventory(root: str) -> IssueInventory:
    """Discover on-disk issue-tracking facts (templates + config); never fetches remote issues."""
    template_dir = os.path.join(root, ".github", "ISSUE_TEMPLATE")
    templates: tuple[str, ...] = ()
    if os.path.isdir(template_dir):
        templates = tuple(sorted(f for f in os.listdir(template_dir) if not f.startswith(".")))
    has_config = os.path.isfile(
        os.path.join(root, ".github", "ISSUE_TEMPLATE", "config.yml")
    ) or bool(templates)
    return IssueInventory(issue_templates=templates, has_issue_config=has_config)


def git_summary(snapshot: RepositorySnapshot) -> GitSummary:
    """Deterministic git snapshot facts (from the scanner's ``.git`` read)."""
    return GitSummary(
        is_git=snapshot.is_git, branch=snapshot.branch, head_commit=snapshot.head_commit
    )


def health_signals(
    root: str,
    snapshot: RepositorySnapshot,
    top: set[str],
    test: TestProfile,
    ci_system: str | None,
    codeowners: bool,
) -> HealthSignals:
    """Factual repository health **signals** — presence indicators only (no grade)."""
    return HealthSignals(
        has_readme=any(e.lower().startswith("readme") for e in snapshot.entries),
        has_tests=bool(test.frameworks or test.test_dirs),
        has_ci=ci_system is not None,
        has_lockfile=any(lock in top for lock in _LOCKFILES),
        has_license=any(name in top for name in _LICENSE_NAMES),
        has_codeowners=codeowners,
        file_count=snapshot.file_count,
    )


# -- helpers ----------------------------------------------------------------- #


def _collect(
    root: str, dirs: tuple[str, ...], keep: Callable[[str], bool], max_hits: int
) -> tuple[str, ...]:
    hits: list[str] = []
    for rel in dirs:
        base = os.path.join(root, *rel.split("/"))
        if not os.path.isdir(base):
            continue
        for current, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d not in _IGNORE_DIRS)
            for name in sorted(filenames):
                if keep(name):
                    hits.append(
                        os.path.relpath(os.path.join(current, name), root).replace("\\", "/")
                    )
                    if len(hits) >= max_hits:
                        return tuple(sorted(set(hits)))
    return tuple(sorted(set(hits)))


def _find_invariants(root: str, max_hits: int) -> tuple[str, ...]:
    hits: list[str] = []
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _IGNORE_DIRS)
        for name in sorted(filenames):
            if "invariant" in name.lower() and name.lower().endswith(".md"):
                hits.append(os.path.relpath(os.path.join(current, name), root).replace("\\", "/"))
                if len(hits) >= max_hits:
                    return tuple(sorted(set(hits)))
    return tuple(sorted(set(hits)))
