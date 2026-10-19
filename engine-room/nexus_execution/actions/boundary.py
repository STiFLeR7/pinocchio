"""Small Nexus-owned repository action boundary with durable request/result facts."""

from __future__ import annotations

import difflib
import hashlib
import os
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from nexus_core.contracts.base import Reference, ValueObject
from nexus_core.domain.event import Event
from nexus_infra import InfrastructureContext, content_hash
from nexus_runtime.events import SystemTimestampSource, TimestampSource

ACTION_REQUESTED = "repository_action.requested"
ACTION_STARTED = "repository_action.started"
ACTION_COMPLETED = "repository_action.completed"
ACTION_DENIED = "repository_action.denied"
ACTION_INDETERMINATE = "repository_action.indeterminate"
ACTION_CANCELLED = "repository_action.cancelled"
ACTION_ARTIFACT = "repository_action.artifact"
ACTION_CLASS = "repository_action"


class ActionDeniedError(RuntimeError):
    """A repository action failed its explicit boundary checks."""


class RepositoryAction(ValueObject):
    """One explicit action; command argv is resolved only from the injected allow-list."""

    kind: str
    workspace_root: str
    actor: str
    request_identity: str
    work_item_key: str = "respond"
    path: str | None = None
    content: str | None = None
    command_id: str | None = None
    resolved_argv: tuple[str, ...] = ()
    correlation_identifier: str = ""

    @classmethod
    def write(
        cls,
        *,
        workspace_root: str,
        path: str,
        content: str,
        actor: str,
        request_identity: str,
        work_item_key: str = "respond",
        correlation: str = "",
    ) -> RepositoryAction:
        return cls(
            kind="write_file",
            workspace_root=workspace_root,
            path=path,
            content=content,
            actor=actor,
            request_identity=request_identity,
            work_item_key=work_item_key,
            correlation_identifier=correlation,
        )

    @classmethod
    def read(
        cls,
        *,
        workspace_root: str,
        path: str,
        actor: str,
        request_identity: str,
        work_item_key: str = "respond",
        correlation: str = "",
    ) -> RepositoryAction:
        return cls(
            kind="read_file",
            workspace_root=workspace_root,
            path=path,
            actor=actor,
            request_identity=request_identity,
            work_item_key=work_item_key,
            correlation_identifier=correlation,
        )

    @classmethod
    def run_test(
        cls,
        *,
        workspace_root: str,
        command_id: str,
        actor: str,
        request_identity: str,
        work_item_key: str = "respond",
        correlation: str = "",
        resolved_argv: tuple[str, ...] = (),
    ) -> RepositoryAction:
        return cls(
            kind="run_test",
            workspace_root=workspace_root,
            command_id=command_id,
            resolved_argv=resolved_argv,
            actor=actor,
            request_identity=request_identity,
            work_item_key=work_item_key,
            correlation_identifier=correlation,
        )

    @property
    def input_digest(self) -> str:
        data = self.model_dump(
            mode="json", exclude={"correlation_identifier", "request_identity", "work_item_key"}
        )
        if os.path.isdir(str(data["workspace_root"])):
            data["workspace_root"] = _canonical_root(str(data["workspace_root"]))
        return content_hash(data)

    @property
    def identity(self) -> str:
        return f"action-{content_hash({'request': self.request_identity, 'item': self.work_item_key, 'digest': self.input_digest})[:24]}"


class ActionOutcome(ValueObject):
    """Durable, safe-to-project result of one repository action."""

    action_id: str
    kind: str
    status: str
    input_digest: str
    actor: str
    workspace_root: str
    path: str | None = None
    before_sha256: str | None = None
    after_sha256: str | None = None
    diff: str = ""
    diff_ref: str | None = None
    output_ref: str | None = None
    command_id: str | None = None
    argv: tuple[str, ...] = ()
    exit_status: int | None = None
    event_refs: tuple[str, ...] = ()


class ActionRequestPayload(ValueObject):
    action: RepositoryAction
    input_digest: str


class ActionAuthorization(ValueObject):
    """References to durable policy, approval, plan, and node facts for one dispatch."""

    policy_event_id: str
    plan_identity: str
    pipeline_session: str
    node: str
    approval_event_id: str | None = None


@dataclass(frozen=True, slots=True)
class _SafeTarget:
    path: Path
    relative: str


