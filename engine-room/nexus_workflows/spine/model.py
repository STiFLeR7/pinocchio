"""Constitutional-spine value models — the pipeline stages, events, session projection, and outcome.

The constitutional pipeline coordinates the constitutional *owners* in order (Understand → Reason →
Contextualize → Plan → Actuate → Validate → Recover → Reflect → Learn) and owns none of their
behavior. Its own durable facts are the additive ``pipeline.*`` events; the :class:`PipelineSession`
is a **projection** of that stream (INV-13/14 — the log is truth, the session is derived), never a
new frozen domain object (INV-07). :class:`SpineRequest` is the text-first pipeline input (Intent
resolves it into a Goal); :class:`SpineRun` is the immutable outcome; :class:`SpineControl` bounds a
run for graceful stop + restart demonstration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from nexus_context import RawContextFragment
from nexus_core.contracts.base import Reference, ValueObject
from nexus_core.contracts.enums import KnowledgeType
from nexus_core.domain import Capability
from nexus_core.domain.event import Event
from nexus_execution.actuation import ActuationControl, ExecutionState
from nexus_intent.model import ClarificationRequest
from nexus_planning import WorkItemSpec
from nexus_workflows.spine.learning import KnowledgeSelection


class SpineStage(StrEnum):
    """The constitutional stages the pipeline drives, in dependency order (each owner invoked once)."""

    INTENT = "intent"
    ENGINEERING = "engineering"
    CONTEXT = "context"
    PLANNING = "planning"
    ACTUATION = "actuation"
    VALIDATION = "validation"
    RECOVERY = "recovery"
    REFLECTION = "reflection"
    KNOWLEDGE = "knowledge"


ORDERED_STAGES: tuple[SpineStage, ...] = tuple(SpineStage)


class SpineStatus(StrEnum):
    """The projected aggregate state of one pipeline run."""

    RUNNING = "running"
    COMPLETED = "completed"  # reached Knowledge
    PAUSED = "paused"  # gracefully stopped before Knowledge — resumable from the durable log


class PipelineSession(ValueObject):
    """The immutable pipeline-session projection — a deterministic read of the ``pipeline.*`` stream.

    Records *which* constitutional stages have completed and the reference each produced (never the
    artifact itself — the owner owns that, INV-07), plus the stage lineage. Rebuildable from the log
    (INV-13/14), so a reopened durable file reconstructs the session and its stage progression exactly.
    """

    identity: str
    request_ref: Reference
    status: SpineStatus
    current_stage: str | None
    stages_completed: tuple[str, ...]
    stage_artifacts: tuple[tuple[str, str], ...]  # (stage, produced-artifact reference id)
    lineage: tuple[str, ...]  # stage completion order

    def completed(self, stage: SpineStage) -> bool:
        """Whether ``stage`` is recorded complete on the durable pipeline log."""
        return stage.value in self.stages_completed


@dataclass(frozen=True, slots=True)
class SpineRequest:
    """The immutable, text-first input to the constitutional pipeline (Goal→Knowledge).

    ``request_text`` is the raw operator request Intent Resolution understands into a Goal — the
    pipeline starts *before* the Goal, not from one. Everything else mirrors the incumbent
    ``WorkflowRequest`` and introduces no new domain concept. ``identity`` seeds the Intent request id
    and the durable pipeline-session id, so a restart addresses the same session.
    """

    identity: str
    request_text: str
    work_items: tuple[WorkItemSpec, ...]
    knowledge_subject: str
    scope: str
    knowledge_kind: KnowledgeType = KnowledgeType.LESSON
    context_fragments: tuple[RawContextFragment, ...] = ()
    capabilities: tuple[Capability, ...] = ()
    fail: bool = False
    correlation_identifier: str = ""
    repository_root: str | None = None
    planning_step_template: WorkItemSpec | None = None
    knowledge_supersedes_subject: str | None = None

    @property
    def pipeline_session_id(self) -> str:
        """The durable pipeline-session identity (stable per request — a restart reuses it)."""
        return f"pipe-{self.identity}"

    @property
    def correlation(self) -> str:
        """The correlation identifier threaded through every stage (falls back to the request id)."""
        return self.correlation_identifier or f"cor-{self.identity}"


@dataclass
class SpineControl:
    """Cooperative bound for one pipeline run — used to demonstrate graceful stop + durable restart.

    ``stop_after_stage`` stops the pipeline gracefully once that constitutional stage completes,
    leaving the rest for a later run to resume from the durable log (never from the Goal — INV-18).
    ``actuation`` is forwarded to the Execution Actuator so a run can be interrupted *mid-execution*
    (the actuator then resumes node-level from its own ``execution.*`` log). ``granted_gates`` are the
    approval-gate node ids already authorized out-of-band (P15): the Approval Exchange reconstructs them
    from its durable ``approval.*`` log and supplies them here so a resumed run drives the now-approved
    nodes — the pipeline forwards them to Actuation's existing ``granted_gates`` input and decides nothing.
    """

    stop_after_stage: SpineStage | None = None
    actuation: ActuationControl | None = None
    granted_gates: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SpineRun:
    """The immutable outcome of one end-to-end constitutional-pipeline execution."""

    pipeline_session: PipelineSession
    status: SpineStatus
    goal_ref: Reference | None
    strategy_ref: Reference | None
    context_ref: Reference | None
    plan_ref: Reference | None
    execution_state: ExecutionState | None
    execution_outcomes: tuple[str, ...]
    validation_decisions: tuple[str, ...]
    recovery_decisions: tuple[str, ...]
    reflection_ref: Reference | None
    knowledge_item_ids: tuple[str, ...]
    knowledge_grounding: KnowledgeSelection | None  # prior Knowledge that grounded this run (P14/A)
    reconstructed_stages: tuple[str, ...]  # stages skipped on restart (owner not re-invoked)
    executed_stages: tuple[str, ...]  # stages actually invoked this run
    events: tuple[Event, ...] = field(default_factory=tuple)
    clarification_requests: tuple[ClarificationRequest, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Whether the pipeline reached Knowledge with every execution node completing normally."""
        return (
            self.status is SpineStatus.COMPLETED
            and bool(self.execution_outcomes)
            and all(outcome == "completed" for outcome in self.execution_outcomes)
        )
