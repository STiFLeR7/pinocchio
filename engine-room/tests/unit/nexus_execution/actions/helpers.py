from __future__ import annotations

from dataclasses import dataclass
from sys import executable

from nexus_approval.events import APPROVAL_APPROVED
from nexus_approval.events import build_event as build_approval_event
from nexus_core.contracts.enums import PolicyCategory, PolicyDecision
from nexus_core.contracts.status import PolicyStatus
from nexus_core.domain.policy import Policy
from nexus_execution.actions.boundary import (
    ActionAuthorization,
    RepositoryAction,
    record_action_request,
)
from nexus_infra import InfrastructureContext, build_infrastructure
from nexus_planning import FixedTimestampSource, WorkItemSpec
from nexus_planning.grounded import PlanningInputs, build_grounded_planning
from tests.unit.nexus_engineering.fixtures import make_goal, strategy_for


@dataclass(frozen=True)
class AuthorizedFixture:
    infra: InfrastructureContext
    action: RepositoryAction
    authorization: ActionAuthorization
    command_allowlist: dict[str, tuple[str, ...]]


def authorized_fixture(
    workspace: str,
    *,
    kind: str = "write_file",
    path: str = "README.md",
    command_id: str = "fixture-test",
) -> AuthorizedFixture:
    request_identity = "action-test-request"
    infra = build_infrastructure()
    command_allowlist: dict[str, tuple[str, ...]] = {"fixture-test": (executable, "-V")}
    if kind == "write_file":
        action = RepositoryAction.write(
            workspace_root=workspace,
            path=path,
            content="after\n",
            actor="operator",
            request_identity=request_identity,
            correlation=f"cor-{request_identity}",
        )
    elif kind == "read_file":
        action = RepositoryAction.read(
            workspace_root=workspace,
            path=path,
            actor="operator",
            request_identity=request_identity,
            correlation=f"cor-{request_identity}",
        )
    else:
        action = RepositoryAction.run_test(
            workspace_root=workspace,
            command_id=command_id,
            actor="operator",
            request_identity=request_identity,
            correlation=f"cor-{request_identity}",
            resolved_argv=command_allowlist.get(command_id, ()),
        )
    action_ref = record_action_request(infra, action, timestamps=FixedTimestampSource())
    goal = make_goal(identity=f"goal-{request_identity}")
    plan = build_grounded_planning(infra, timestamps=FixedTimestampSource()).planner.plan(
        PlanningInputs(
            goal=goal,
            engineering_strategy=strategy_for(goal, persist=False),  # type: ignore[no-untyped-call]
            work_items=(
                WorkItemSpec(
                    key="action",
                    objective="perform explicit repository action",
                    inputs=(action_ref,),
                    requires_approval=kind == "write_file",
                ),
            ),
        )
    )

    policy = Policy(
        identity="policy.test.repository-action.allow",
        version="1",
        purpose="test allow for the constrained action path",
        conditions={"attr": "action_class", "op": "eq", "value": "repository_action"},
        decision=PolicyDecision.ALLOW,
        priority=0,
        owner="test",
        status=PolicyStatus.ENABLED,
        category=PolicyCategory.GOVERNANCE,
        governed_action_class="repository_action",
    )
    from nexus_policy.composition import build_policy
    from nexus_policy.model import DecisionRequest

    policy_context = build_policy(infra, seed=False, now=FixedTimestampSource().now)
    policy_context.registry.register(policy)
    node = next(
        node
        for node in plan.execution_graph.nodes
        if node.work_package_ref.identifier
        in {package.identifier for package in plan.work_packages if action_ref in package.inputs}
    )
    session = f"pipe-{request_identity}"
    policy_context.engine.evaluate(
        DecisionRequest(
            action_class="repository_action",
            correlation_identifier=action.correlation_identifier,
            attributes={
                "action_id": action.identity,
                "input_digest": action.input_digest,
                "workspace_root": action.workspace_root,
                "plan_identity": plan.identity,
                "pipeline_session": session,
                "node": node.identifier,
                "actor": action.actor,
                "request_identity": action.request_identity,
                "work_item_key": action.work_item_key,
            },
        )
    )
    policy_event = next(
        event
        for event in reversed(tuple(infra.event_store.read_all()))
        if event.type == "policy.evaluated"
    )
    approval = build_approval_event(
        f"evt-{session}-{node.identifier}-approved-test",
        APPROVAL_APPROVED,
        action.correlation_identifier,
        {
            "session": session,
            "node": node.identifier,
            "decided_by": "operator",
            "reason": "approved",
        },
        "1970-01-01T00:00:00+00:00",
    )
    infra.emit(approval)
    return AuthorizedFixture(
        infra=infra,
        action=action,
        authorization=ActionAuthorization(
            policy_event_id=policy_event.identifier,
            plan_identity=plan.identity,
            pipeline_session=session,
            node=node.identifier,
            approval_event_id=approval.identifier if kind == "write_file" else None,
        ),
        command_allowlist=command_allowlist,
    )
