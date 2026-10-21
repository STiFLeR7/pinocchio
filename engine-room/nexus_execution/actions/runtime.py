"""RuntimeAdapter bridge for explicit first-party repository action references."""

from __future__ import annotations

from collections.abc import Iterator, Mapping

from nexus_core.contracts.base import Reference
from nexus_core.domain.work_package import WorkPackage
from nexus_core.registries.interfaces import HarnessDescriptor
from nexus_execution.actions.boundary import (
    ACTION_CLASS,
    ActionAuthorization,
    ActionDeniedError,
    RepositoryActionBoundary,
    resolve_action_request,
)
from nexus_execution.adapter import (
    AdapterConfig,
    ConfiguredRuntime,
    ExecutionControl,
    RuntimeAdapter,
    TeardownReport,
)
from nexus_execution.signals import (
    ArtifactSignal,
    OutputSignal,
    RuntimeSignal,
    StreamChannel,
    TerminalOutcome,
    TerminalSignal,
)
from nexus_infra import InfrastructureContext


class RepositoryActionRuntimeAdapter:
    """Route planned action references through the constrained boundary; delegate other packages."""

    def __init__(
        self,
        fallback: RuntimeAdapter,
        infrastructure: InfrastructureContext,
        boundary: RepositoryActionBoundary,
        *,
        action_only: bool = False,
    ) -> None:
        self._fallback = fallback
        self._infra = infrastructure
        self._boundary = boundary
        self._action_only = action_only

    def descriptor(self) -> HarnessDescriptor:
        descriptor = self._fallback.descriptor()
        capabilities = (
            (Reference(target_type="capability", identifier="repository_action"),)
            if self._action_only
            else tuple(
                {
                    reference.identifier: reference
                    for reference in (
                        *descriptor.advertised_capabilities,
                        Reference(target_type="capability", identifier="repository_action"),
                    )
                }.values()
            )
        )
        return descriptor.model_copy(
            update={
                "identity": "nexus-repository-action"
                if self._action_only
                else f"nexus-first-party-action+{descriptor.identity}",
                "advertised_capabilities": capabilities,
                "metadata": {
                    **(descriptor.metadata or {}),
                    "first_party_action_boundary": True,
                    "action_only": self._action_only,
                },
            }
        )

    def configure(self, config: AdapterConfig) -> ConfiguredRuntime:
        return self._fallback.configure(config)

    def execute(
        self,
        *,
        session_ref: Reference,
        work_package: WorkPackage,
        control: ExecutionControl,
    ) -> Iterator[RuntimeSignal]:
        refs = tuple(ref for ref in work_package.inputs if ref.target_type == "action_request")
        if not refs:
            yield from self._fallback.execute(
                session_ref=session_ref, work_package=work_package, control=control
            )
            return
        if len(refs) != 1:
            yield TerminalSignal(
                TerminalOutcome.FAILED,
                detail="one first-party repository action per work package is supported",
                error_class="PolicyViolation",
            )
            return
        action = resolve_action_request(self._infra, refs[0])
        try:
            authorization = self._authorization(action, refs[0].identifier, work_package)
            outcome = self._boundary.execute(action, authorization=authorization, control=control)
        except ActionDeniedError as exc:
            yield TerminalSignal(
                TerminalOutcome.FAILED, detail=str(exc), error_class="ActionDeniedError"
            )
            return
        if outcome.output_ref:
            yield ArtifactSignal(
                Reference(target_type="repository_action_event", identifier=outcome.output_ref),
                "action_output",
            )
        if outcome.diff_ref:
            yield ArtifactSignal(
                Reference(target_type="repository_action_event", identifier=outcome.diff_ref),
                "unified_diff",
            )
        yield OutputSignal(StreamChannel.STRUCTURED, f"action_id={outcome.action_id}")
        yield TerminalSignal(
            TerminalOutcome.COMPLETED if outcome.status == "completed" else TerminalOutcome.FAILED,
            exit_status=outcome.exit_status,
        )

    def cleanup(self) -> TeardownReport:
        return self._fallback.cleanup()

    def _authorization(
        self, action: object, action_id: str, work_package: WorkPackage
    ) -> ActionAuthorization:
        events = tuple(self._infra.event_store.read_all())
        plans = []
        for event in events:
            if event.type != "planning.execution_plan_assembled" or event.producer != "planning":
                continue
            raw = event.payload.get("execution_plan")
            if not isinstance(raw, Mapping):
                continue
            plan = raw.get("plan")
            if not isinstance(plan, Mapping):
                continue
            packages = raw.get("work_packages", ())
            if any(
                isinstance(package, Mapping)
                and package.get("identifier") == work_package.identifier
                and any(
                    isinstance(ref, Mapping)
                    and ref.get("target_type") == "action_request"
                    and ref.get("identifier") == action_id
                    for ref in package.get("inputs", ())
                )
                for package in packages
            ):
                plans.append((event, raw))
        if len(plans) != 1:
            raise ActionDeniedError("action reference does not map to one frozen plan")
        _plan_event, raw_plan = plans[0]
        plan_value = raw_plan.get("plan")
        plan_identity = str(plan_value.get("identity")) if isinstance(plan_value, Mapping) else ""
        goal = raw_plan.get("goal_ref")
        goal_identity = str(goal.get("identifier")) if isinstance(goal, Mapping) else ""
        node_id = next(
            (
                str(node.get("identifier"))
                for node in raw_plan.get("execution_graph", {}).get("nodes", ())
                if isinstance(node, Mapping)
                and isinstance(node.get("work_package_ref"), Mapping)
                and node["work_package_ref"].get("identifier") == work_package.identifier
            ),
            "",
        )
        from nexus_execution.actions.boundary import RepositoryAction

        if not isinstance(action, RepositoryAction):
            raise ActionDeniedError("invalid durable action request")
        pipeline_session = f"pipe-{action.request_identity}"
        policy = next(
            (
                event
                for event in events
                if event.type == "policy.evaluated"
                and event.producer == "policy"
                and event.payload.get("decision") == "allow"
                and isinstance(event.payload.get("attributes"), Mapping)
                and all(
                    event.payload["attributes"].get(key) == value
                    for key, value in {
                        "action_id": action.identity,
                        "input_digest": action.input_digest,
                        "workspace_root": action.workspace_root,
                        "plan_identity": plan_identity,
                        "pipeline_session": pipeline_session,
                        "node": node_id,
                        "actor": action.actor,
                        "request_identity": action.request_identity,
                        "work_item_key": action.work_item_key,
                    }.items()
                )
                and event.payload.get("action_class") == ACTION_CLASS
            ),
            None,
        )
        if policy is None or goal_identity != f"goal-{action.request_identity}" or not node_id:
            raise ActionDeniedError("matching Policy ALLOW and frozen plan lineage are required")
        approval = next(
            (
                event
                for event in events
                if action.kind == "write_file"
                and event.type == "approval.approved"
                and event.producer == "approval_exchange"
                and event.payload.get("session") == pipeline_session
                and event.payload.get("node") == node_id
            ),
            None,
        )
        return ActionAuthorization(
            policy_event_id=policy.identifier,
            plan_identity=plan_identity,
            pipeline_session=pipeline_session,
            node=node_id,
            approval_event_id=approval.identifier if approval else None,
        )
