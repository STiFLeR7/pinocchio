"""Nexus v2 terminal front door — the first real entrypoint for ``nexus_human_interaction``.

Every other v2 entrypoint (``python -m nexus_scheduler``) drives goals a caller registers
programmatically; nothing lets an actual person type a request and get an answer. This script is
that missing front door. It wires the existing, previously-unwired
:func:`nexus_human_interaction.build_human_interaction` façade to a terminal chat loop, using a
real LLM runtime adapter (:mod:`nexus_runtime_llm`) chosen entirely by configuration
(``NEXUS_LLM_PROVIDER``). It introduces no orchestration bypass: ``--once`` drives the existing
Goal -> Planning -> Execution -> Operations -> Response flow, while ``--plan`` stops after Planning
for inspection and ``--resume`` continues that durable request in a separate process.

Usage::

    uv run python scripts/nexus_cli.py                       # interactive, in-memory (no --db)
    uv run python scripts/nexus_cli.py --db nexus_personal.db # durable, replay/restart-capable
    uv run python scripts/nexus_cli.py --once "summarize this file"   # one request; gated work prompts
    uv run python scripts/nexus_cli.py --db nexus.db --plan "Add a CLI version option" --repository-root .
    uv run python scripts/nexus_cli.py --db nexus.db --resume cli-<session-id>

Provider selection is pure configuration (see ``nexus_runtime_llm.config``):

    NEXUS_LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=... uv run python scripts/nexus_cli.py

With no ``NEXUS_LLM_PROVIDER`` set, the deterministic, network-free stub answers instead — the
same fail-closed default every other runtime adapter in this platform already uses.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from typing import cast

from nexus_context import ContextCategory, ContextSource, RawContextFragment
from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import CapabilityCategory, KnowledgeType
from nexus_core.domain import Capability
from nexus_execution.actions import RepositoryAction
from nexus_human_interaction import HumanInteractionContext, build_human_interaction
from nexus_human_interaction.facade import HumanInteraction
from nexus_human_interaction.model import InteractionResponse, OperatorRequest
from nexus_infra import InfrastructureContext, build_durable_infrastructure, build_infrastructure
from nexus_operations import OperationsContext, build_operations
from nexus_planning import WorkItemSpec
from nexus_runtime.events import SystemTimestampSource
from nexus_runtime_llm import LLMRuntimeAdapter, build_llm_invoker, load_llm_provider_config
from nexus_workflows.spine import SpineControl, SpineStage

CAPABILITY_ID = "text_generation"
ARTIFACTS_DIR = ".nexus_llm_artifacts"

# A deterministic, CLI-level heuristic for whether a request looks write-capable — NOT a new
# Policy Engine policy (out of P0 scope). It only decides how this script fills in the one
# existing WorkItemSpec.requires_approval flag, exactly the mechanism
# examples/07-approval-exchange already exercises via its ``gated=`` parameter.
_WRITE_KEYWORDS = ("commit", "push", "delete", "remove", "write", "modify", "merge", "rm ")


def looks_write_capable(request_text: str) -> bool:
    lowered = request_text.lower()
    return any(keyword in lowered for keyword in _WRITE_KEYWORDS)


def _capability() -> Capability:
    return Capability(
        identifier=CAPABILITY_ID,
        name="Text Generation",
        version="1",
        category=CapabilityCategory.DEVELOPMENT,
        description="answer a user request via a real LLM runtime",
        inputs=(),
        outputs=(),
    )


def build_operator_request(
    request_text: str,
    *,
    identity: str,
    repository_root: str | None = None,
    include_work_item: bool = True,
    repository_actions: tuple[RepositoryAction, ...] = (),
) -> OperatorRequest:
    """Build the deterministic operator request for execution or plan-first inspection.

    Normal execution supplies one fixed work item. Plan-first mode leaves decomposition to Intent's
    recorded explicit steps and provides the work-item template separately for execution metadata.
    Neither path asks an LLM to decompose work.
    """
    work_item = WorkItemSpec(
        key="respond",
        objective=request_text,
        capability_requirements=(CAPABILITY_ID,),
        skill_refs=(Reference(target_type="skill", identifier="skill-respond"),),
        requires_approval=looks_write_capable(request_text),
    )
    return OperatorRequest(
        identity=identity,
        request_text=request_text,
        work_items=(work_item,) if include_work_item else (),
        knowledge_subject=request_text[:80] or "operator request",
        scope=f"cli-{identity}",
        knowledge_kind=KnowledgeType.LESSON,
        context_fragments=(
            RawContextFragment(
                source=ContextSource.WORKSPACE, category=ContextCategory.WORKSPACE, key="repository"
            ),
        ),
        capabilities=(_capability(),),
        correlation_identifier=f"cor-{identity}",
        repository_root=repository_root,
        planning_step_template=work_item if not include_work_item else None,
        repository_actions=repository_actions,
    )


def response_text(ops: OperationsContext, request: OperatorRequest) -> str:
    """Read back the LLM's actual answer from the durable log (Operations, read-only).

    ``InteractionResponse`` reports pipeline *status*, never runtime content (INV-27: served by
    reference) — the ``runtime.output`` fact itself only records a chunk's length, never its text.
    The adapter (``nexus_runtime_llm``) writes the complete answer to one artifact file and
    references it via ``runtime.artifact_emitted``; this reads that reference back, the same
    by-reference discipline Validation itself relies on for evidence, never a second engine.
    """
    events = ops.service.event_lookup(producer="runtime", event_type="runtime.artifact_emitted")
    for event in events:
        if event.correlation_identifier != request.correlation:
            continue
        identifier = str(event.payload.get("artifact", ""))
        if not identifier.endswith("response.md"):
            continue
        artifact_dir = os.path.realpath(ARTIFACTS_DIR)
        path = os.path.realpath(os.path.join(artifact_dir, identifier))
        if (
            os.path.dirname(path) == artifact_dir
            and os.path.basename(path) == identifier
            and os.path.isfile(path)
        ):
            with open(path, encoding="utf-8") as handle:
                return handle.read().strip()
    return ""


def _print_response(
    ops: OperationsContext, request: OperatorRequest, response: InteractionResponse
) -> None:
    print(f"  status: {response.status}")
    print(f"  runtime completed: {'yes' if response.runtime_completed else 'no'}")
    accepted = response.outcome_accepted
    acceptance = "unknown" if accepted is None else ("accepted" if accepted else "not accepted")
    if response.validation_decisions:
        print(f"  validation verdicts: {', '.join(response.validation_decisions)}")
    print(f"  outcome acceptance: {acceptance}")
    if response.awaiting_approval:
        for pending in response.pending_approvals:
            print(f"  [gate] node={pending.node!r} requires approval before it can run.")
        return
    text = response_text(ops, request)
    if text:
        print(f"  nexus: {text}")
    print(f"  executed stages: {', '.join(response.executed_stages)}")


def _handle_approvals(
    hi: HumanInteraction,
    ops: OperationsContext,
    request: OperatorRequest,
    response: InteractionResponse,
) -> None:
    """Interactively resolve every pending gate — the exact Requested/Pending/Approved lifecycle
    examples/07-approval-exchange demonstrates non-interactively, driven here from stdin."""
    while True:
        pending_approvals = hi.pending_approvals(request.identity)
        if not pending_approvals:
            break
        pending = pending_approvals[0]
        try:
            answer = input(f"  approve node {pending.node!r}? [y/N] ").strip().lower()
        except EOFError:
            print(
                "  approval left pending; use --pending to find it and --resume <session> to continue."
            )
            return
        if answer == "y":
            decision = hi.approve(request, pending.node, decided_by="operator")
            print(f"  [approval] approved -> pipeline status: {decision.pipeline_status}")
        else:
            decision = hi.deny(
                request, pending.node, decided_by="operator", reason="declined at terminal"
            )
            print(f"  [approval] denied -> node {pending.node!r} will never execute.")
            return
    text = response_text(ops, request)
    if text:
        print(f"  nexus: {text}")


def _build_infrastructure(db_path: str | None) -> InfrastructureContext:
    if db_path:
        return cast(InfrastructureContext, build_durable_infrastructure(db_path))
    return build_infrastructure()


def _saved_request_text(infra: InfrastructureContext, identity: str) -> str:
    session = f"hi-{identity}"
    for event in infra.event_store.read_all():
        if (
            event.type == "interaction.request_submitted"
            and event.payload.get("session") == session
        ):
            return str(event.payload.get("request_text", ""))
    raise ValueError(f"no saved request for session {identity!r}")


def _saved_repository_root(infra: InfrastructureContext, identity: str) -> str | None:
    session = f"hi-{identity}"
    for event in infra.event_store.read_all():
        if (
            event.type == "interaction.request_submitted"
            and event.payload.get("session") == session
        ):
            value = event.payload.get("repository_root")
            return str(value) if value is not None else None
    raise ValueError(f"no saved request for session {identity!r}")


def _saved_action_ids(infra: InfrastructureContext, identity: str) -> tuple[str, ...]:
    session = f"hi-{identity}"
    for event in infra.event_store.read_all():
        if (
            event.type == "interaction.request_submitted"
            and event.payload.get("session") == session
        ):
            return tuple(str(value) for value in event.payload.get("action_ids", ()))
    return ()


def _command_allowlist(path: str | None) -> dict[str, tuple[str, ...]]:
    if path is None:
        return {}
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or any(
        not isinstance(key, str)
        or not isinstance(argv, list)
        or not argv
        or any(not isinstance(part, str) or not part for part in argv)
        for key, argv in payload.items()
    ):
        raise ValueError("command allow-list must map command IDs to non-empty argv arrays")
    return {key: tuple(argv) for key, argv in payload.items()}


def _action_from_args(args: argparse.Namespace, identity: str) -> tuple[RepositoryAction, ...]:
    if args.action is None:
        return ()
    if not args.repository_root:
        raise ValueError("--action requires --repository-root")
    common = {
        "workspace_root": args.repository_root,
        "actor": args.actor,
        "request_identity": identity,
        "correlation": f"cor-{identity}",
    }
    if args.action == "read_file":
        if not args.action_path:
            raise ValueError("read_file requires --action-path")
        action = RepositoryAction.read(path=args.action_path, **common)
    elif args.action == "write_file":
        if not args.action_path or args.action_content is None:
            raise ValueError("write_file requires --action-path and --action-content")
        action = RepositoryAction.write(
            path=args.action_path, content=args.action_content, **common
        )
    else:
        if not args.command_id:
            raise ValueError("run_test requires --command-id")
        action = RepositoryAction.run_test(command_id=args.command_id, **common)
    return (action,)


def _print_plan(response: InteractionResponse) -> None:
    print(f"  status: {response.status}")
    if response.intent_analysis:
        intent = response.intent_analysis
        goal = cast(dict[str, object], intent.get("goal") or {})
        intent_record = cast(dict[str, object], intent.get("intent") or {})
        print(f"  intended outcome: {goal.get('outcome') or intent_record.get('raw_request', '')}")
        uncertainty = (
            intent_record.get("ambiguity")
            or intent_record.get("missing_information")
            or "none recorded"
        )
        print(f"  uncertainty: {uncertainty}")
    if response.execution_plan:
        plan = response.execution_plan
        for node in plan.execution_graph.nodes:
            package = next(
                item
                for item in plan.work_packages
                if item.identifier == node.work_package_ref.identifier
            )
            print(f"  work item {node.identifier}: {package.objective}")
        for source, target in plan.coordination.dependency_edges:
            print(f"  dependency: {source} -> {target}")
        print(
            f"  source refs: {[(ref.target_type, ref.identifier) for ref in plan.context_references]}"
        )
        print(f"  assumptions: {plan.plan.assumptions}")
        print("  plan paused before actuation; run --resume with this session ID to execute.")
    elif response.clarification_requests:
        print("  clarification required before a plan can be resumed.")


def _print_pending(context: HumanInteractionContext, infra: InfrastructureContext) -> None:
    sessions = {
        str(event.payload.get("session", ""))
        for event in infra.event_store.read_all()
        if event.type == "approval.pending"
    }
    for session in sorted(sessions):
        pending = context.approval.pending(session)
        if pending:
            identity = session.removeprefix("pipe-")
            print(f"{identity}: " + ", ".join(item.node for item in pending))


def run_one(
    hi: HumanInteraction,
    ops: OperationsContext,
    request_text: str,
    *,
    repository_root: str | None = None,
    repository_actions: tuple[RepositoryAction, ...] = (),
    identity: str | None = None,
) -> None:
    identity = identity or f"cli-{uuid.uuid4().hex[:12]}"
    print(f"  session: {identity}")
    request = build_operator_request(
        request_text,
        identity=identity,
        repository_root=repository_root,
        repository_actions=repository_actions,
    )
    response = hi.submit(request)
    for event in hi.history(identity):
        if event.type == "interaction.request_submitted":
            for action_id in event.payload.get("action_ids", ()):
                print(f"  action: {action_id}")
    _print_response(ops, request, response)
    if response.awaiting_approval:
        _handle_approvals(hi, ops, request, response)
    for clarification in response.clarification_requests:
        print(f"  nexus needs clarification: {clarification.question}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="nexus-cli", description="Nexus v2 terminal front door (nexus_human_interaction)"
    )
    parser.add_argument(
        "--db", default=None, help="durable SQLite path (omit for in-memory, non-persistent)"
    )
    parser.add_argument(
        "--once", default=None, help="submit one request and exit (prompts if approval is required)"
    )
    parser.add_argument(
        "--pending", action="store_true", help="list durable approvals awaiting a decision"
    )
    parser.add_argument(
        "--resume", default=None, help="resume a durable request by its printed session ID"
    )
    parser.add_argument(
        "--plan", default=None, help="create and display a plan for this request, then stop"
    )
    parser.add_argument(
        "--repository-root", default=None, help="explicit workspace root to profile for --plan"
    )
    parser.add_argument("--action", choices=("read_file", "write_file", "run_test"))
    parser.add_argument("--action-path", default=None)
    parser.add_argument("--action-content", default=None)
    parser.add_argument("--command-id", default=None, help="named command in configured allow-list")
    parser.add_argument("--actor", default="operator")
    args = parser.parse_args(argv)
    if args.action is not None and args.once is None and args.plan is None:
        parser.error("--action requires --once or --plan")
    if args.command_id is not None and args.action != "run_test":
        parser.error("--command-id is valid only with --action run_test")
    if args.action_path is not None and args.action not in {"read_file", "write_file"}:
        parser.error("--action-path is valid only with read_file or write_file")
    if args.action_content is not None and args.action != "write_file":
        parser.error("--action-content is valid only with write_file")

    infra = _build_infrastructure(args.db)
    config = load_llm_provider_config()
    print(f"[nexus-cli] llm provider: {config.provider} (model={config.model})")
    if args.db:
        print(f"[nexus-cli] durable log: {args.db}")

    def adapter_factory(_request: object) -> LLMRuntimeAdapter:
        return LLMRuntimeAdapter(invoker=build_llm_invoker(config), working_dir=ARTIFACTS_DIR)

    context = build_human_interaction(
        infra,
        timestamps=SystemTimestampSource(),
        adapter_factory=adapter_factory,
        action_command_allowlist=_command_allowlist(os.environ.get("NEXUS_ACTION_COMMANDS_FILE")),
        action_artifact_directory=(
            os.path.abspath(f"{args.db}.action_artifacts") if args.db is not None else None
        ),
    )
    ops = build_operations(context.spine.coordinator, context.approval, infra)

    if args.pending:
        _print_pending(context, infra)
        return
    if args.resume:
        repository_root = _saved_repository_root(infra, args.resume)
        request = build_operator_request(
            _saved_request_text(infra, args.resume),
            identity=args.resume,
            repository_root=repository_root,
            include_work_item=repository_root is None,
        )
        response = context.facade.restart(request)
        for action_id in _saved_action_ids(infra, args.resume):
            print(f"  action: {action_id}")
        _print_response(ops, request, response)
        if response.awaiting_approval:
            _handle_approvals(context.facade, ops, request, response)
        return

    if args.once is not None:
        identity = f"cli-{uuid.uuid4().hex[:12]}"
        actions = _action_from_args(args, identity) if args.action else ()
        run_one(
            context.facade,
            ops,
            args.once,
            repository_root=args.repository_root,
            repository_actions=actions,
            identity=identity,
        )
        return

    if args.plan is not None:
        if not args.db:
            parser.error(
                "--plan requires --db so the operator can inspect, then resume the same plan"
            )
        if not args.repository_root:
            parser.error("--plan requires --repository-root for explicit repository scope")
        identity = f"cli-{uuid.uuid4().hex[:12]}"
        print(f"  session: {identity}")
        request = build_operator_request(
            args.plan,
            identity=identity,
            repository_root=args.repository_root,
            include_work_item=False,
            repository_actions=_action_from_args(args, identity),
        )
        response = context.facade.submit(
            request, control=SpineControl(stop_after_stage=SpineStage.PLANNING)
        )
        for action_id in _saved_action_ids(infra, identity):
            print(f"  action: {action_id}")
        _print_plan(response)
        for clarification in response.clarification_requests:
            print(f"  nexus needs clarification: {clarification.question}")
        return

    print("[nexus-cli] interactive mode — type a request, or 'exit' to quit.")
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            break
        if not line or line.lower() in ("exit", "quit"):
            break
        run_one(context.facade, ops, line)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    main()
