"""The Human Interaction façade (P14/B) — the first constitutional operator surface.

:class:`HumanInteraction` is a *façade*, not a UI framework: it exposes the constitutional platform and
never bypasses it. Every operation invokes **only** the :class:`~nexus_workflows.spine.ConstitutionalPipeline`
(``submit`` / ``restart`` drive it; ``status`` / ``history`` / ``execution_graph`` / ``knowledge`` /
``replay`` / ``explain_lineage`` project it) — no engine is ever called directly, and the façade owns no
reasoning. It owns exactly four things: request translation (``OperatorRequest`` → ``SpineRequest``),
response formatting, session lookup, and progress reporting, recording its own durable ``interaction.*``
facts so an operator session replays exactly and a restart resumes without replaying completed stages.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import Any

from nexus_approval import (
    ApprovalDecision,
    ApprovalExchange,
    ApprovalExplanation,
    ApprovalRequest,
)
from nexus_core.contracts.base import Reference, Struct
from nexus_core.contracts.enums import KnowledgeType
from nexus_core.domain.context_package import ContextPackage
from nexus_core.domain.event import Event
from nexus_human_interaction import events as ievents
from nexus_human_interaction.model import (
    ExecutionGraphView,
    InteractionResponse,
    InteractionSession,
    InteractionStatus,
    KnowledgeView,
    LineageView,
    OperatorRequest,
)
from nexus_human_interaction.observability import OperatorObservability
from nexus_human_interaction.session import reconstruct_interaction_session
from nexus_infra import DuplicateEventError, InfrastructureContext, content_hash
from nexus_workflows.spine import (
    ConstitutionalPipeline,
    SpineControl,
    SpineRequest,
    SpineRun,
    find_execution_state,
    find_goal,
    find_plan,
)
from nexus_workflows.spine.learning import KnowledgeSelection


class HumanInteraction:
    """The operator façade over the constitutional pipeline (invokes only the pipeline)."""

    def __init__(
        self,
        pipeline: ConstitutionalPipeline,
        infrastructure: InfrastructureContext,
        approval: ApprovalExchange,
        *,
        now: Callable[[], str] | None = None,
        observability: OperatorObservability | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._infra = infrastructure
        # The Approval Exchange (P15) is the sole owner of approval coordination — the façade never
        # bypasses it; its approval methods delegate here and it owns no approval logic (presentation only).
        self._approval = approval
        self._now = now or ievents.system_now
        self._obs = observability or OperatorObservability(infrastructure.observability)

    # -- drive the pipeline -------------------------------------------------- #

    def submit(
        self, request: OperatorRequest, *, control: SpineControl | None = None
    ) -> InteractionResponse:
        """Translate the operator request, drive the whole pipeline, record + format the response."""
        if request.repository_actions:
            work_items, capabilities, actions = self._pipeline.prepare_repository_actions(
                identity=request.identity,
                repository_root=request.repository_root,
                correlation=request.correlation,
                work_items=request.work_items,
                capabilities=request.capabilities,
                repository_actions=request.repository_actions,
            )
            request = replace(
                request,
                work_items=work_items,
                repository_actions=actions,
                capabilities=capabilities,
            )
        spine = _translate(request)
        self._emit(
            request,
            ievents.INTERACTION_SESSION_STARTED,
            {"pipeline_session": spine.pipeline_session_id, "request": request.identity},
        )
        self._emit(
            request,
            ievents.INTERACTION_REQUEST_SUBMITTED,
            {
                "request_text": request.request_text,
                "subject": request.knowledge_subject,
                "scope": request.scope,
                "work_items": [item.key for item in request.work_items],
                "repository_root": request.repository_root,
                "action_ids": [action.identity for action in request.repository_actions],
            },
        )
        run = self._pipeline.run(spine, control=control)
        self._obs.submitted()
        return self._record(request, run, resumed=False)

    def restart(self, request: OperatorRequest) -> InteractionResponse:
        """Resume a paused/interrupted operator session — the pipeline reconstructs completed stages."""
        request = self._restore_action_inputs(request)
        completed = self._completed_response(request)
        if completed is not None:
            return completed
        spine = _translate(request)
        run = self._pipeline.run(spine)  # the coordinator seeds from the log and resumes (INV-18)
        self._obs.resumed()
        self._emit(
            request,
            ievents.INTERACTION_RESUMED,
            {"reconstructed": list(run.reconstructed_stages)},
        )
        return self._record(request, run, resumed=True)

    def _restore_action_inputs(self, request: OperatorRequest) -> OperatorRequest:
        submitted = next(
            (
                event
                for event in self._pipeline.history()
                if event.type == ievents.INTERACTION_REQUEST_SUBMITTED
                and event.payload.get("session") == request.interaction_session_id
            ),
            None,
        )
        if submitted is None:
            return request
        ids = list(submitted.payload.get("action_ids", ()))
        if not ids:
            if request.repository_actions:
                raise ValueError(
                    "restart action inputs differ from the immutable submitted request"
                )
            return request
        if submitted.payload.get("request_text") != request.request_text:
            raise ValueError("restart request text differs from the immutable submitted request")
        if submitted.payload.get("repository_root") != request.repository_root:
            raise ValueError("restart workspace differs from the immutable submitted request")
        if submitted.correlation_identifier != request.correlation:
            raise ValueError("restart correlation differs from the immutable submitted request")
        if request.repository_actions:
            if [action.identity for action in request.repository_actions] != ids:
                raise ValueError(
                    "restart action inputs differ from the immutable submitted request"
                )
            return request
        actions = self._pipeline.restore_repository_actions(
            tuple(str(action_id) for action_id in ids)
        )
        return replace(request, repository_actions=actions)

    def _completed_response(self, request: OperatorRequest) -> InteractionResponse | None:
        """Return an already recorded terminal response without re-running completed owners."""
        events = self._pipeline.history()
        recorded = next(
            (
                event
                for event in reversed(events)
                if event.type == ievents.INTERACTION_RESPONSE_RECORDED
                and event.payload.get("session") == request.interaction_session_id
                and event.payload.get("status") == "completed"
            ),
            None,
        )
        if recorded is None:
            return None

        submitted = next(
            (
                event
                for event in events
                if event.type == ievents.INTERACTION_REQUEST_SUBMITTED
                and event.payload.get("session") == request.interaction_session_id
            ),
            None,
        )
        if submitted is not None and submitted.payload.get("request_text") != request.request_text:
            raise ValueError(
                f"request identity {request.identity!r} was already used for different text"
            )
        if (
            submitted is not None
            and submitted.payload.get("repository_root") != request.repository_root
        ):
            raise ValueError(
                f"request identity {request.identity!r} was already used with a different repository root"
            )
        stored_action_ids = list(submitted.payload.get("action_ids", ())) if submitted else []
        if stored_action_ids != [action.identity for action in request.repository_actions]:
            raise ValueError(
                "request identity was already used with different repository action inputs"
            )
        if recorded.correlation_identifier != request.correlation:
            raise ValueError(
                f"request identity {request.identity!r} was already used with a different correlation"
            )

        payload = recorded.payload
        own_events = _request_events(events, request)
        goal = find_goal(own_events)
        plan = find_plan(own_events)
        execution = find_execution_state(own_events)
        grounding_event = next(
            (
                event
                for event in own_events
                if event.type == "pipeline.knowledge_grounded"
                and event.payload.get("session") == f"pipe-{request.identity}"
            ),
            None,
        )
        grounding = (
            KnowledgeSelection.model_validate(
                {
                    key: value
                    for key, value in grounding_event.payload.items()
                    if key not in {"session", "count", "item_snapshots"}
                }
                | {
                    "items": grounding_event.payload.get("item_snapshots", []),
                }
            )
            if grounding_event is not None
            else None
        )
        return InteractionResponse(
            session_id=request.interaction_session_id,
            status="completed",
            pipeline_session=self._pipeline.session(f"pipe-{request.identity}"),
            goal_ref=Reference(target_type="goal", identifier=goal.identity) if goal else None,
            plan_ref=Reference(target_type="plan", identifier=plan.plan.identity) if plan else None,
            execution_status=execution.status.value if execution is not None else None,
            validation_decisions=tuple(
                str(event.payload["decision"])
                for event in events
                if event.producer == "validation"
                and event.type in ("validation.completed", "validation.failed")
                and event.correlation_identifier == request.correlation
            ),
            knowledge_item_ids=tuple(str(x) for x in payload.get("knowledge_item_ids", ())),
            knowledge_grounding=grounding,
            reconstructed_stages=tuple(str(x) for x in payload.get("reconstructed", ())),
            executed_stages=tuple(str(x) for x in payload.get("executed", ())),
            progress=self._pipeline.session(f"pipe-{request.identity}").stages_completed,
            pending_approvals=self._approval.pending(f"pipe-{request.identity}"),
            clarification_requests=(),
            execution_plan=plan,
            grounding_selection=_grounding_selection(own_events),
            intent_analysis=_event_payload(own_events, "intent.resolved", "analysis"),
            context_package=_event_model(
                own_events, "context.grounding.assembled", "package", ContextPackage
            ),
            repository_profile=_event_payload(own_events, "repository.profiled", "profile"),
        )

    # -- approval surface (delegates to the Approval Exchange, never bypassed) - #

    def pending_approvals(self, identity: str) -> tuple[ApprovalRequest, ...]:
        """The gates of this session still awaiting an operator decision (from the Approval Exchange)."""
        return self._approval.pending(_pipeline_session_id(identity))

    def approve(
        self, request: OperatorRequest, node: str, *, decided_by: str = "operator", reason: str = ""
    ) -> ApprovalDecision:
        """Authorize a gate — the Approval Exchange records it and resumes the paused pipeline."""
        decision, run = self._approval.approve_with_run(
            _translate(request), node, decided_by=decided_by, reason=reason
        )
        self._record(request, run, resumed=True)
        self._obs.resumed()
        return decision

    def deny(
        self, request: OperatorRequest, node: str, *, decided_by: str = "operator", reason: str = ""
    ) -> ApprovalDecision:
        """Deny a gate — the Approval Exchange records it; the gated node is not authorized to run."""
        return self._approval.deny(
            _pipeline_session_id(request.identity), node, decided_by=decided_by, reason=reason
        )

    def approval_explanation(self, identity: str, node: str) -> ApprovalExplanation:
        """Explain why a gate required approval and its current state (via the Approval Exchange)."""
        return self._approval.explanation(_pipeline_session_id(identity), node)

    def approval_history(self, identity: str) -> tuple[ApprovalRequest, ...]:
        """The full approval-decision history for the session (via the Approval Exchange)."""
        return self._approval.history(_pipeline_session_id(identity))

    def feedback_knowledge(
        self,
        subject_key: str,
        *,
        actor: str,
        source_run_ref: Reference,
        effect: str,
        feedback_id: str,
    ) -> Reference:
        """Record attributable operator feedback through the Knowledge owner via the pipeline."""
        return self._pipeline.record_knowledge_feedback(
            subject_key,
            actor=actor,
            source_run_ref=source_run_ref,
            effect=effect,
            feedback_id=feedback_id,
        )

    # -- inspect the platform (read-only projections) ------------------------ #

    def status(self, identity: str) -> InteractionStatus:
        """Report the pipeline progress for a session (reconstructed from the log)."""
        session = self._pipeline.session(_pipeline_session_id(identity))
        return InteractionStatus(
            session_id=_interaction_session_id(identity),
            status=session.status.value,
            current_stage=session.current_stage,
            stages_completed=session.stages_completed,
            is_complete=session.status.value == "completed",
        )

    def session(self, identity: str) -> InteractionSession:
        """Reconstruct the operator interaction session from the ``interaction.*`` log."""
        return reconstruct_interaction_session(
            self._pipeline.history(), _interaction_session_id(identity)
        )

    def history(self, identity: str) -> tuple[Event, ...]:
        """The correlated event history for the session's run (the audit trail)."""
        pipe = _pipeline_session_id(identity)
        events = tuple(
            event
            for event in self._pipeline.history()
            if event.identifier.startswith(f"evt-{pipe}-")
            or event.identifier.startswith(f"evt-{_interaction_session_id(identity)}-")
        )
        submitted = next(
            (
                event
                for event in self._pipeline.history()
                if event.type == ievents.INTERACTION_REQUEST_SUBMITTED
                and event.payload.get("session") == _interaction_session_id(identity)
            ),
            None,
        )
        action_ids = (
            {str(value) for value in submitted.payload.get("action_ids", ())}
            if submitted
            else set()
        )
        action_events = tuple(
            event
            for event in self._pipeline.history()
            if event.type.startswith("repository_action.")
            and event.payload.get("action_id") in action_ids
        )
        return tuple(sorted((*events, *action_events), key=lambda event: event.timestamp))

    def execution_graph(self, _identity: str) -> ExecutionGraphView:
        """The frozen Execution Graph topology for the run (reconstructed; never re-planned)."""
        graph = self._pipeline.execution_graph()
        if graph is None:
            return ExecutionGraphView(nodes=(), edges=())
        return ExecutionGraphView(
            nodes=tuple(node.identifier for node in graph.nodes),
            edges=tuple((edge.source_node, edge.target_node) for edge in graph.edges),
        )

    def knowledge(
        self, *, subject: str | None = None, kind: KnowledgeType | None = None
    ) -> KnowledgeView:
        """Inspect Knowledge read-only through the pipeline (the engine is never user-callable)."""
        served = self._pipeline.inspect_knowledge(subject=subject, kind=kind)
        return KnowledgeView(
            items=tuple((item.identity, subject or "", item.type.value) for item in served)
        )

    def replay(self, identity: str) -> InteractionSession:
        """Deterministically reconstruct the operator session from the durable log (no re-execution)."""
        return self.session(identity)

    def explain_lineage(self, identity: str) -> LineageView:
        """Explain the run's execution lineage + the Knowledge that grounded it (from the log)."""
        timeline = self._pipeline.lineage()
        grounded: dict[str, object] = {}
        for event in self._pipeline.history():
            if event.type == "pipeline.knowledge_grounded":
                grounded = dict(event.payload)
        return LineageView(
            stages=tuple((stage.producer, stage.count) for stage in timeline.stages),
            total_events=timeline.total_events,
            knowledge_provenance=grounded,
        )

    # -- formatting + events ------------------------------------------------- #

    def _record(
        self, request: OperatorRequest, run: SpineRun, *, resumed: bool
    ) -> InteractionResponse:
        own_events = _request_events(run.events, request)
        grounding = run.knowledge_grounding
        # If the run paused at an approval boundary, surface the request through the Approval Exchange
        # (it publishes idempotently; a run with no waiting gate is a no-op) — presentation, not logic.
        waiting = run.execution_state.waiting_nodes if run.execution_state is not None else ()
        action_nodes = _human_action_nodes(own_events, request)
        pending = self._approval.publish(
            _pipeline_session_id(request.identity), waiting, human_required=action_nodes
        )
        self._emit(
            request,
            ievents.INTERACTION_RESPONSE_RECORDED,
            {
                "status": run.status.value,
                "knowledge_item_ids": list(run.knowledge_item_ids),
                "knowledge_references": list(grounding.selected_ids) if grounding else [],
                "stages_completed": list(run.pipeline_session.stages_completed),
                "reconstructed": list(run.reconstructed_stages),
                "executed": list(run.executed_stages),
                "resumed": resumed,
            },
        )
        self._obs.responded(stages=len(run.pipeline_session.stages_completed))
        return InteractionResponse(
            session_id=request.interaction_session_id,
            status=run.status.value,
            pipeline_session=run.pipeline_session,
            goal_ref=run.goal_ref,
            plan_ref=run.plan_ref,
            execution_status=run.execution_state.status.value if run.execution_state else None,
            validation_decisions=run.validation_decisions,
            knowledge_item_ids=run.knowledge_item_ids,
            knowledge_grounding=grounding,
            reconstructed_stages=run.reconstructed_stages,
            executed_stages=run.executed_stages,
            progress=run.pipeline_session.stages_completed,
            pending_approvals=pending,
            clarification_requests=run.clarification_requests,
            execution_plan=find_plan(own_events),
            grounding_selection=_grounding_selection(own_events),
            intent_analysis=_event_payload(own_events, "intent.resolved", "analysis"),
            context_package=_event_model(
                own_events, "context.grounding.assembled", "package", ContextPackage
            ),
            repository_profile=_event_payload(own_events, "repository.profiled", "profile"),
        )

    def _emit(self, request: OperatorRequest, event_type: str, payload: Struct) -> None:
        session = request.interaction_session_id
        full: Struct = {"session": session, **payload}
        identifier = f"evt-{session}-{event_type.split('.')[-1]}-{content_hash(full)[:16]}"
        event = ievents.build_event(identifier, event_type, request.correlation, full, self._now())
        if self._infra.event_store.contains(identifier):
            existing = next(
                item for item in self._infra.event_store.read_all() if item.identifier == identifier
            )
            if existing.model_copy(update={"timestamp": event.timestamp}) == event:
                return
            raise DuplicateEventError(identifier)
        self._infra.emit(event)


