"""Workspace path confinement for runtime file operations (S-4 / A-006 R-05).

The single containment boundary for file access: every requested path is resolved against the
approved workspace and must stay inside it. Paths that traverse out (``..``) or point elsewhere
(absolute paths outside the workspace) are refused fail-closed. Symlinks are followed during
resolution, so a symlink escaping the workspace is also refused.

This mirrors, for file operations, the cwd-scoped containment the SandboxManager already applies to
command execution — giving all runtime execution paths one workspace boundary.
"""

from __future__ import annotations

from pathlib import Path

from nexus.core.exceptions import WorkspaceConfinementError


def resolve_in_workspace(workspace: str, requested_path: str) -> Path:
    """Resolve ``requested_path`` within ``workspace``, fail-closed on escape/traversal.

    Args:
        workspace: The approved workspace root (e.g. the execution's repository directory).
        requested_path: The path requested by a runtime file tool (relative or absolute).

    Returns:
        The fully-resolved absolute path, guaranteed to be the workspace root or a descendant.

    Raises:
        WorkspaceConfinementError: if the resolved path lies outside the workspace.
    """
    ws = Path(workspace).resolve()
    requested = Path(requested_path)
    candidate = requested if requested.is_absolute() else ws / requested
    resolved = candidate.resolve()
    if not resolved.is_relative_to(ws):
        raise WorkspaceConfinementError(
            f"Path '{requested_path}' resolves outside the approved workspace '{ws}'. "
            "Refusing file access (fail-closed)."
        )
    return resolved
