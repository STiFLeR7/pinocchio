"""The Constitutional Pipeline — one deterministic Goal→Knowledge driver (P13/F-1, F-2, F-3).

:class:`ConstitutionalPipeline` is the single spine coordinator. It invokes each constitutional owner
**exactly once**, in dependency order, passing only constitutional contracts::

    Intent → Engineering → Context → Planning → Execution Actuation → [Execution→Validation seam]
        → Validation → Recovery → Reflection → Knowledge

It contains **no business logic** and owns none of the owners' behavior — it reasons/estimates/plans/
traverses/validates/recovers/reflects/learns through nobody's internals. Its only durable facts are the
additive ``pipeline.*`` events; every owner records its own facts on the same shared log unchanged.

Durability + restart (F-2) ride that shared log (ADR-007; INV-13/14/18). The pipeline's restart
checkpoints are the four owner-embedded artifacts on the log — the resolved **Goal** (``intent.resolved``),
the **EngineeringStrategy** (``engineering.strategized``), the **ExecutionPlan**
(``planning.execution_plan_assembled``), and the **ExecutionState** (``execution.completed``). On restart
the coordinator reconstructs each from the log (never re-invoking its owner) and resumes at the first
constitutional boundary not yet on the log; the Execution Actuator itself resumes node-level from the same
log if execution was interrupted mid-flight. Context Engineering is checkpointed jointly with Planning —
its ContextPackage is a transient, deterministic input consumed only by Planning and superseded by the
log-embedded ExecutionPlan, so it is never persisted as a second copy of another owner's artifact.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from nexus_context import ContextRequest, context_reference
from nexus_context.grounding import GroundedContextEngineeringContext, GroundingInputs
from nexus_core.contracts.base import Reference, Struct
from nexus_core.contracts.enums import (
    CapabilityCategory,
    ConfidenceLadder,
    KnowledgeType,
)
from nexus_core.domain.capability import Capability
from nexus_core.domain.context_package import ContextPackage
from nexus_core.domain.event import Event
from nexus_core.domain.execution_graph import ExecutionGraph
from nexus_core.domain.goal import Goal
from nexus_core.domain.knowledge import Knowledge
from nexus_engineering import ENGINEERING_STRATEGIZED, EngineeringContext
from nexus_engineering.model import EngineeringStrategy
from nexus_estimation.composition import EstimationContext
from nexus_execution.actions.boundary import (
    RepositoryAction,
    RepositoryActionBoundary,
    action_is_cancelled,
    action_is_indeterminate,
    record_action_cancelled,
    record_action_denial,
    record_action_request,
    record_indeterminate,
    resolve_action_request,
)
from nexus_execution.actions.runtime import RepositoryActionRuntimeAdapter
from nexus_execution.actuation import (
    EXECUTION_COMPLETED,
    ActuationInputs,
    ActuationStatus,
    ExecutionState,
    build_execution_actuation,
)
from nexus_execution.adapter import RuntimeAdapter
from nexus_execution.results import ExecutionResult
from nexus_infra import (
    DuplicateEventError,
    InfrastructureContext,
    NullObservability,
    Observability,
    content_hash,
)
from nexus_intent.composition import IntentContext
from nexus_intent.events import INTENT_RESOLVED
from nexus_intent.model import ClarificationRequest, IntentAnalysis, request_from_text
from nexus_knowledge import KnowledgeCandidate, KnowledgeContextBundle, KnowledgeQuery
from nexus_planning import WorkItemSpec
from nexus_planning.grounded import ExecutionPlan, GroundedPlanningContext, PlanningInputs
from nexus_planning.grounded.assembler import PLANNING_EXECUTION_PLAN_ASSEMBLED
from nexus_policy import REPOSITORY_ACTION_CLASS, DecisionRequest, repository_action_baseline
from nexus_policy.composition import PolicyContext
from nexus_recovery import RecoveryContextBundle
from nexus_recovery.plan import RecoveryPlan
from nexus_reflection import ReflectionContextBundle
from nexus_reflection.report import ReflectionReport
from nexus_repository import RepositoryProfile, build_repository
from nexus_runtime.events import SystemTimestampSource, TimestampSource
from nexus_validation import ValidationContext, ValidationPolicy
from nexus_validation.report import ValidationReport
from nexus_workflows.executor import ReplayTimeline, reconstruct
from nexus_workflows.spine import events as pevents
from nexus_workflows.spine.bridge import execution_results
from nexus_workflows.spine.learning import KnowledgeSelection, KnowledgeSelector
from nexus_workflows.spine.model import (
    ORDERED_STAGES,
    PipelineSession,
    SpineControl,
    SpineRequest,
    SpineRun,
    SpineStage,
    SpineStatus,
)

_VALIDATION_TARGET_TYPE = "validation_report"

AdapterFactory = Callable[[SpineRequest], RuntimeAdapter]

# Learning disabled (no selector) → an empty grounding selection, i.e. the P13 behavior unchanged.
_EMPTY_SELECTION = KnowledgeSelection(
    subject="",
    kind="",
    governed=False,
    decision="",
    reasoning=(),
    references=(),
    selected_ids=(),
    items=(),
)


# --------------------------------------------------------------------------- #
# Replay integration — reconstruct owner artifacts + the pipeline session         #
# from the shared durable log alone (INV-13/14; no owner re-invoked).             #
# --------------------------------------------------------------------------- #


def find_goal(events: tuple[Event, ...]) -> Goal | None:
    """Reconstruct the resolved Goal from ``intent.resolved`` (no re-understanding — INV-17)."""
    for event in events:
        if event.type == INTENT_RESOLVED:
            return IntentAnalysis.model_validate(event.payload["analysis"]).goal
    return None


def find_strategy(events: tuple[Event, ...]) -> EngineeringStrategy | None:
    """Reconstruct the EngineeringStrategy from ``engineering.strategized`` (no re-inference)."""
    for event in events:
        if event.type == ENGINEERING_STRATEGIZED:
            return EngineeringStrategy.model_validate(event.payload["strategy"])
    return None


def find_plan(events: tuple[Event, ...]) -> ExecutionPlan | None:
    """Reconstruct the ExecutionPlan from ``planning.execution_plan_assembled`` (no re-planning)."""
    for event in events:
        if event.type == PLANNING_EXECUTION_PLAN_ASSEMBLED:
            return ExecutionPlan.model_validate(event.payload["execution_plan"])
    return None


def find_execution_state(events: tuple[Event, ...]) -> ExecutionState | None:
    """Reconstruct the terminal ExecutionState from ``execution.completed`` (no re-execution)."""
    for event in events:
        if event.type == EXECUTION_COMPLETED:
            return ExecutionState.model_validate(event.payload["execution_state"])
    return None


# --------------------------------------------------------------------------- #
# RC2 — goal-scoped restart reconstruction (``_seed``'s own finders)               #
# --------------------------------------------------------------------------- #
#
# ``find_goal``/``find_strategy``/``find_plan``/``find_execution_state`` above return the *first*
# matching fact anywhere in ``events`` — correct only when the log holds exactly one goal. ``_seed``
# scans the *entire* durable log (every goal ever run on this infra), so it must instead find the fact
# that belongs to the request it is actually resuming — matched via each artifact's own goal-reference
# field (never inferred from log position). ``correlation_identifier`` is not a safe key for this: the
# Scheduler deliberately reuses one correlation across every occurrence of a recurring schedule, so two
# genuinely different goal runs (occurrence 0 and occurrence 1) would otherwise look like the same run.


def _own_goal_identity(request: SpineRequest) -> str:
    """The Goal identity Intent Resolution derives for ``request`` (``nexus_intent`` interpreter)."""
    return f"goal-{request.identity}"


def _find_own_goal(events: tuple[Event, ...], goal_identity: str) -> Goal | None:
    for event in events:
        if event.type == INTENT_RESOLVED and event.payload.get("goal") == goal_identity:
            return IntentAnalysis.model_validate(event.payload["analysis"]).goal
    return None


def _find_own_strategy(events: tuple[Event, ...], goal_identity: str) -> EngineeringStrategy | None:
    for event in events:
        if event.type != ENGINEERING_STRATEGIZED:
            continue
        strategy = EngineeringStrategy.model_validate(event.payload["strategy"])
        if strategy.subject_identifier == goal_identity:
            return strategy
    return None


def _find_own_plan(events: tuple[Event, ...], goal_identity: str) -> ExecutionPlan | None:
    for event in events:
        if event.type != PLANNING_EXECUTION_PLAN_ASSEMBLED:
            continue
        plan = ExecutionPlan.model_validate(event.payload["execution_plan"])
        if plan.plan.parent_goal.identifier == goal_identity:
            return plan
    return None


def _find_own_execution_state(
    events: tuple[Event, ...], goal_identity: str
) -> ExecutionState | None:
    for event in events:
        if event.type != EXECUTION_COMPLETED:
            continue
        state = ExecutionState.model_validate(event.payload["execution_state"])
        if state.goal_ref.identifier == goal_identity:
            return state
    return None


def reconstruct_pipeline_session(events: tuple[Event, ...], session_id: str) -> PipelineSession:
    """Rebuild the pipeline session from the ``pipeline.*`` stream (the log is truth — INV-13/14)."""
    prefix = f"evt-{session_id}-"
    completed: list[str] = []
    artifacts: list[tuple[str, str]] = []
    current: str | None = None
    status = SpineStatus.RUNNING
    for event in events:
        if event.producer != pevents.PIPELINE_PRODUCER or not event.identifier.startswith(prefix):
            continue
        if event.type == pevents.PIPELINE_STAGE_STARTED:
            current = str(event.payload.get("stage"))
        elif event.type == pevents.PIPELINE_STAGE_COMPLETED:
            stage = str(event.payload.get("stage"))
            current = stage
            if stage not in completed:
                completed.append(stage)
                artifacts.append((stage, str(event.payload.get("artifact", ""))))
        elif event.type == pevents.PIPELINE_COMPLETED:
            status = SpineStatus.COMPLETED
        elif event.type == pevents.PIPELINE_PAUSED and status is not SpineStatus.COMPLETED:
            status = SpineStatus.PAUSED
    return PipelineSession(
        identity=session_id,
        request_ref=Reference(target_type="spine_request", identifier=session_id),
        status=status,
        current_stage=current,
        stages_completed=tuple(completed),
        stage_artifacts=tuple(artifacts),
        lineage=tuple(completed),
    )


# --------------------------------------------------------------------------- #
# Observability — pipeline-level metadata (instrumentation only, INV-11).         #
# --------------------------------------------------------------------------- #


class PipelineObservability:
    """Pipeline-level counters over the P1 sink (derived convenience, never authoritative)."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def stage(self, stage: SpineStage) -> None:
        self._obs.increment("pipeline.stage_completed")

    def resumed(self, stage: SpineStage) -> None:
        self._obs.increment("pipeline.resumed")

    def completed(self, stages: int) -> None:
        self._obs.observe("pipeline.stages_completed", float(stages))


