"""The low-level repository scanner — a deterministic, read-only file-system snapshot.

Standalone (it imports **no** engine — reimplemented here rather than reusing the A0 prototype's
walker, which lives in ``nexus_workflows`` and would pull downstream engines in). It walks the tree
once, skipping vendored/generated directories, and returns a sorted, deterministic snapshot: the
top-level inventory, detected languages, file count, and git snapshot facts read straight from
``.git`` (no shelling out, no history walk). Same tree in → same snapshot out.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

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
_KEY_DOCUMENTS = (
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "package.json",
    "pyproject.toml",
)
_EXT_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".json": "json",
    ".md": "markdown",
    ".css": "css",
    ".scss": "css",
    ".html": "html",
    ".sh": "shell",
    ".rs": "rust",
    ".go": "go",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
}


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    """A faithful, read-only, deterministic description of a repository at one scan."""

    root: str
    exists: bool
    is_git: bool
    branch: str | None
    head_commit: str | None
    entries: tuple[str, ...]
    files: tuple[str, ...]
    key_documents: tuple[str, ...]
    languages: tuple[str, ...]
    file_count: int


def scan_tree(root: str, *, max_files: int = 8000) -> RepositorySnapshot:
    """Read ``root`` into a :class:`RepositorySnapshot` (deterministic; skips vendored dirs)."""
    if not os.path.isdir(root):
        return RepositorySnapshot(root, False, False, None, None, (), (), (), (), 0)

    entries = tuple(sorted(e for e in os.listdir(root) if not e.startswith(".git")))
    key_documents = tuple(d for d in _KEY_DOCUMENTS if os.path.isfile(os.path.join(root, d)))

    languages: set[str] = set()
    files: list[str] = []
    file_count = 0
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _IGNORE_DIRS)
        for name in sorted(filenames):
            file_count += 1
            files.append(os.path.relpath(os.path.join(current, name), root).replace(os.sep, "/"))
            language = _EXT_LANGUAGE.get(os.path.splitext(name)[1].lower())
            if language is not None:
                languages.add(language)
            if file_count >= max_files:
                break
        if file_count >= max_files:
            break

    branch, head = _git_facts(root)
    return RepositorySnapshot(
        root=os.path.abspath(root),
        exists=True,
        is_git=os.path.isdir(os.path.join(root, ".git")),
        branch=branch,
        head_commit=head,
        entries=entries,
        files=tuple(sorted(files)),
        key_documents=key_documents,
        languages=tuple(sorted(languages)),
        file_count=file_count,
    )


def _git_facts(root: str) -> tuple[str | None, str | None]:
    """Deterministic ``(branch, head_commit)`` from ``.git/HEAD`` (None where unborn/absent)."""
    head_path = os.path.join(root, ".git", "HEAD")
    try:
        with open(head_path, encoding="utf-8") as handle:
            content = handle.read().strip()
    except OSError:
        return None, None
    if content.startswith("ref:"):
        ref = content.split(":", 1)[1].strip()
        branch = ref.rsplit("/", 1)[-1]
        ref_path = os.path.join(root, ".git", *ref.split("/"))
        try:
            with open(ref_path, encoding="utf-8") as handle:
                return branch, handle.read().strip()[:12]
        except OSError:
            return branch, None  # unborn branch
    return None, content[:12]  # detached HEAD
