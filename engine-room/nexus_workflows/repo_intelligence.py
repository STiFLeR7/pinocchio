"""Repository Intelligence -- the minimum reusable capability that turns a real repository on
disk into engineered-context input, for the A0 vertical (and any future consumer).

This is deliberately *thin*. The Architecture Freeze Review deferred "Repository Intelligence as
a full subsystem" (``docs/v2/engineering/10``); A0 needs only enough grounding to prove the
vertical: read a real working directory and surface a faithful, provider-independent snapshot
(inventory, key documents, detected languages, git HEAD) as a single ``WORKSPACE`` context
fragment Context Engineering can normalize.

It decides nothing and actuates nothing: it *reads* a filesystem and emits value objects. It coins
no new domain concept -- the output is an existing :class:`~nexus_context.RawContextFragment`. When
a real Repository Intelligence subsystem is built, this function is its smallest honest seed, not a
throwaway: callers depend only on ``read_repository`` / ``to_context_fragments``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from nexus_context import ContextCategory, ContextSource, RawContextFragment

# Directories never worth walking for context (heavy, generated, or vendored).
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
# Documents that, if present, most cheaply describe intent/conventions for an engineering agent.
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
}


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    """A faithful, read-only description of a repository at one instant."""

    root: str
    exists: bool
    is_git: bool
    head: str | None
    entries: tuple[str, ...]
    key_documents: tuple[str, ...]
    languages: tuple[str, ...]
    file_count: int


def read_repository(root: str, *, max_files: int = 4000) -> RepositorySnapshot:
    """Read ``root`` and return a :class:`RepositorySnapshot` (skips vendored/generated dirs)."""
    if not os.path.isdir(root):
        return RepositorySnapshot(
            root=root,
            exists=False,
            is_git=False,
            head=None,
            entries=(),
            key_documents=(),
            languages=(),
            file_count=0,
        )

    entries = tuple(sorted(e for e in os.listdir(root) if not e.startswith(".git")))
    key_documents = tuple(d for d in _KEY_DOCUMENTS if os.path.isfile(os.path.join(root, d)))

    languages: set[str] = set()
    file_count = 0
    for _current, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]
        for name in filenames:
            file_count += 1
            language = _EXT_LANGUAGE.get(os.path.splitext(name)[1].lower())
            if language is not None:
                languages.add(language)
            if file_count >= max_files:
                break
        if file_count >= max_files:
            break

    return RepositorySnapshot(
        root=os.path.abspath(root),
        exists=True,
        is_git=os.path.isdir(os.path.join(root, ".git")),
        head=_git_head(root),
        entries=entries,
        key_documents=key_documents,
        languages=tuple(sorted(languages)),
        file_count=file_count,
    )


def to_context_fragments(snapshot: RepositorySnapshot) -> tuple[RawContextFragment, ...]:
    """Project a snapshot onto the canonical ``WORKSPACE`` context fragment (no new concept)."""
    payload: dict[str, object] = {
        "root": snapshot.root,
        "exists": snapshot.exists,
        "is_git": snapshot.is_git,
        "head": snapshot.head,
        "entries": list(snapshot.entries),
        "key_documents": list(snapshot.key_documents),
        "languages": list(snapshot.languages),
        "file_count": snapshot.file_count,
    }
    return (
        RawContextFragment(
            source=ContextSource.WORKSPACE,
            category=ContextCategory.WORKSPACE,
            key="repository",
            payload=payload,
        ),
    )


def _git_head(root: str) -> str | None:
    """Best-effort short HEAD ref from ``.git/HEAD`` without shelling out (None if unborn/absent)."""
    head_path = os.path.join(root, ".git", "HEAD")
    try:
        with open(head_path, encoding="utf-8") as handle:
            content = handle.read().strip()
    except OSError:
        return None
    if content.startswith("ref:"):
        ref = content.split(":", 1)[1].strip()
        ref_path = os.path.join(root, ".git", *ref.split("/"))
        try:
            with open(ref_path, encoding="utf-8") as handle:
                return handle.read().strip()[:12]
        except OSError:
            return None  # unborn branch (ref named but no commit yet)
    return content[:12]
