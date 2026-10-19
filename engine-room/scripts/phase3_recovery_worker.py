"""Fresh-process fixture worker for Phase 3 durable action recovery evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Buffer
from dataclasses import replace
from pathlib import Path

from nexus_execution.actions import RepositoryAction
from nexus_human_interaction import build_human_interaction
from nexus_human_interaction.model import OperatorRequest
from nexus_infra import InfrastructureContext, build_durable_infrastructure


def _request(identity: str, workspace: Path) -> OperatorRequest:
    return OperatorRequest(
        identity=identity,
        request_text="Update the fixture marker with the approved text.",
        work_items=(),
        knowledge_subject="phase 3 recovery fixture",
        scope=f"phase3-{identity}",
        repository_root=str(workspace),
        repository_actions=(
            RepositoryAction.write(
                workspace_root=str(workspace),
                path="marker.txt",
                content="approved marker\n",
                actor="phase3-evaluator",
                request_identity=identity,
            ),
        ),
    )


def _events(
    infrastructure: InfrastructureContext, identity: str, workspace: Path
) -> list[dict[str, object]]:
    action_id = RepositoryAction.write(
        workspace_root=str(workspace),
        path="marker.txt",
        content="approved marker\n",
        actor="phase3-evaluator",
        request_identity=identity,
    ).identity
    return [
        {"id": event.identifier, "type": event.type, "payload": dict(event.payload)}
        for event in infrastructure.event_store.read_all()
        if event.identifier.startswith(f"evt-{action_id}-")
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("crash-after-write", "resume"))
    parser.add_argument("--db", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--identity", required=True)
    parser.add_argument("--dispatch-log", required=True)
    args = parser.parse_args()
    db = str(Path(args.db).resolve())
    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    target = workspace / "marker.txt"

    original = Path.write_bytes

    def count_target_write(path: Path, data: Buffer) -> int:
        result = original(path, data)
        if path.resolve() == target.resolve():
            with Path(args.dispatch_log).open("a", encoding="utf-8") as log:
                log.write("write\n")
            if args.mode == "crash-after-write":
                print("FAULT_INJECTED_AFTER_SIDE_EFFECT", flush=True)
                os._exit(86)
        return result

    from unittest.mock import patch

    with patch.object(Path, "write_bytes", count_target_write):
        return _run(args.mode, db, workspace, args.identity, target)


def _run(mode: str, db: str, workspace: Path, identity: str, target: Path) -> int:

    infrastructure = build_durable_infrastructure(db)
    facade = build_human_interaction(infrastructure, learning=False).facade
    request = _request(identity, workspace)
    if mode == "crash-after-write":
        pending = facade.submit(request)
        if not pending.awaiting_approval:
            raise RuntimeError("fixture write did not stop at human approval")
        facade.approve(request, pending.pending_approvals[0].node, decided_by="phase3-evaluator")
        raise RuntimeError("fault injector did not terminate after the write")

    resumed = facade.restart(replace(request, repository_actions=()))
    content = target.read_bytes() if target.exists() else b""
    digest = hashlib.sha256(content).hexdigest()
    trace = _events(infrastructure, identity, workspace)
    print(
        json.dumps(
            {
                "status": resumed.status,
                "succeeded": resumed.succeeded,
                "target_sha256": digest,
                "target_content": content.decode("utf-8"),
                "action_events": trace,
                "started_count": sum(
                    event["type"] == "repository_action.started" for event in trace
                ),
                "completed_count": sum(
                    event["type"] == "repository_action.completed" for event in trace
                ),
                "indeterminate_count": sum(
                    event["type"] == "repository_action.indeterminate" for event in trace
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
