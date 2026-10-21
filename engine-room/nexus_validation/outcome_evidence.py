"""Bounded independent evidence checks for frozen file and JUnit conditions."""

from __future__ import annotations

import hashlib
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from nexus_core.contracts.base import Reference
from nexus_execution.actions.boundary import RepositoryAction
from nexus_infra import content_hash
from nexus_validation import ids
from nexus_validation.evidence import Evidence
from nexus_validation.report import RuleResult
from nexus_validation.rules import RuleContext, _result
from nexus_validation.vocabulary import EvidenceSource, RuleOutcome

MAX_EVIDENCE_BYTES = 2 * 1024 * 1024
MAX_DECLARED_PATHS = 8


class OutcomeConditionEvaluator:
    """Evaluate bounded acceptance facts from the frozen package and durable action lineage."""

    def evaluate(self, context: RuleContext) -> tuple[RuleResult, tuple[Evidence, ...]]:
        criteria = context.work_package.completion_criteria
        conditions = criteria.get("outcome_conditions")
        if not isinstance(conditions, (list, tuple)) or not conditions:
            if context.policy.require_explicit_conditions:
                return (
                    _result(
                        "outcome_conditions",
                        RuleOutcome.INSUFFICIENT_EVIDENCE,
                        "no explicit testable outcome conditions were frozen before actuation",
                    ),
                    (),
                )
            return (
                _result("outcome_conditions", RuleOutcome.NOT_APPLICABLE, "no outcome conditions"),
                (),
            )
        if len(conditions) > 32:
            return (
                _result(
                    "outcome_conditions",
                    RuleOutcome.INSUFFICIENT_EVIDENCE,
                    "outcome condition list exceeds the bounded limit",
                ),
                (),
            )

        condition_digest = content_hash(_canonical_json(conditions))
        action, action_events, action_error = self._bound_action(context)
        workspace = action.workspace_root if action is not None else None
        preflight = self._preflight(
            context, conditions, action, action_events, action_error, workspace
        )
        if preflight:
            return (
                _result(
                    "outcome_conditions",
                    RuleOutcome.INSUFFICIENT_EVIDENCE,
                    "; ".join(preflight) + f" (conditions sha256 {condition_digest})",
                ),
                (),
            )
        source_bytes: dict[tuple[str, str], bytes] = {}
        for condition in conditions:
            if not isinstance(condition, dict):
                continue
            paths = (
                [condition.get("path")]
                if condition.get("type") == "file_sha256"
                else condition.get("paths", [])
            )
            root = (
                workspace
                if condition.get("type") == "file_sha256"
                else (action.workspace_root if action is not None else None)
            )
            if not root or not isinstance(paths, (list, tuple)):
                continue
            for relative in paths:
                if isinstance(relative, str):
                    data = _read_confined(root, relative)
                    if data is not None:
                        source_bytes[(root, relative)] = data
        evidence: list[Evidence] = []
        states: list[bool] = []
        condition_outcomes: list[str] = []
        missing: list[str] = []
        conflicts: list[str] = []
        for index, condition in enumerate(conditions):
            if not isinstance(condition, dict):
                missing.append(f"condition {index + 1} has invalid shape")
                continue
            condition_id = str(condition.get("id", f"condition-{index + 1}"))
            kind = condition.get("type")
            if kind == "file_sha256":
                result = self._file_condition(
                    context,
                    condition,
                    condition_id,
                    condition_digest,
                    workspace,
                    index,
                    source_bytes,
                )
                if result is None:
                    missing.append(f"{condition_id}: file evidence is missing or unsafe")
                else:
                    item, passed = result
                    evidence.append(item)
                    states.append(passed)
                    condition_outcomes.append(
                        f"{condition_id}={'satisfied' if passed else 'violated'}"
                    )
            elif kind == "junit_xml":
                if action_error or action is None:
                    missing.append(f"{condition_id}: {action_error or 'action binding is absent'}")
                    continue
                report_results, error = self._junit_condition(
                    context,
                    condition,
                    condition_id,
                    condition_digest,
                    action,
                    action_events,
                    index,
                    source_bytes,
                )
                evidence.extend(report_results)
                if error:
                    missing.append(f"{condition_id}: {error}")
                    continue
                report_states = [bool(item.observed.get("passed")) for item in report_results]
                if report_states and any(state != report_states[0] for state in report_states):
                    conflicts.append(f"{condition_id}: valid JUnit reports conflict")
                elif report_states:
                    states.append(report_states[0])
                    condition_outcomes.append(
                        f"{condition_id}={'satisfied' if report_states[0] else 'violated'}"
                    )
                else:
                    missing.append(f"{condition_id}: no JUnit reports were evaluated")
            else:
                missing.append(f"{condition_id}: unsupported condition type")

        refs = tuple(item.reference() for item in evidence)
        if conflicts:
            outcome = RuleOutcome.INSUFFICIENT_EVIDENCE
            rationale = "; ".join(conflicts)
        elif missing:
            outcome = RuleOutcome.INSUFFICIENT_EVIDENCE
            rationale = "; ".join(missing)
        elif states and all(states):
            outcome = RuleOutcome.SATISFIED
            rationale = "all frozen outcome conditions were independently satisfied"
        elif states and not any(states):
            outcome = RuleOutcome.VIOLATED
            rationale = "all evaluated frozen outcome conditions were violated"
        elif states:
            outcome = RuleOutcome.PARTIAL
            rationale = "some frozen outcome conditions passed and others failed"
        else:
            outcome = RuleOutcome.INSUFFICIENT_EVIDENCE
            rationale = "no frozen outcome conditions could be evaluated"
        if condition_outcomes:
            rationale += "; outcomes: " + ", ".join(condition_outcomes)
        return (
            RuleResult(
                rule_id="outcome_conditions",
                outcome=outcome,
                rationale=f"{rationale} (conditions sha256 {condition_digest})",
                evidence_refs=refs,
            ),
            tuple(evidence),
        )

    def _preflight(
        self,
        context: RuleContext,
        conditions: object,
        action: RepositoryAction | None,
        action_events: tuple[Any, ...],
        action_error: str | None,
        workspace: str | None,
    ) -> list[str]:
        """Validate every declared source path before any file bytes are read."""
        if not isinstance(conditions, (list, tuple)) or len(conditions) > 32:
            return ["outcome condition list exceeds the bounded limit or is invalid"]
        errors: list[str] = []
        for index, condition in enumerate(conditions):
            if not isinstance(condition, dict):
                errors.append(f"condition {index + 1} has invalid shape")
                continue
            condition_id = str(condition.get("id", f"condition-{index + 1}"))
            kind = condition.get("type")
            if kind == "file_sha256":
                path = condition.get("path")
                expected = condition.get("expected_sha256")
                if workspace is None or not isinstance(path, str) or not _valid_sha(expected):
                    errors.append(f"{condition_id}: invalid file path or digest")
                elif _confined_path(workspace, path) is None:
                    errors.append(f"{condition_id}: file path is missing, unsafe, or oversized")
            elif kind == "junit_xml":
                paths = condition.get("paths")
                if action_error or action is None:
                    errors.append(f"{condition_id}: {action_error or 'action binding is absent'}")
                if (
                    not isinstance(paths, (list, tuple))
                    or not paths
                    or len(paths) > MAX_DECLARED_PATHS
                ):
                    errors.append(f"{condition_id}: invalid or excessive JUnit paths")
                elif workspace is None or any(
                    not isinstance(path, str) or _confined_path(workspace, path) is None
                    for path in paths
                ):
                    errors.append(f"{condition_id}: a JUnit path is missing, unsafe, or oversized")
                if action is not None:
                    completed = next(
                        (
                            event
                            for event in action_events
                            if event.type == "repository_action.completed"
                        ),
                        None,
                    )
                    outcome = completed.payload.get("outcome") if completed is not None else None
                    artifact_ref = outcome.get("output_ref") if isinstance(outcome, dict) else None
                    artifact = next(
                        (
                            event
                            for event in context.events
                            if event.identifier == artifact_ref
                            and event.type == "repository_action.artifact"
                            and event.payload.get("action_id") == action.identity
                            and event.payload.get("kind") == "action_output"
                        ),
                        None,
                    )
                    artifact_path = artifact.payload.get("path") if artifact is not None else None
                    artifact_root = context.policy.action_artifact_directory
                    if (
                        not isinstance(artifact_path, str)
                        or not artifact_root
                        or _artifact_relative_path(
                            artifact_path,
                            artifact_root,
                            action.identity,
                            str(artifact.payload.get("sha256", "")) if artifact is not None else "",
                        )
                        is None
                    ):
                        errors.append(f"{condition_id}: action output artifact path is invalid")
            else:
                errors.append(f"{condition_id}: unsupported condition type")
        return errors

    def _file_condition(
        self,
        context: RuleContext,
        condition: dict[str, Any],
        condition_id: str,
        condition_digest: str,
        workspace: str | None,
        index: int,
        source_bytes: dict[tuple[str, str], bytes],
    ) -> tuple[Evidence, bool] | None:
        relative = condition.get("path")
        expected = condition.get("expected_sha256")
        if (
            workspace is None
            or not isinstance(relative, str)
            or not isinstance(expected, str)
            or not _valid_sha(expected)
        ):
            return None
        data = source_bytes.get((workspace, relative))
        if data is None:
            return None
        digest = hashlib.sha256(data).hexdigest()
        passed = digest == expected.lower()
        action_ref = next(
            (ref for ref in context.work_package.inputs if ref.target_type == "action_request"),
            None,
        )
        request_event = next(
            (
                event
                for event in context.events
                if action_ref is not None
                and event.type == "repository_action.requested"
                and event.payload.get("action_id") == action_ref.identifier
            ),
            None,
        )
        return (
            self._evidence(
                context,
                index,
                "file_sha256",
                {
                    "condition_id": condition_id,
                    "condition_digest": condition_digest,
                    "path": relative.replace("\\", "/"),
                    "sha256": digest,
                    "expected_sha256": expected.lower(),
                    "passed": passed,
                    "action_id": action_ref.identifier if action_ref is not None else None,
                    "action_digest": request_event.payload.get("input_digest")
                    if request_event is not None
                    else None,
                },
                (Reference(target_type="event", identifier=request_event.identifier),)
                if request_event is not None
                else (),
            ),
            passed,
        )

    def _junit_condition(
        self,
        context: RuleContext,
        condition: dict[str, Any],
        condition_id: str,
        condition_digest: str,
        action: RepositoryAction,
        action_events: tuple[Any, ...],
        index: int,
        source_bytes: dict[tuple[str, str], bytes],
    ) -> tuple[list[Evidence], str | None]:
        paths = condition.get("paths")
        if (
            condition.get("command_id") != action.command_id
            or action.kind != "run_test"
            or not isinstance(paths, (list, tuple))
            or not paths
            or len(paths) > MAX_DECLARED_PATHS
        ):
            return [], "condition does not bind a named run_test action and bounded paths"
        workspace = action.workspace_root
        completed = next(
            (event for event in action_events if event.type == "repository_action.completed"), None
        )
        started = next(
            (event for event in action_events if event.type == "repository_action.started"), None
        )
        if completed is None or started is None:
            return [], "action has no matching start and completion facts"
        outcome = completed.payload.get("outcome")
        if not isinstance(outcome, dict):
            return [], "completed action outcome is malformed"
        plan_id = context.work_package.parent_plan.identifier
        runtime_session = context.result.session_ref.identifier
        runtime_created = tuple(
            event
            for event in context.events
            if event.type == "runtime.session_created"
            and event.producer == "runtime"
            and event.identifier.startswith(f"evt-{runtime_session}-created-")
        )
        if len(runtime_created) != 1:
            return [], "matching runtime session creation fact is absent or ambiguous"
        runtime_node = runtime_created[0].payload.get("node")
        if (
            completed.payload.get("action_id") != action.identity
            or started.payload.get("input_digest") != action.input_digest
            or outcome.get("action_id") != action.identity
            or outcome.get("input_digest") != action.input_digest
            or outcome.get("workspace_root") != workspace
            or outcome.get("command_id") != action.command_id
            or outcome.get("status") != "completed"
            or started.payload.get("action_id") != action.identity
            or started.payload.get("workspace_root") != workspace
            or completed.payload.get("plan") != started.payload.get("plan")
            or completed.payload.get("node") != started.payload.get("node")
            or completed.payload.get("pipeline_session") != started.payload.get("pipeline_session")
            or completed.payload.get("plan") != plan_id
            or runtime_node != started.payload.get("node")
        ):
            return [], "action lineage does not match the frozen work package"
        output_ref = outcome.get("output_ref")
        artifact = next(
            (
                event
                for event in context.events
                if event.identifier == output_ref
                and event.type == "repository_action.artifact"
                and event.payload.get("action_id") == action.identity
                and event.payload.get("kind") == "action_output"
            ),
            None,
        )
        if artifact is None:
            return [], "completed action output artifact reference is absent or mismatched"
        artifact_path = artifact.payload.get("path")
        artifact_root = context.policy.action_artifact_directory
        if not isinstance(artifact_path, str) or not artifact_root:
            return [], "trusted action artifact directory is not configured"
        artifact_digest = str(artifact.payload.get("sha256", ""))
        artifact_relative = _artifact_relative_path(
            artifact_path, artifact_root, action.identity, artifact_digest
        )
        if artifact_relative is None:
            return [], "action output artifact is not content-addressed for this action"
        output_bytes = _read_confined(artifact_root, artifact_relative)
        if output_bytes is None or hashlib.sha256(output_bytes).hexdigest() != artifact_digest:
            return [], "action output artifact digest is invalid"
        evidence: list[Evidence] = []
        report_bytes: list[bytes] = []
        states: list[bool] = []
        for path_index, relative in enumerate(paths):
            if not isinstance(relative, str):
                return [], "JUnit path is invalid"
            data = source_bytes.get((workspace, relative))
            if data is None:
                return evidence, f"required report {relative} is missing, unsafe, or oversized"
            report_bytes.append(data)
            digest = hashlib.sha256(data).hexdigest()
            try:
                root = ET.fromstring(data)
            except (ET.ParseError, ValueError):
                return evidence, f"required report {relative} is malformed XML"
            if _local(root.tag) not in {"testsuite", "testsuites"}:
                return evidence, f"required report {relative} is not JUnit XML"
            cases = [node for node in root.iter() if _local(node.tag) == "testcase"]
            if not cases:
                return evidence, f"required report {relative} contains no test cases"
            failures = sum(
                1 for case in cases for child in case.iter() if _local(child.tag) == "failure"
            )
            errors = sum(
                1 for case in cases for child in case.iter() if _local(child.tag) == "error"
            )
            skipped = sum(
                1 for case in cases for child in case.iter() if _local(child.tag) == "skipped"
            )
            passed = failures == 0 and errors == 0 and skipped == 0
            states.append(passed)
            evidence.append(
                self._evidence(
                    context,
                    index * MAX_DECLARED_PATHS + path_index,
                    "junit_xml",
                    {
                        "condition_id": condition_id,
                        "condition_digest": condition_digest,
                        "path": relative.replace("\\", "/"),
                        "sha256": digest,
                        "testcases": len(cases),
                        "failures": failures,
                        "errors": errors,
                        "skipped": skipped,
                        "passed": passed,
                        "action_id": action.identity,
                        "action_digest": action.input_digest,
                        "plan": plan_id,
                        "node": completed.payload.get("node"),
                        "pipeline_session": completed.payload.get("pipeline_session"),
                        "artifact_ref": artifact.identifier,
                        "action_exit_status": outcome.get("exit_status"),
                    },
                    (
                        Reference(target_type="event", identifier=completed.identifier),
                        Reference(target_type="event", identifier=artifact.identifier),
                        Reference(target_type="event", identifier=started.identifier),
                    ),
                )
            )
            if skipped:
                return evidence, f"required report {relative} contains skipped testcases"
        if not any(output_bytes == data for data in report_bytes):
            return evidence, "action output artifact does not match any declared report bytes"
        return evidence, None

    def _bound_action(
        self, context: RuleContext
    ) -> tuple[RepositoryAction | None, tuple[Any, ...], str | None]:
        refs = [ref for ref in context.work_package.inputs if ref.target_type == "action_request"]
        if len(refs) != 1:
            return None, (), "exactly one immutable action request is required"
        request = next(
            (
                event
                for event in context.events
                if event.type == "repository_action.requested"
                and event.payload.get("action_id") == refs[0].identifier
            ),
            None,
        )
        if request is None:
            return None, (), "immutable action request event is absent"
        try:
            action = RepositoryAction.model_validate(request.payload.get("action"))
        except Exception:
            return None, (), "immutable action request is invalid"
        if action.identity != refs[0].identifier or action.input_digest != request.payload.get(
            "input_digest"
        ):
            return None, (), "immutable action request digest does not match"
        related = tuple(
            event
            for event in context.events
            if event.type.startswith("repository_action.")
            and event.payload.get("action_id") == action.identity
        )
        return action, related, None

    def _evidence(
        self,
        context: RuleContext,
        index: int,
        kind: str,
        observed: dict[str, Any],
        sources: tuple[Reference, ...],
    ) -> Evidence:
        scope = context.result.session_ref.identifier
        return Evidence(
            identity=ids.evidence_id(scope, "outcome-" + kind, index),
            source=EvidenceSource.ARTIFACT,
            kind=kind,
            subject_ref=Reference(
                target_type="work_package", identifier=context.work_package.identifier
            ),
            observed=observed,
            derived_from=sources,
            correlation_identifier=context.result.session_ref.identifier,
        )