def _translate(request: OperatorRequest) -> SpineRequest:
    """Request translation — the one operator→constitutional-contract mapping (no reasoning)."""
    return SpineRequest(
        identity=request.identity,
        request_text=request.request_text,
        work_items=request.work_items,
        knowledge_subject=request.knowledge_subject,
        scope=request.scope,
        knowledge_kind=request.knowledge_kind,
        context_fragments=request.context_fragments,
        capabilities=request.capabilities,
        fail=request.fail,
        correlation_identifier=request.correlation_identifier,
        repository_root=request.repository_root,
        planning_step_template=request.planning_step_template,
    )


def _human_action_nodes(events: Sequence[Event], request: OperatorRequest) -> tuple[str, ...]:
    plan = find_plan(tuple(events))
    if plan is None:
        return ()
    action_ids = {
        action.identity for action in request.repository_actions if action.kind == "write_file"
    }
    packages = {
        package.identifier
        for package in plan.work_packages
        if any(
            ref.target_type == "action_request" and ref.identifier in action_ids
            for ref in package.inputs
        )
    }
    return tuple(
        node.identifier
        for node in plan.execution_graph.nodes
        if node.work_package_ref.identifier in packages
    )


def _grounding_selection(events: Sequence[Event]) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.type == "context.grounding.selected":
            return dict(event.payload)
    return None