# --------------------------------------------------------------------------- #
# The coordinator                                                                 #
# --------------------------------------------------------------------------- #


@dataclass
class _RunCtx:
    """Mutable per-run accumulators — the artifacts threaded between constitutional stages."""

    goal: Goal | None = None
    strategy: EngineeringStrategy | None = None
    knowledge_selection: KnowledgeSelection | None = None
    context_package: ContextPackage | None = None
    plan: ExecutionPlan | None = None
    execution_state: ExecutionState | None = None
    execution_results: tuple[ExecutionResult, ...] = ()
    validation_reports: list[ValidationReport] = field(default_factory=list)
    recovery_plans: list[RecoveryPlan] = field(default_factory=list)
    reflection: ReflectionReport | None = None
    knowledge_item_ids: tuple[str, ...] = ()
    goal_ref: Reference | None = None
    strategy_ref: Reference | None = None
    context_ref: Reference | None = None
    plan_ref: Reference | None = None
    clarifications: tuple[ClarificationRequest, ...] = ()
    intent_analysis: IntentAnalysis | None = None
    repository_profile: RepositoryProfile | None = None


class ConstitutionalPipeline:
    """Drives every constitutional owner once, in order, over one shared (durable) log."""

    def __init__(
        self,
        infrastructure: InfrastructureContext,
        *,
        intent: IntentContext,
        engineering: EngineeringContext,
        estimation: EstimationContext,
        policy: PolicyContext,
        grounded_context: GroundedContextEngineeringContext,
        planning: GroundedPlanningContext,
        validation: ValidationContext,
        recovery: RecoveryContextBundle,
        reflection: ReflectionContextBundle,
        knowledge: KnowledgeContextBundle,
        adapter_factory: AdapterFactory,
        action_command_allowlist: Mapping[str, tuple[str, ...]] | None = None,
        action_artifact_directory: str | None = None,
        selector: KnowledgeSelector | None = None,
        timestamps: TimestampSource | None = None,
        now: Callable[[], str] | None = None,
        observability: PipelineObservability | None = None,
    ) -> None:
        self._infra = infrastructure
        self._intent = intent
        self._repository = build_repository(infrastructure)
        self._engineering = engineering
        self._estimation = estimation
        self._policy = policy
        self._grounded_context = grounded_context
        self._planning = planning
        self._validation = validation
        self._recovery = recovery
        self._reflection = reflection
        self._knowledge = knowledge
        self._adapter_factory = adapter_factory
        self._action_command_allowlist = dict(action_command_allowlist or {})
        self._action_artifact_directory = action_artifact_directory
        # The learning integration (P14/A) — optional: absent → no Knowledge grounding (P13 behavior).
        self._selector = selector
        self._timestamps = timestamps or SystemTimestampSource()
        self._now = now or self._timestamps.now
        self._obs = observability or PipelineObservability(infrastructure.observability)

    # -- public entry point -------------------------------------------------- #

    def prepare_repository_actions(
        self,
        *,
        identity: str,
        repository_root: str | None,
        correlation: str,
        work_items: tuple[WorkItemSpec, ...],
        capabilities: tuple[Capability, ...],
        repository_actions: tuple[RepositoryAction, ...],
    ) -> tuple[tuple[WorkItemSpec, ...], tuple[Capability, ...], tuple[RepositoryAction, ...]]:
        """Freeze explicit action inputs and their Planning references before pipeline submission."""
        items = list(work_items)
        canonical_actions: list[RepositoryAction] = []
        for action in repository_actions:
            if action.request_identity != identity:
                raise ValueError(
                    "repository action request identity must match the operator request"
                )
            if repository_root is None:
                raise ValueError("repository actions require an explicit operator workspace")
            updates: dict[str, object] = {
                "workspace_root": os.path.realpath(action.workspace_root),
                "correlation_identifier": correlation,
            }
            if action.kind == "run_test":
                updates["resolved_argv"] = self._action_command_allowlist.get(
                    action.command_id or "", ()
                )
            action = action.model_copy(update=updates)
            canonical_actions.append(action)
            reference = record_action_request(self._infra, action)
            matches = [
                index for index, item in enumerate(items) if item.key == action.work_item_key
            ]
            if matches:
                index = matches[0]
                item = items[index]
                items[index] = item.model_copy(
                    update={
                        "inputs": (*item.inputs, reference),
                        "capability_requirements": tuple(
                            sorted({*item.capability_requirements, "repository_action"})
                        ),
                        "requires_approval": action.kind == "write_file" or item.requires_approval,
                    }
                )
            else:
                items.append(
                    WorkItemSpec(
                        key=action.work_item_key,
                        objective=f"Perform the explicitly requested {action.kind} action",
                        capability_requirements=("repository_action",),
                        inputs=(reference,),
                        requires_approval=action.kind == "write_file",
                    )
                )
        capability_map = {capability.identifier: capability for capability in capabilities}
        capability_map.setdefault(
            "repository_action",
            Capability(
                identifier="repository_action",
                name="First-party repository action",
                version="1",
                category=CapabilityCategory.DEVELOPMENT,
                description="Perform one explicit confined repository action.",
                inputs=(),
                outputs=(),
            ),
        )
        return tuple(items), tuple(capability_map.values()), tuple(canonical_actions)

    def restore_repository_actions(
        self, action_ids: tuple[str, ...]
    ) -> tuple[RepositoryAction, ...]:
        """Resolve immutable submitted action requests from their durable references."""
        return tuple(
            resolve_action_request(
                self._infra,
                Reference(target_type="action_request", identifier=action_id),
            )
            for action_id in action_ids
        )

    def run(self, request: SpineRequest, *, control: SpineControl | None = None) -> SpineRun:
        """Drive (or resume) the whole Goal→Knowledge pipeline; return the immutable outcome."""
        control = control or SpineControl()
        ctx = _RunCtx()
        prior = tuple(self._infra.event_store.read_all())
        resume = self._seed(prior, ctx, request)  # reconstruct completed boundaries from the log
        reconstructed = tuple(stage.value for stage in ORDERED_STAGES if _idx(stage) < _idx(resume))
        self._announce(request, resume, reconstructed)

        executed: list[str] = []
        status = SpineStatus.COMPLETED
        for stage in ORDERED_STAGES:
            if _idx(stage) < _idx(resume):
                continue
            self._emit(request, pevents.PIPELINE_STAGE_STARTED, {"stage": stage.value})
            completed, ref = self._run_stage(stage, ctx, request, control)
            executed.append(stage.value)
            if not completed:  # execution actuation stopped before completing (resumable)
                reason = "clarification_required" if ctx.clarifications else "actuation_incomplete"
                self._emit(
                    request,
                    pevents.PIPELINE_PAUSED,
                    {"stage": stage.value, "reason": reason},
                )
                status = SpineStatus.PAUSED
                break
            self._emit(
                request,
                pevents.PIPELINE_STAGE_COMPLETED,
                {"stage": stage.value, "artifact": ref.identifier if ref else ""},
            )
            self._obs.stage(stage)
            if control.stop_after_stage is stage:
                self._emit(
                    request,
                    pevents.PIPELINE_PAUSED,
                    {"stage": stage.value, "reason": "control"},
                )
                status = SpineStatus.PAUSED
                break

        if status is SpineStatus.COMPLETED:
            self._emit(
                request,
                pevents.PIPELINE_COMPLETED,
                {"stages": [stage.value for stage in ORDERED_STAGES]},
            )
            self._obs.completed(len(ORDERED_STAGES))

        events = tuple(self._infra.event_store.read_all())
        session = reconstruct_pipeline_session(events, request.pipeline_session_id)
        return self._build_run(ctx, session, status, reconstructed, tuple(executed), events)

    # -- read-only inspection surface (the pipeline is the single entry point) - #
    #
    # The Human Interaction layer (P14/B) invokes ONLY the pipeline — never an engine directly. These
    # methods project the shared log (deterministic reconstruction, no re-execution) and delegate the
    # one Knowledge read to its sole owner; the pipeline never becomes a bypass.

    def history(self) -> tuple[Event, ...]:
        """The full event history on the shared log (the audit trail)."""
        return tuple(self._infra.event_store.read_all())

    def session(self, session_id: str) -> PipelineSession:
        """Reconstruct one pipeline session's stage progression from the log (INV-13/14)."""
        return reconstruct_pipeline_session(self.history(), session_id)

    def lineage(self) -> ReplayTimeline:
        """Reconstruct the execution lineage (one producer run per contiguous stage) from the log."""
        return reconstruct(self.history())

    def execution_graph(self) -> ExecutionGraph | None:
        """The frozen Execution Graph for the run, reconstructed from ``planning.*`` (no re-planning)."""
        plan = find_plan(self.history())
        return plan.execution_graph if plan is not None else None

    def execution_state(self) -> ExecutionState | None:
        """The terminal ExecutionState, reconstructed from ``execution.completed`` (no re-execution)."""
        return find_execution_state(self.history())

    def inspect_knowledge(
        self, *, subject: str | None = None, kind: KnowledgeType | None = None
    ) -> tuple[Knowledge, ...]:
        """Read Knowledge through its sole owner (read-only serve — the engine is never user-callable)."""
        return self._knowledge.engine.serve(KnowledgeQuery(subject=subject, kind=kind))

    def record_knowledge_feedback(
        self,
        subject_key: str,
        *,
        actor: str,
        source_run_ref: Reference,
        effect: str,
        feedback_id: str,
    ) -> Reference:
        """Route attributable operator feedback to the Knowledge owner."""
        return self._knowledge.engine.record_feedback(
            subject_key,
            actor=actor,
            source_run_ref=source_run_ref,
            effect=effect,
            feedback_id=feedback_id,
        )

    # -- restart seeding (reconstruct completed boundaries from the log) ------ #

    def _seed(self, events: tuple[Event, ...], ctx: _RunCtx, request: SpineRequest) -> SpineStage:
        """Fill ``ctx`` with *this request's own* log-embedded artifacts; return the first stage to (re)run.

        ``events`` is the entire durable log (every goal ever run on this infra), so each artifact is
        matched to ``request``'s own goal identity (RC2's ``_find_own_*`` — see the note above them),
        not merely the first fact of its type. Without this, a second goal run on the same log would
        seed from the *first* goal's Goal/Plan/ExecutionState found in the log and silently skip
        straight to Validation on someone else's execution, never running its own Intent→Actuation.
        """
        goal_identity = _own_goal_identity(request)
        goal = _find_own_goal(events, goal_identity)
        strategy = _find_own_strategy(events, goal_identity)
        plan = _find_own_plan(events, goal_identity)
        state = _find_own_execution_state(events, goal_identity)
        ctx.repository_profile = next(
            (
                RepositoryProfile.model_validate(event.payload["profile"])
                for event in events
                if event.type == "repository.profiled"
                and request.repository_root is not None
                and event.payload.get("request") == request.identity
                and event.payload.get("root") == os.path.abspath(request.repository_root)
            ),
            None,
        )
        selection_event = next(
            (
                event
                for event in events
                if event.type == pevents.PIPELINE_KNOWLEDGE_GROUNDED
                and event.payload.get("session") == request.pipeline_session_id
            ),
            None,
        )
        if selection_event is not None:
            selection_payload = selection_event.payload
            item_snapshots = selection_payload.get("item_snapshots", [])
            if isinstance(item_snapshots, list):
                items = tuple(Knowledge.model_validate(item) for item in item_snapshots)
                refs = tuple(
                    Reference.model_validate(ref) for ref in selection_payload.get("references", [])
                )
                ctx.knowledge_selection = KnowledgeSelection(
                    subject=str(selection_payload.get("subject", "")),
                    kind=str(selection_payload.get("kind", "")),
                    governed=bool(selection_payload.get("governed", False)),
                    decision=str(selection_payload.get("decision", "")),
                    reasoning=tuple(selection_payload.get("reasoning", [])),
                    references=refs,
                    selected_ids=tuple(selection_payload.get("selected_ids", [])),
                    items=items,
                )
        for event in events:
            if event.type == INTENT_RESOLVED and event.payload.get("intent") == request.identity:
                ctx.intent_analysis = IntentAnalysis.model_validate(event.payload["analysis"])
                if ctx.intent_analysis.intent.raw_request != request.request_text:
                    raise ValueError(
                        f"request identity {request.identity!r} was already used for different text"
                    )
                stored_root = (ctx.intent_analysis.intent.source or {}).get("repository_root")
                requested_root = (
                    os.path.abspath(request.repository_root) if request.repository_root else None
                )
                if stored_root != requested_root:
                    raise ValueError(
                        f"request identity {request.identity!r} was already used with a different repository root"
                    )
                if ctx.intent_analysis.correlation_identifier != request.correlation:
                    raise ValueError(
                        f"request identity {request.identity!r} was already used with a different correlation"
                    )
                if not ctx.intent_analysis.resolved:
                    ctx.clarifications = ctx.intent_analysis.clarifications
                break
        if goal is not None:
            ctx.goal, ctx.goal_ref = goal, Reference(target_type="goal", identifier=goal.identity)
        if strategy is not None:
            ctx.strategy = strategy
            ctx.strategy_ref = Reference(
                target_type="engineering_strategy", identifier=strategy.identity
            )
        if plan is not None:
            ctx.plan = plan
            ctx.plan_ref = Reference(target_type="plan", identifier=plan.plan.identity)
            if plan.context_references:
                ctx.context_ref = plan.context_references[0]
        if state is not None:
            ctx.execution_state = state
        if state is not None:
            return SpineStage.VALIDATION
        if plan is not None:
            return SpineStage.ACTUATION
        if strategy is not None:
            return SpineStage.CONTEXT
        if goal is not None:
            return SpineStage.ENGINEERING
        return SpineStage.INTENT

    def _announce(
        self, request: SpineRequest, resume: SpineStage, reconstructed: tuple[str, ...]
    ) -> None:
        if reconstructed:  # a restart — prior boundaries reconstructed, owners not re-invoked
            self._emit(request, pevents.PIPELINE_RESUMED, {"from_stage": resume.value})
            self._obs.resumed(resume)
        else:
            self._emit(
                request,
                pevents.PIPELINE_STARTED,
                {"request": request.identity, "stages": [s.value for s in ORDERED_STAGES]},
            )

    # -- stage dispatch ------------------------------------------------------ #

    def _run_stage(
        self, stage: SpineStage, ctx: _RunCtx, request: SpineRequest, control: SpineControl
    ) -> tuple[bool, Reference | None]:
        match stage:
            case SpineStage.INTENT:
                return self._stage_intent(ctx, request, control)
            case SpineStage.ENGINEERING:
                return self._stage_engineering(ctx, request, control)
            case SpineStage.CONTEXT:
                return self._stage_context(ctx, request, control)
            case SpineStage.PLANNING:
                return self._stage_planning(ctx, request, control)
            case SpineStage.ACTUATION:
                return self._stage_actuation(ctx, request, control)
            case SpineStage.VALIDATION:
                return self._stage_validation(ctx, request, control)
            case SpineStage.RECOVERY:
                return self._stage_recovery(ctx, request, control)
            case SpineStage.REFLECTION:
                return self._stage_reflection(ctx, request, control)
            case SpineStage.KNOWLEDGE:
                return self._stage_knowledge(ctx, request, control)

    def _stage_intent(
        self, ctx: _RunCtx, request: SpineRequest, _control: SpineControl
    ) -> tuple[bool, Reference | None]:
        analysis = ctx.intent_analysis or self._intent.engine.resolve(
            request_from_text(
                request.identity,
                request.request_text,
                correlation_identifier=request.correlation,
                source={"repository_root": os.path.abspath(request.repository_root)}
                if request.repository_root
                else None,
            )
        )
        ctx.intent_analysis = analysis
        goal = analysis.goal
        if goal is None:
            ctx.clarifications = analysis.clarifications
            return False, None
        ctx.goal = goal
        ctx.goal_ref = Reference(target_type="goal", identifier=goal.identity)
        return True, ctx.goal_ref

    def _stage_engineering(
        self, ctx: _RunCtx, request: SpineRequest, _control: SpineControl
    ) -> tuple[bool, Reference | None]:
        assert ctx.goal is not None
        grounding = self._grounding(
            ctx, request
        )  # Knowledge → Engineering (P14/A; INV-26 indirect)
        strategy = self._engineering.strategize_for_goal(
            ctx.goal,
            estimation_engine=self._estimation.engine,
            policy_engine=self._policy.engine,
            knowledge=grounding.items,
        )
        ctx.strategy = strategy
        ctx.strategy_ref = Reference(
            target_type="engineering_strategy", identifier=strategy.identity
        )
        return True, ctx.strategy_ref

    def _stage_context(
        self, ctx: _RunCtx, request: SpineRequest, _control: SpineControl
    ) -> tuple[bool, Reference | None]:
        assert ctx.goal is not None
        grounding = self._grounding(
            ctx, request
        )  # Knowledge → Context (INV-06, read-only, provenance)
        if request.repository_root and ctx.repository_profile is None:
            ctx.repository_profile = self._repository.engine.profile(
                request.repository_root,
                correlation_identifier=request.correlation,
                request_identifier=request.identity,
            )
        result = self._grounded_context.assembler.assemble(
            GroundingInputs(
                goal=ctx.goal,
                intent=ctx.intent_analysis,
                repository_profile=ctx.repository_profile,
                engineering_strategy=ctx.strategy,
                knowledge=grounding.items,
            ),
            ContextRequest(
                fragments=request.context_fragments,
                correlation_identifier=request.correlation_identifier or None,
            ),
        ).result
        ctx.context_package = result.package
        ctx.context_ref = context_reference(result.package)
        return True, ctx.context_ref

    def _grounding(self, ctx: _RunCtx, request: SpineRequest) -> KnowledgeSelection:
        """Select governed prior Knowledge once per run (deterministic); record references-only provenance.

        Lazy + cached so both Engineering and Context consume the *same* selection, and a restart that
        resumes at Context (Engineering reconstructed) still grounds. With no selector wired, learning is
        off — an empty selection (the P13 behavior).
        """
        if ctx.knowledge_selection is not None:
            return ctx.knowledge_selection
        assert ctx.goal is not None
        if self._selector is None:
            ctx.knowledge_selection = _EMPTY_SELECTION
            return ctx.knowledge_selection
        selection = self._selector.select(
            goal=ctx.goal,
            subject=request.knowledge_subject,
            kind=request.knowledge_kind,
            correlation=request.correlation,
            applicability={"domain": ctx.goal.domain.value},
        )
        ctx.knowledge_selection = selection
        self._emit(request, pevents.PIPELINE_KNOWLEDGE_GROUNDED, selection.provenance())
        return selection

    def _stage_planning(
        self, ctx: _RunCtx, request: SpineRequest, _control: SpineControl
    ) -> tuple[bool, Reference | None]:
        assert ctx.goal is not None
        plan = self._planning.planner.plan(
            PlanningInputs(
                goal=ctx.goal,
                engineering_strategy=ctx.strategy,
                context_package=ctx.context_package,
                work_items=request.work_items,
                operator_steps=ctx.intent_analysis.declared_steps
                if ctx.intent_analysis is not None
                else (),
                operator_step_template=request.planning_step_template,
                assumptions=ctx.intent_analysis.intent.assumptions
                if ctx.intent_analysis is not None
                else (),
                repository_profile_ref=(
                    Reference(
                        target_type="repository_profile", identifier=ctx.repository_profile.identity
                    )
                    if ctx.repository_profile is not None
                    else None
                ),
            )
        )
        ctx.plan = plan
        ctx.plan_ref = Reference(target_type="plan", identifier=plan.plan.identity)
        return True, ctx.plan_ref

    def _stage_actuation(
        self, ctx: _RunCtx, request: SpineRequest, control: SpineControl
    ) -> tuple[bool, Reference | None]:
        plan = ctx.plan
        assert plan is not None
        action_bindings = []
        for package in plan.work_packages:
            refs = tuple(ref for ref in package.inputs if ref.target_type == "action_request")
            if not refs:
                continue
            if len(refs) != 1:
                raise ValueError("one repository action reference per work package is supported")
            action = resolve_action_request(self._infra, refs[0])
            node = next(
                node
                for node in plan.execution_graph.nodes
                if node.work_package_ref.identifier == package.identifier
            )
            action_bindings.append((action, package, node.identifier))
        human_required: list[str] = []
        if action_bindings:
            self._policy.registry.register(repository_action_baseline())
            for action, _package, node_id in action_bindings:
                if action_is_cancelled(self._infra, action.identity):
                    return False, None
                if action_is_indeterminate(self._infra, action.identity):
                    record_indeterminate(self._infra, action)
                    return False, None
                if control.actuation is not None and control.actuation.cancelled:
                    record_action_cancelled(self._infra, action, "cancelled before side effect")
                    return False, None
                if request.repository_root and os.path.realpath(
                    action.workspace_root
                ) != os.path.realpath(request.repository_root):
                    record_action_denial(
                        self._infra,
                        action,
                        "action workspace differs from the explicit operator workspace",
                    )
                    return False, None
                if action.kind == "write_file":
                    human_required.append(node_id)
                attributes = {
                    "action_id": action.identity,
                    "input_digest": action.input_digest,
                    "workspace_root": action.workspace_root,
                    "plan_identity": plan.plan.identity,
                    "pipeline_session": request.pipeline_session_id,
                    "node": node_id,
                    "actor": action.actor,
                    "request_identity": action.request_identity,
                    "work_item_key": action.work_item_key,
                }
                previous = next(
                    (
                        event
                        for event in self._infra.event_store.read_all()
                        if event.type == "policy.evaluated"
                        and event.producer == "policy"
                        and event.payload.get("action_class") == REPOSITORY_ACTION_CLASS
                        and event.payload.get("attributes") == attributes
                    ),
                    None,
                )
                decision_request = DecisionRequest(
                    action_class=REPOSITORY_ACTION_CLASS,
                    correlation_identifier=request.correlation,
                    attributes=attributes,
                )
                current = self._policy.engine.simulate(decision_request)
                if previous is None or previous.payload.get("decision") != current.decision.value:
                    evaluation = self._policy.engine.evaluate(decision_request)
                else:
                    evaluation = current
                if evaluation.decision.value != "allow":
                    record_action_denial(self._infra, action, "Policy DENY or non-ALLOW decision")
                    return False, None
        adapter = self._adapter_factory(request)
        if action_bindings:
            adapter = RepositoryActionRuntimeAdapter(
                adapter,
                self._infra,
                RepositoryActionBoundary(
                    self._infra,
                    command_allowlist=self._action_command_allowlist,
                    artifact_directory=self._action_artifact_directory,
                ),
                action_only=(
                    len(action_bindings) == len(plan.work_packages)
                    and all(
                        {
                            ref.identifier
                            for ref in package.skills
                            if ref.target_type == "capability"
                        }
                        <= {"repository_action"}
                        for _, package, _ in action_bindings
                    )
                ),
            )
        actuation = build_execution_actuation(
            self._infra, adapter=adapter, timestamps=self._timestamps
        )
        state = actuation.actuator.actuate(
            ActuationInputs(
                plan=plan.plan,
                execution_graph=plan.execution_graph,
                execution_strategy=plan.execution_strategy,
                work_packages=plan.work_packages,
                context_references=plan.context_references,
                granted_gates=control.granted_gates,  # P15: gates the Approval Exchange authorized
                human_required_gates=tuple(human_required),
            ),
            control=control.actuation,
        )
        ctx.execution_state = state
        ref = Reference(target_type="execution_state", identifier=state.identity)
        # PAUSED = a resumable interruption (cancel/shutdown). BLOCKED with nodes still WAITING on an
        # ungranted approval is the P15 approval boundary — also resumable, so pause the pipeline and let
        # the Approval Exchange coordinate the decision (Actuation still owns the pause/resume, INV-23).
        # A COMPLETED run, or one BLOCKED purely by a failure, is terminal → hand on to Validation.
        paused = state.status is ActuationStatus.PAUSED or (
            state.status is ActuationStatus.BLOCKED and bool(state.waiting_nodes)
        )
        return not paused, ref

    def _stage_validation(
        self, ctx: _RunCtx, _request: SpineRequest, _control: SpineControl
    ) -> tuple[bool, Reference | None]:
        assert ctx.execution_state is not None and ctx.plan is not None
        events = tuple(self._infra.event_store.read_all())
        results = execution_results(ctx.execution_state, events)  # the F-3 seam
        ctx.execution_results = results
        wp_by_ref = {wp.identifier: wp for wp in ctx.plan.work_packages}
        reports = []
        for result in results:
            work_package = wp_by_ref[result.work_package_ref.identifier]
            existing = self._validation.engine.replay(events, result, work_package)
            action_bound = any(
                reference.target_type == "action_request" for reference in work_package.inputs
            )
            reports.append(
                existing
                or self._validation.engine.validate(
                    result,
                    work_package,
                    events=events,
                    policy=ValidationPolicy(
                        require_explicit_conditions=action_bound,
                        action_artifact_directory=(
                            self._action_artifact_directory
                            or str(Path(tempfile.gettempdir()) / "nexus-action-artifacts")
                        )
                        if action_bound
                        else None,
                    ),
                )
            )
        ctx.validation_reports = reports
        ref = (
            Reference(target_type=_VALIDATION_TARGET_TYPE, identifier=reports[0].identity)
            if reports
            else None
        )
        return True, ref

    def _stage_recovery(
        self, ctx: _RunCtx, _request: SpineRequest, _control: SpineControl
    ) -> tuple[bool, Reference | None]:
        events = tuple(self._infra.event_store.read_all())
        ctx.recovery_plans = [
            self._recovery.engine.recover(report, result, events=events)
            for report, result in zip(ctx.validation_reports, ctx.execution_results, strict=True)
        ]
        return True, None

    def _stage_reflection(
        self, ctx: _RunCtx, request: SpineRequest, _control: SpineControl
    ) -> tuple[bool, Reference | None]:
        events = tuple(self._infra.event_store.read_all())
        report = self._reflection.engine.reflect(
            request.scope,
            execution_results=tuple(ctx.execution_results),
            validation_reports=tuple(ctx.validation_reports),
            recovery_plans=tuple(ctx.recovery_plans),
            events=events,
        )
        ctx.reflection = report
        return True, report.reference()

    def _stage_knowledge(
        self, ctx: _RunCtx, request: SpineRequest, _control: SpineControl
    ) -> tuple[bool, Reference | None]:
        assert ctx.reflection is not None
        ctx.knowledge_item_ids = self._write_knowledge(
            request,
            ctx.reflection,
            ctx.validation_reports,
            ctx.goal_ref,
            ctx.goal,
            ctx.recovery_plans,
        )
        ref = (
            Reference(target_type="knowledge", identifier=ctx.knowledge_item_ids[0])
            if ctx.knowledge_item_ids
            else None
        )
        return True, ref

    def _write_knowledge(
        self,
        request: SpineRequest,
        reflection: ReflectionReport,
        reports: list[ValidationReport],
        goal_ref: Reference | None,
        goal: Goal | None,
        recovery_plans: list[RecoveryPlan],
    ) -> tuple[str, ...]:
        if goal_ref is None or goal is None:
            return ()
        items: list[str] = []
        for advisory in reflection.knowledge_candidates:
            pattern = next(
                (
                    item
                    for item in reflection.patterns
                    if advisory.source_pattern_ref is not None
                    and item.identity == advisory.source_pattern_ref.identifier
                ),
                None,
            )
            pattern_refs = set()
            if pattern is not None:
                pattern_refs = {ref.identifier for ref in pattern.evidence_refs}
            report_sessions = {
                plan.session_ref.identifier
                for plan in recovery_plans
                if plan.identity in pattern_refs
            }
            matching_reports = tuple(
                report
                for report in reports
                if (
                    report.identity in pattern_refs
                    or report.session_ref.identifier in pattern_refs
                    or report.session_ref.identifier in report_sessions
                    or (not pattern_refs and len(reports) == 1)
                )
            )
            if not matching_reports:
                continue
            evidence = tuple(
                {
                    (ref.target_type, ref.identifier): ref
                    for report in matching_reports
                    for ref in report.evidence_refs
                }.values()
            )
            if not evidence:
                continue
            candidate = KnowledgeCandidate(
                identity=advisory.identity,
                kind=request.knowledge_kind,
                subject=request.knowledge_subject,
                statement=f"{request.knowledge_subject}: {advisory.summary}",
                confidence=ConfidenceLadder.OBSERVED,
                evidence_refs=evidence,
                source_goal_ref=goal_ref,
                source_run_refs=tuple(report.session_ref for report in matching_reports),
                validation_report_refs=tuple(report.reference() for report in matching_reports),
                domain=goal.domain,
                applicability={"domain": goal.domain.value},
                supersedes_subject=request.knowledge_supersedes_subject,
                originating_reflection_ref=reflection.reference(),
                source_pattern_ref=advisory.source_pattern_ref,
                correlation_identifier=reflection.correlation_identifier,
            )
            outcome = self._knowledge.engine.ingest(candidate)
            if outcome.item is not None:
                items.append(outcome.item.identity)
        return tuple(items)

    # -- outcome + events ---------------------------------------------------- #

    def _build_run(
        self,
        ctx: _RunCtx,
        session: PipelineSession,
        status: SpineStatus,
        reconstructed: tuple[str, ...],
        executed: tuple[str, ...],
        events: tuple[Event, ...],
    ) -> SpineRun:
        return SpineRun(
            pipeline_session=session,
            status=status,
            goal_ref=ctx.goal_ref,
            strategy_ref=ctx.strategy_ref,
            context_ref=ctx.context_ref,
            plan_ref=ctx.plan_ref,
            execution_state=ctx.execution_state,
            execution_outcomes=tuple(r.outcome.value for r in ctx.execution_results),
            validation_decisions=tuple(rep.decision.value for rep in ctx.validation_reports),
            recovery_decisions=tuple(pl.decision.value for pl in ctx.recovery_plans),
            reflection_ref=ctx.reflection.reference() if ctx.reflection is not None else None,
            knowledge_item_ids=ctx.knowledge_item_ids,
            knowledge_grounding=ctx.knowledge_selection,
            clarification_requests=ctx.clarifications,
            reconstructed_stages=reconstructed,
            executed_stages=executed,
            events=events,
        )

    def _emit(self, request: SpineRequest, event_type: str, payload: Struct) -> None:
        session = request.pipeline_session_id
        full: Struct = {"session": session, **payload}
        identifier = f"evt-{session}-{event_type.split('.')[-1]}-{content_hash(full)[:16]}"
        event = pevents.build_event(identifier, event_type, request.correlation, full, self._now())
        if self._infra.event_store.contains(identifier):
            existing = next(
                item for item in self._infra.event_store.read_all() if item.identifier == identifier
            )
            if existing.model_copy(update={"timestamp": event.timestamp}) == event:
                return
            raise DuplicateEventError(identifier)
        self._infra.emit(event)


def _idx(stage: SpineStage) -> int:
    return ORDERED_STAGES.index(stage)
