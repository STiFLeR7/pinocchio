"""S-4 — Workspace confinement & R-05 closure (v1.1.0 Track S).

Establishes a single containment boundary for file operations: Nexus file tools must resolve every
path within the approved workspace and fail closed on traversal/escape — matching the containment
model already applied to command execution (cwd-scoped SandboxManager).

Evidence basis: A-006 R-05 / AP-105 Gap 7 (Nexus file-tool host bypass);
R-05-shared-resolution.md, S-1-runtime-containment-design.md.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.config import NexusSettings, SandboxConfig
from nexus.core.exceptions import WorkspaceConfinementError
from nexus.execution.runners.nexus_agent import NexusRuntimeAdapter
from nexus.execution.sandbox import resolve_in_workspace
from nexus.memory.models import ExecutionRecord, TaskRecord

# --------------------------------------------------------------------------- #
# Confinement seam (the Track-S-owned mechanism)                              #
# --------------------------------------------------------------------------- #


def test_valid_relative_path_allowed(tmp_path: Path) -> None:
    resolved = resolve_in_workspace(str(tmp_path), "a.txt")
    assert resolved == (tmp_path / "a.txt").resolve()


def test_valid_nested_path_allowed(tmp_path: Path) -> None:
    resolved = resolve_in_workspace(str(tmp_path), "sub/dir/a.txt")
    assert resolved == (tmp_path / "sub" / "dir" / "a.txt").resolve()


def test_absolute_inside_workspace_allowed(tmp_path: Path) -> None:
    inside = str(tmp_path / "inside.txt")
    resolved = resolve_in_workspace(str(tmp_path), inside)
    assert resolved == (tmp_path / "inside.txt").resolve()


def test_parent_traversal_denied(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceConfinementError):
        resolve_in_workspace(str(tmp_path), "../escape.txt")


def test_deep_traversal_denied(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceConfinementError):
        resolve_in_workspace(str(tmp_path), "../../../../../../etc/passwd")


def test_absolute_escape_denied(tmp_path: Path) -> None:
    outside = str(tmp_path.parent / "outside.txt")
    with pytest.raises(WorkspaceConfinementError):
        resolve_in_workspace(str(tmp_path), outside)


# --------------------------------------------------------------------------- #
# Nexus file tools confined (R-05 closure)                                   #
# --------------------------------------------------------------------------- #


async def _nexus_in_workspace(
    db_session: AsyncSession, workspace: Path, settings: NexusSettings | None = None
) -> NexusRuntimeAdapter:
    task = TaskRecord(
        id=uuid.uuid4(), title="t", description="goal:x", status="created", priority=1
    )
    db_session.add(task)
    await db_session.flush()
    exec_record = ExecutionRecord(
        id=uuid.uuid4(), task_id=task.id, runner="nexus", repository=str(workspace)
    )
    db_session.add(exec_record)
    await db_session.flush()
    return NexusRuntimeAdapter(db_session, exec_record.id, settings=settings)


@pytest.mark.asyncio
async def test_nexus_read_within_workspace_succeeds(db_session: AsyncSession, tmp_path: Path) -> None:
    (tmp_path / "in.txt").write_text("approved-content", encoding="utf-8")
    adapter = await _nexus_in_workspace(db_session, tmp_path)
    result = await adapter._execute_tool("read_file", {"path": "in.txt"})
    assert result == "approved-content"


@pytest.mark.asyncio
async def test_nexus_read_escape_denied(db_session: AsyncSession, tmp_path: Path) -> None:
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("TOPSECRET", encoding="utf-8")
    adapter = await _nexus_in_workspace(db_session, tmp_path)
    result = await adapter._execute_tool("read_file", {"path": "../secret.txt"})
    assert "TOPSECRET" not in result  # the file was NOT read
    assert "workspace" in result.lower() or "error" in result.lower()


@pytest.mark.asyncio
async def test_nexus_write_within_workspace_succeeds(db_session: AsyncSession, tmp_path: Path) -> None:
    adapter = await _nexus_in_workspace(db_session, tmp_path)
    result = await adapter._execute_tool("write_file", {"path": "out.txt", "content": "hello"})
    assert "error" not in result.lower()
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "hello"


@pytest.mark.asyncio
async def test_nexus_write_escape_denied(db_session: AsyncSession, tmp_path: Path) -> None:
    evil = tmp_path.parent / "evil.txt"
    adapter = await _nexus_in_workspace(db_session, tmp_path)
    result = await adapter._execute_tool("write_file", {"path": "../evil.txt", "content": "x"})
    assert not evil.exists()  # the file was NOT created outside the workspace
    assert "workspace" in result.lower() or "error" in result.lower()


@pytest.mark.asyncio
async def test_read_and_write_equally_constrained(db_session: AsyncSession, tmp_path: Path) -> None:
    """Both read and write reject an absolute path outside the workspace."""
    adapter = await _nexus_in_workspace(db_session, tmp_path)
    outside = str(tmp_path.parent / "x.txt")
    (tmp_path.parent / "x.txt").write_text("nope", encoding="utf-8")
    read_res = await adapter._execute_tool("read_file", {"path": outside})
    write_res = await adapter._execute_tool("write_file", {"path": outside, "content": "y"})
    assert "nope" not in read_res
    assert (tmp_path.parent / "x.txt").read_text(encoding="utf-8") == "nope"  # unchanged
    assert "error" in read_res.lower() or "workspace" in read_res.lower()
    assert "error" in write_res.lower() or "workspace" in write_res.lower()


@pytest.mark.asyncio
async def test_confinement_independent_of_provider(db_session: AsyncSession, tmp_path: Path) -> None:
    """Confinement is enforced at the path layer, so it holds under any sandbox provider config."""
    secret = tmp_path.parent / "docker_secret.txt"
    secret.write_text("CONTAINERSECRET", encoding="utf-8")
    settings = NexusSettings()
    settings.sandbox = SandboxConfig(enabled=True, provider="docker")
    adapter = await _nexus_in_workspace(db_session, tmp_path, settings=settings)
    result = await adapter._execute_tool("read_file", {"path": "../docker_secret.txt"})
    assert "CONTAINERSECRET" not in result