def _request_events(events: Sequence[Event], request: OperatorRequest) -> tuple[Event, ...]:
    goal_identity = f"goal-{request.identity}"
    scoped: list[Event] = []
    for event in events:
        if event.correlation_identifier != request.correlation:
            continue
        payload = event.payload
        if event.type == "intent.resolved" and payload.get("intent") != request.identity:
            continue
        if event.type == "repository.profiled" and payload.get("request") != request.identity:
            continue
        if event.type == "context.grounding.selected" and not event.identifier.startswith(
            f"evt-context-{goal_identity}-v1-grounding-selected-"
        ):
            continue
        if event.type == "context.grounding.assembled" and payload.get("goal") != goal_identity:
            continue
        if event.type == "planning.execution_plan_assembled":
            plan = payload.get("execution_plan", {})
            parent = plan.get("plan", {}).get("parent_goal", {})
            if parent.get("identifier") != goal_identity:
                continue
        if event.type == "execution.completed":
            state = payload.get("execution_state", {})
            goal = state.get("goal_ref", {})
            if goal.get("identifier") != goal_identity:
                continue
        scoped.append(event)
    return tuple(scoped)


def _event_model(events: Sequence[Event], event_type: str, payload_key: str, model: Any) -> Any:
    event = next((item for item in reversed(events) if item.type == event_type), None)
    return model.model_validate(event.payload[payload_key]) if event is not None else None


def _event_payload(
    events: Sequence[Event], event_type: str, payload_key: str
) -> dict[str, Any] | None:
    event = next((item for item in reversed(events) if item.type == event_type), None)
    return dict(event.payload[payload_key]) if event is not None else None


def _pipeline_session_id(identity: str) -> str:
    return f"pipe-{identity}"


def _interaction_session_id(identity: str) -> str:
    return f"hi-{identity}"