def _read_confined(root: str, relative: str) -> bytes | None:
    path = _confined_path(root, relative)
    if path is None:
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def _confined_path(root: str, relative: str) -> Path | None:
    if not relative or len(relative) > 1024 or Path(relative).is_absolute():
        return None
    normalized = relative.replace("\\", "/")
    parts = Path(normalized).parts
    if any(part in {".", ".."} for part in parts):
        return None
    try:
        root_path = Path(root).resolve(strict=True)
        candidate = root_path
        for part in parts:
            candidate = candidate / part
            if candidate.is_symlink():
                return None
        resolved = candidate.resolve(strict=True)
        if os.path.commonpath((str(root_path), str(resolved))) != str(root_path):
            return None
        if not resolved.is_file() or resolved.stat().st_size > MAX_EVIDENCE_BYTES:
            return None
        return resolved
    except (OSError, ValueError):
        return None


def _valid_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdefABCDEF" for ch in value)
    )


def _artifact_relative_path(path: str, root: str, action_id: str, digest: str) -> str | None:
    try:
        relative = os.path.relpath(path, root)
    except ValueError:
        return None
    parts = Path(relative).parts
    if len(parts) != 2 or parts[0] != action_id or parts[1] != f"output-{digest}.txt":
        return None
    return relative


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
