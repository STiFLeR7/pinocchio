from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from nexus_execution.actions.boundary import (
    ActionDeniedError,
    RepositoryActionBoundary,
)
from tests.unit.nexus_execution.actions.helpers import authorized_fixture


def test_write_is_confined_and_captures_diff_and_hashes(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "README.md"
    target.write_bytes(b"before\n")
    fixture = authorized_fixture(str(workspace))
    infra = fixture.infra
    boundary = RepositoryActionBoundary(infra)
    action = fixture.action

    outcome = boundary.execute(action, authorization=fixture.authorization)

    assert target.read_text(encoding="utf-8") == "after\n"
    assert outcome.before_sha256 == hashlib.sha256(b"before\n").hexdigest()
    assert outcome.after_sha256 == hashlib.sha256(b"after\n").hexdigest()
    assert outcome.diff_ref is not None
    diff_event = next(
        event for event in infra.event_store.read_all() if event.identifier == outcome.diff_ref
    )
    diff = Path(str(diff_event.payload["path"])).read_text(encoding="utf-8")
    assert "-before" in diff
    assert "+after" in diff


@pytest.mark.parametrize("path", ["../outside.txt", "nested/../../outside.txt"])
def test_write_rejects_traversal_before_start(tmp_path: Path, path: str) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    fixture = authorized_fixture(str(workspace), path=path)
    infra = fixture.infra
    boundary = RepositoryActionBoundary(infra)
    action = fixture.action.model_copy(update={"path": path})

    with pytest.raises(ActionDeniedError):
        boundary.execute(action, authorization=fixture.authorization)

    assert not any(
        event.type == "repository_action.started" for event in infra.event_store.read_all()
    )


def test_write_rejects_symlink_component(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    target = outside / "secret.txt"
    target.write_text("secret", encoding="utf-8")
    (workspace / "link").symlink_to(target)
    fixture = authorized_fixture(str(workspace), path="link")
    infra = fixture.infra
    boundary = RepositoryActionBoundary(infra)

    with pytest.raises(ActionDeniedError):
        boundary.execute(
            fixture.action.model_copy(update={"path": "link"}),
            authorization=fixture.authorization,
        )

    assert target.read_text(encoding="utf-8") == "secret"
    assert not any(
        event.type == "repository_action.started" for event in infra.event_store.read_all()
    )


def test_repeating_the_same_denied_action_is_idempotent(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    fixture = authorized_fixture(str(workspace), path="../outside.txt")
    boundary = RepositoryActionBoundary(fixture.infra)

    for _ in range(2):
        with pytest.raises(ActionDeniedError):
            boundary.execute(fixture.action, authorization=fixture.authorization)

    denied = [
        event
        for event in fixture.infra.event_store.read_all()
        if event.type == "repository_action.denied"
    ]
    assert len(denied) == 1
    assert not any(
        event.type == "repository_action.started" for event in fixture.infra.event_store.read_all()
    )


def test_unlisted_command_is_denied_and_allowed_argv_uses_no_shell(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    fixture = authorized_fixture(str(workspace), kind="run_test", command_id="unlisted")
    infra = fixture.infra
    boundary = RepositoryActionBoundary(infra, command_allowlist=fixture.command_allowlist)
    action = fixture.action
    with pytest.raises(ActionDeniedError):
        boundary.execute(action, authorization=fixture.authorization)
    assert not any(
        event.type == "repository_action.started" for event in infra.event_store.read_all()
    )

    allowed = authorized_fixture(str(workspace), kind="run_test")
    allowed_boundary = RepositoryActionBoundary(
        allowed.infra, command_allowlist=allowed.command_allowlist
    )
    result = allowed_boundary.execute(allowed.action, authorization=allowed.authorization)
    assert result.exit_status == 0
    assert result.command_id == "fixture-test"
    assert result.argv == fixture.command_allowlist["fixture-test"]


def test_untrusted_direct_action_cannot_bypass_policy_or_approval(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    fixture = authorized_fixture(str(workspace))
    boundary = RepositoryActionBoundary(fixture.infra)
    target = workspace / "README.md"

    with pytest.raises(ActionDeniedError, match="Policy"):
        boundary.execute(
            fixture.action,
            authorization=fixture.authorization.model_copy(
                update={"policy_event_id": "missing-policy-event"}
            ),
        )
    with pytest.raises(ActionDeniedError, match="Approval Exchange"):
        boundary.execute(
            fixture.action,
            authorization=fixture.authorization.model_copy(
                update={"approval_event_id": "missing-approval-event"}
            ),
        )
    assert not target.exists()