class RepositoryActionBoundary:
    """Validate confinement, dispatch one bounded action, and record each lifecycle fact."""

    def __init__(
        self,
        infrastructure: InfrastructureContext,
        *,
        command_allowlist: Mapping[str, tuple[str, ...]] | None = None,
        artifact_directory: str | Path | None = None,
        timestamps: TimestampSource | None = None,
    ) -> None:
        self._infra = infrastructure
        self._commands = dict(command_allowlist or {})
        self._artifact_directory = Path(
            artifact_directory or Path(tempfile.gettempdir()) / "nexus-action-artifacts"
        )
        self._timestamps = timestamps or SystemTimestampSource()

    def execute(
        self,
        action: RepositoryAction,
        *,
        authorization: ActionAuthorization,
        control: object | None = None,
    ) -> ActionOutcome:
        try:
            return self._execute_checked(action, authorization=authorization, control=control)
        except ActionDeniedError as exc:
            if not bool(getattr(control, "cancelled", False)):
                self._emit(
                    action,
                    ACTION_DENIED,
                    f"denied-{content_hash({'reason': str(exc)})[:12]}",
                    {"input_digest": action.input_digest, "reason": str(exc)},
                )
            raise

    def _execute_checked(
        self,
        action: RepositoryAction,
        *,
        authorization: ActionAuthorization,
        control: object | None = None,
    ) -> ActionOutcome:
        self._validate_authorization(action, authorization)
        root = _canonical_root(action.workspace_root)
        if action.kind not in {"read_file", "write_file", "run_test"}:
            raise ActionDeniedError(f"unsupported action kind: {action.kind}")
        target = _safe_target(root, action.path) if action.kind != "run_test" else None
        argv: tuple[str, ...] = ()
        if bool(getattr(control, "cancelled", False)):
            self._emit(
                action,
                ACTION_CANCELLED,
                "cancelled",
                {"action_id": action.identity, "input_digest": action.input_digest},
            )
            raise ActionDeniedError("action cancelled before start")
        if action.kind == "run_test":
            if action.command_id is None or action.command_id not in self._commands:
                raise ActionDeniedError("test command is not allow-listed")
            argv = self._commands[action.command_id]
            if action.resolved_argv != argv:
                raise ActionDeniedError(
                    "test command argv differs from the immutable approved request"
                )
            if not argv:
                raise ActionDeniedError("allow-listed test command has empty argv")
        if action.kind == "write_file" and action.content is None:
            raise ActionDeniedError("write action requires content")
        if action.kind == "read_file" and target is None:
            raise ActionDeniedError("read action requires a path")

        completed = self._completed(action.identity)
        if completed is not None:
            return ActionOutcome.model_validate(completed.payload["outcome"])
        started = self._started(action.identity)
        if started is not None:
            self._emit(
                action,
                ACTION_INDETERMINATE,
                "indeterminate",
                {"action_id": action.identity, "input_digest": action.input_digest},
            )
            raise ActionDeniedError("action is indeterminate; reconciliation is required")

        self._emit(
            action,
            ACTION_STARTED,
            "started",
            {
                "action_id": action.identity,
                "input_digest": action.input_digest,
                "kind": action.kind,
                "actor": action.actor,
                "request_identity": action.request_identity,
                "work_item_key": action.work_item_key,
                "workspace_root": root,
                "path": target.relative if target else None,
                "command_id": action.command_id,
                "argv": list(argv),
                "plan": authorization.plan_identity,
                "pipeline_session": authorization.pipeline_session,
                "node": authorization.node,
                "policy_event": authorization.policy_event_id,
                "approval_event": authorization.approval_event_id,
            },
        )
        before: bytes | None = None
        diff = ""
        output = ""
        exit_status: int | None = None
        relative = target.relative if target else None
        if action.kind == "read_file":
            assert target is not None
            output = target.path.read_text(encoding="utf-8")
            before = target.path.read_bytes()
        elif action.kind == "write_file":
            assert target is not None and action.content is not None
            before = target.path.read_bytes() if target.path.exists() else b""
            old_text = before.decode("utf-8", errors="replace").splitlines(keepends=True)
            new_text = action.content.splitlines(keepends=True)
            diff = "".join(
                difflib.unified_diff(
                    old_text, new_text, fromfile=relative or "", tofile=relative or ""
                )
            )
            target.path.parent.mkdir(parents=True, exist_ok=True)
            _safe_target(root, action.path)
            target.path.write_bytes(action.content.encode("utf-8"))
        else:
            completed_process = subprocess.run(
                argv,
                cwd=root,
                shell=False,
                check=False,
                capture_output=True,
                text=True,
            )
            exit_status = completed_process.returncode
            output = completed_process.stdout + completed_process.stderr

        after: bytes | None = None
        if target is not None and target.path.exists():
            after = target.path.read_bytes()
        outcome = ActionOutcome(
            action_id=action.identity,
            kind=action.kind,
            status="completed" if exit_status in (None, 0) else "failed",
            input_digest=action.input_digest,
            actor=action.actor,
            workspace_root=root,
            path=relative,
            before_sha256=_sha256(before),
            after_sha256=_sha256(after),
            diff_ref=None,
            output_ref=None,
            command_id=action.command_id,
            argv=argv,
            exit_status=exit_status,
        )
        artifact_refs: list[str] = []
        if diff:
            diff_ref = self._store_artifact(action, "diff", diff)
            artifact_refs.append(
                self._emit(
                    action,
                    ACTION_ARTIFACT,
                    "artifact-diff",
                    {
                        "artifact_id": f"{action.identity}-diff",
                        "kind": "unified_diff",
                        "path": str(diff_ref),
                        "sha256": hashlib.sha256(diff.encode("utf-8")).hexdigest(),
                    },
                ).identifier
            )
            outcome = outcome.model_copy(update={"diff_ref": artifact_refs[-1]})
        if output:
            output_ref = self._store_artifact(action, "output", output)
            artifact_refs.append(
                self._emit(
                    action,
                    ACTION_ARTIFACT,
                    "artifact-output",
                    {
                        "artifact_id": f"{action.identity}-output",
                        "kind": "action_output",
                        "path": str(output_ref),
                        "sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
                    },
                ).identifier
            )
            outcome = outcome.model_copy(update={"output_ref": artifact_refs[-1]})
        outcome = outcome.model_copy(update={"event_refs": tuple(artifact_refs)})
        event = self._emit(
            action,
            ACTION_COMPLETED,
            "completed",
            {
                "plan": authorization.plan_identity,
                "pipeline_session": authorization.pipeline_session,
                "node": authorization.node,
                "policy_event": authorization.policy_event_id,
                "approval_event": authorization.approval_event_id,
                # Diff and command output live in content-addressed artifacts; durable events
                # retain only hashes and references so they never contain repository content.
                "outcome": outcome.model_dump(mode="json", exclude={"diff"}),
            },
        )
        return outcome.model_copy(update={"event_refs": (*artifact_refs, event.identifier)})

    def _store_artifact(self, action: RepositoryAction, kind: str, content: str) -> Path:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        directory = self._artifact_directory / action.identity
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{kind}-{digest}.txt"
        if not path.exists():
            path.write_text(content, encoding="utf-8", newline="")
        return path

    def _validate_authorization(
        self, action: RepositoryAction, authorization: ActionAuthorization
    ) -> None:
        events = tuple(self._infra.event_store.read_all())
        request_event = next(
            (
                event
                for event in events
                if event.type == ACTION_REQUESTED
                and event.producer == "repository_action"
                and event.payload.get("action_id") == action.identity
            ),
            None,
        )
        if request_event is None:
            raise ActionDeniedError("the durable action request is missing")
        recorded_action = RepositoryAction.model_validate(request_event.payload.get("action"))
        if (
            recorded_action.model_dump(mode="json") != action.model_dump(mode="json")
            or request_event.payload.get("input_digest") != action.input_digest
        ):
            raise ActionDeniedError("action input does not match its immutable request")
        policy = next(
            (
                event
                for event in events
                if event.identifier == authorization.policy_event_id
                and event.type == "policy.evaluated"
                and event.producer == "policy"
            ),
            None,
        )
        if policy is None or policy.payload.get("decision") != "allow":
            raise ActionDeniedError("a matching Policy ALLOW event is required")
        attributes = policy.payload.get("attributes")
        if (
            policy.payload.get("action_class") != ACTION_CLASS
            or not isinstance(attributes, Mapping)
            or any(
                attributes.get(key) != value
                for key, value in {
                    "action_id": action.identity,
                    "input_digest": action.input_digest,
                    "workspace_root": _canonical_root(action.workspace_root),
                    "plan_identity": authorization.plan_identity,
                    "pipeline_session": authorization.pipeline_session,
                    "node": authorization.node,
                    "actor": action.actor,
                    "request_identity": action.request_identity,
                    "work_item_key": action.work_item_key,
                }.items()
            )
        ):
            raise ActionDeniedError("Policy event does not authorize this exact action input")

        plan_event = next(
            (
                event
                for event in events
                if event.type == "planning.execution_plan_assembled"
                and event.producer == "planning"
                and event.payload.get("execution_plan", {}).get("identity")
                == authorization.plan_identity
            ),
            None,
        )
        if plan_event is None:
            raise ActionDeniedError("the frozen plan binding is missing")
        try:
            from nexus_planning.grounded.model import ExecutionPlan

            plan = ExecutionPlan.model_validate(plan_event.payload["execution_plan"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ActionDeniedError("the frozen plan binding is invalid") from exc
        work_package_ids = {
            node.work_package_ref.identifier
            for node in plan.execution_graph.nodes
            if node.identifier == authorization.node
        }
        action_refs = {
            ref.identifier
            for package in plan.work_packages
            if package.identifier in work_package_ids
            for ref in package.inputs
            if ref.target_type == "action_request"
        }
        if action.identity not in action_refs:
            raise ActionDeniedError("the plan node is not bound to this action")
        if authorization.pipeline_session != f"pipe-{action.request_identity}":
            raise ActionDeniedError("approval session does not own this action request")
        if plan.goal_ref.identifier != f"goal-{action.request_identity}":
            raise ActionDeniedError("frozen plan does not belong to this action request")
        if action.kind == "write_file":
            approval = next(
                (
                    event
                    for event in events
                    if event.identifier == authorization.approval_event_id
                    and event.type == "approval.approved"
                    and event.producer == "approval_exchange"
                    and event.payload.get("session") == authorization.pipeline_session
                    and event.payload.get("node") == authorization.node
                ),
                None,
            )
            if approval is None:
                raise ActionDeniedError("a matching human Approval Exchange event is required")

    def _events(self, action_id: str) -> tuple[Event, ...]:
        return tuple(
            event
            for event in self._infra.event_store.read_all()
            if event.type.startswith("repository_action.")
            and event.payload.get("action_id") == action_id
        )

    def _completed(self, action_id: str) -> Event | None:
        return next(
            (e for e in reversed(self._events(action_id)) if e.type == ACTION_COMPLETED), None
        )

    def _started(self, action_id: str) -> Event | None:
        return next(
            (e for e in reversed(self._events(action_id)) if e.type == ACTION_STARTED), None
        )

    def _emit(
        self, action: RepositoryAction, event_type: str, suffix: str, payload: dict[str, object]
    ) -> Event:
        full: dict[str, object] = {"action_id": action.identity, **payload}
        identifier = f"evt-{action.identity}-{suffix}-{content_hash(full)[:16]}"
        existing = next(
            (
                event
                for event in self._infra.event_store.read_all()
                if event.identifier == identifier
            ),
            None,
        )
        if existing is not None:
            if existing.type != event_type or existing.payload != full:
                raise RuntimeError(f"repository action event ID collision: {identifier}")
            return existing
        event = Event(
            identifier=identifier,
            type=event_type,
            version="1",
            timestamp=self._timestamps.now(),
            producer="repository_action",
            correlation_identifier=action.correlation_identifier or f"cor-{action.identity}",
            execution_identifier=None,
            payload=full,
            source="nexus_execution.actions",
        )
        self._infra.emit(event)
        return event


def record_action_request(
    infrastructure: InfrastructureContext,
    action: RepositoryAction,
    *,
    timestamps: TimestampSource | None = None,
) -> Reference:
    """Persist the exact action input before planning and return its WorkItem input reference."""
    canonical = action.model_copy(update={"workspace_root": _canonical_root(action.workspace_root)})
    payload = {
        "action_id": canonical.identity,
        "action": canonical.model_dump(mode="json"),
        "input_digest": canonical.input_digest,
    }
    identifier = f"evt-{canonical.identity}-requested"
    timestamp = (timestamps or SystemTimestampSource()).now()
    event = Event(
        identifier=identifier,
        type=ACTION_REQUESTED,
        version="1",
        timestamp=timestamp,
        producer="repository_action",
        correlation_identifier=canonical.correlation_identifier or f"cor-{canonical.identity}",
        execution_identifier=None,
        payload=payload,
        source="nexus_execution.actions",
    )
    if not infrastructure.event_store.contains(identifier):
        infrastructure.emit(event)
    else:
        existing = next(
            e for e in infrastructure.event_store.read_all() if e.identifier == identifier
        )
        if existing.payload != payload:
            raise ValueError("action identity is already bound to different input")
    return Reference(target_type="action_request", identifier=canonical.identity)


def resolve_action_request(
    infrastructure: InfrastructureContext, reference: Reference
) -> RepositoryAction:
    if reference.target_type != "action_request":
        raise ActionDeniedError("work package input is not an action request")
    event = next(
        (
            event
            for event in infrastructure.event_store.read_all()
            if event.type == ACTION_REQUESTED
            and event.payload.get("action_id") == reference.identifier
        ),
        None,
    )
    if event is None:
        raise ActionDeniedError("durable action request is missing")
    action = RepositoryAction.model_validate(event.payload["action"])
    if action.identity != reference.identifier or action.input_digest != event.payload.get(
        "input_digest"
    ):
        raise ActionDeniedError("durable action request digest does not match its reference")
    return action


def action_is_indeterminate(infrastructure: InfrastructureContext, action_id: str) -> bool:
    """Whether a durable start has no terminal result; callers must halt before Actuation."""
    events = tuple(
        event
        for event in infrastructure.event_store.read_all()
        if event.type.startswith("repository_action.")
        and event.payload.get("action_id") == action_id
    )
    return any(event.type == ACTION_STARTED for event in events) and not any(
        event.type == ACTION_COMPLETED for event in events
    )


def action_is_cancelled(infrastructure: InfrastructureContext, action_id: str) -> bool:
    """Whether a durable cancellation fact makes this action terminally non-dispatchable."""
    return any(
        event.type == ACTION_CANCELLED
        and event.producer == "repository_action"
        and event.payload.get("action_id") == action_id
        for event in infrastructure.event_store.read_all()
    )


def record_indeterminate(infrastructure: InfrastructureContext, action: RepositoryAction) -> None:
    """Record a stable reconciliation marker after an observed started-without-terminal action."""
    identifier = f"evt-{action.identity}-indeterminate"
    if infrastructure.event_store.contains(identifier):
        return
    event = Event(
        identifier=identifier,
        type=ACTION_INDETERMINATE,
        version="1",
        timestamp=SystemTimestampSource().now(),
        producer="repository_action",
        correlation_identifier=action.correlation_identifier or f"cor-{action.identity}",
        execution_identifier=None,
        payload={
            "action_id": action.identity,
            "input_digest": action.input_digest,
            "status": "indeterminate",
        },
        source="nexus_execution.actions",
    )
    infrastructure.emit(event)


def record_action_denial(
    infrastructure: InfrastructureContext, action: RepositoryAction, reason: str
) -> None:
    identifier = f"evt-{action.identity}-denied-{content_hash({'reason': reason})[:12]}"
    if infrastructure.event_store.contains(identifier):
        return
    infrastructure.emit(
        Event(
            identifier=identifier,
            type=ACTION_DENIED,
            version="1",
            timestamp=SystemTimestampSource().now(),
            producer="repository_action",
            correlation_identifier=action.correlation_identifier or f"cor-{action.identity}",
            execution_identifier=None,
            payload={
                "action_id": action.identity,
                "input_digest": action.input_digest,
                "reason": reason,
            },
            source="nexus_execution.actions",
        )
    )


def record_action_cancelled(
    infrastructure: InfrastructureContext, action: RepositoryAction, reason: str
) -> None:
    identifier = f"evt-{action.identity}-cancelled"
    if infrastructure.event_store.contains(identifier):
        return
    infrastructure.emit(
        Event(
            identifier=identifier,
            type=ACTION_CANCELLED,
            version="1",
            timestamp=SystemTimestampSource().now(),
            producer="repository_action",
            correlation_identifier=action.correlation_identifier or f"cor-{action.identity}",
            execution_identifier=None,
            payload={
                "action_id": action.identity,
                "input_digest": action.input_digest,
                "reason": reason,
            },
            source="nexus_execution.actions",
        )
    )


def _canonical_root(root: str) -> str:
    resolved = os.path.realpath(root)
    if not os.path.isdir(resolved):
        raise ActionDeniedError("workspace root must be an existing directory")
    return resolved


def _safe_target(root: str, relative: str | None) -> _SafeTarget:
    if not relative or os.path.isabs(relative):
        raise ActionDeniedError("action path must be a non-empty workspace-relative path")
    normalized = relative.replace("\\", "/")
    parts = Path(normalized).parts
    if any(part in {"..", "."} for part in parts):
        raise ActionDeniedError("path traversal is not allowed")
    candidate = Path(root)
    for part in parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ActionDeniedError("symlink path components are not allowed")
    resolved = os.path.realpath(candidate)
    if os.path.commonpath((root, resolved)) != root:
        raise ActionDeniedError("action path escapes the workspace")
    return _SafeTarget(Path(resolved), normalized)


def _sha256(value: bytes | None) -> str | None:
    return hashlib.sha256(value).hexdigest() if value is not None else None
