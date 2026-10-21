"""Module dependency graph + package inventory — deterministic Python-structure facts.

Both are pure functions of the tree: the package inventory lists top-level Python packages
(directories with ``__init__.py``); the module graph extracts intra-repository import edges by
parsing each ``.py`` file's ``import`` statements with :mod:`ast` (no execution, no evaluation) and
keeping only edges between discovered packages. Sorted and deduplicated — same tree → same graph.
"""

from __future__ import annotations

import ast
import os

from nexus_repository.profile import ModuleGraph, PackageInventory

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


def package_inventory(root: str) -> PackageInventory:
    """Discover top-level Python packages (directories with ``__init__.py``), deterministically."""
    names: list[str] = []
    paths: list[str] = []
    for entry in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        path = os.path.join(root, entry)
        if (
            os.path.isdir(path)
            and entry not in _IGNORE_DIRS
            and os.path.isfile(os.path.join(path, "__init__.py"))
        ):
            names.append(entry)
            paths.append(entry)
        elif entry == "src" and os.path.isdir(path):
            for sub in sorted(os.listdir(path)):
                if os.path.isfile(os.path.join(path, sub, "__init__.py")):
                    names.append(sub)
                    paths.append(f"src/{sub}")
    return PackageInventory(packages=tuple(names), package_paths=tuple(paths))


def module_graph(root: str, packages: PackageInventory, *, max_files: int = 6000) -> ModuleGraph:
    """Build the intra-repository module dependency graph from Python imports (deterministic)."""
    known = set(packages.packages)
    edges: set[tuple[str, str]] = set()
    scanned = 0
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _IGNORE_DIRS)
        owner = _owning_package(os.path.relpath(current, root))
        if owner not in known:
            continue
        for name in sorted(f for f in filenames if f.endswith(".py")):
            scanned += 1
            if scanned > max_files:
                break
            for imported in _imports(os.path.join(current, name)):
                target = imported.split(".", 1)[0]
                if target in known and target != owner:
                    edges.add((owner, target))
        if scanned > max_files:
            break
    return ModuleGraph(nodes=packages.packages, edges=tuple(sorted(edges)))


def _owning_package(relpath: str) -> str:
    parts = relpath.replace("\\", "/").split("/")
    if parts and parts[0] == "src" and len(parts) > 1:
        return parts[1]
    return parts[0] if parts else ""


def _imports(path: str) -> set[str]:
    try:
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
    except (OSError, SyntaxError, ValueError):
        return set()
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules
