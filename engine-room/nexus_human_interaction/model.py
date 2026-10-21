"""Human-Interaction value models — the operator-facing request, session, and formatted responses.

The Human Interaction layer owns request *translation* and response *formatting* — it owns no reasoning.
:class:`OperatorRequest` is the operator-facing input the façade translates into a
:class:`~nexus_workflows.spine.SpineRequest`; :class:`InteractionSession` is a ``ValueObject`` projection
of the ``interaction.*`` log (INV-13/14 — the log is truth); the ``*View`` / :class:`InteractionResponse`
values are read-only formatted projections of what the constitutional pipeline returned or the log holds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nexus_approval import ApprovalRequest
from nexus_context import RawContextFragment
from nexus_core.contracts.base import Reference, ValueObject
from nexus_core.contracts.enums import KnowledgeType
from nexus_core.domain import Capability
from nexus_core.domain.context_package import ContextPackage
from nexus_execution.actions import RepositoryAction
from nexus_intent.model import ClarificationRequest
from nexus_planning import WorkItemSpec
from nexus_planning.grounded.model import ExecutionPlan
from nexus_workflows.spine import PipelineSession
from nexus_workflows.spine.learning import KnowledgeSelection


@dataclass(frozen=True, slots=True)
class OperatorRequest:
    """The operator-facing submission — raw intent + the decomposition the façade will run.

    Introduces no new domain concept: it is the Human-Interaction DTO that translates 1:1 into a
    :class:`SpineRequest`. ``identity`` keys the interaction session and the pipeline session so a
    later status / replay / restart addresses the same run.
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
    repository_actions: tuple[RepositoryAction, ...] = ()

    @property
    def interaction_session_id(self) -> str:
        """The durable interaction-session identity (stable per request — replay/restart reuse it)."""
        return f"hi-{self.identity}"

    @property
    def correlation(self) -> str:
        """The correlation identifier threaded through the run (falls back to the request id)."""
        return self.correlation_identifier or f"cor-{self.identity}"


class InteractionSession(ValueObject):
    """The immutable interaction-session projection — a deterministic read of ``interaction.*``.

    Records the operator session lifecycle by reference (never the reasoning): the pipeline session it
    drove, whether a request was submitted and a response recorded, the Knowledge that grounded the run,
    and the constitutional stages completed. Rebuildable from the log (INV-13/14).
    """

    identity: str
    pipeline_session_ref: Reference
    status: str
    submitted: bool
    responded: bool
    knowledge_references: tuple[Reference, ...]
    stages_completed: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InteractionResponse:
    """The formatted result of a submit / restart — what the pipeline produced, operator-shaped."""

    session_id: str
    status: str
    pipeline_session: PipelineSession
    goal_ref: Reference | None
    plan_ref: Reference | None
    execution_status: str | None
    validation_decisions: tuple[str, ...]
    knowledge_item_ids: tuple[str, ...]
    knowledge_grounding: KnowledgeSelection | None
    reconstructed_stages: tuple[str, ...]
    executed_stages: tuple[str, ...]
    progress: tuple[str, ...]
    pending_approvals: tuple[ApprovalRequest, ...] = field(default_factory=tuple)
    clarification_requests: tuple[ClarificationRequest, ...] = ()
    execution_plan: ExecutionPlan | None = None
    grounding_selection: dict[str, object] | None = None
    intent_analysis: dict[str, object] | None = None
    context_package: ContextPackage | None = None
    repository_profile: dict[str, object] | None = None

    @property
    def succeeded(self) -> bool:
        """Whether the pipeline reached Knowledge with every execution node completing normally."""
        return self.status == "completed" and bool(self.knowledge_item_ids)

    @property
    def runtime_completed(self) -> bool:
        """Whether execution completed, independently of outcome validation."""
        return self.execution_status == "completed"

    @property
    def outcome_accepted(self) -> bool | None:
        """Whether every returned validation verdict passed; None means no verdict is available."""
        if not self.validation_decisions:
            return None
        return all(decision == "passed" for decision in self.validation_decisions)

    @property
    def awaiting_approval(self) -> bool:
        """Whether the run paused with a gate awaiting an operator decision (P15)."""
        return bool(self.pending_approvals)


@dataclass(frozen=True, slots=True)
class InteractionStatus:
    """The formatted progress of one pipeline session (a read-only projection)."""

    session_id: str
    status: str
    current_stage: str | None
    stages_completed: tuple[str, ...]
    is_complete: bool


@dataclass(frozen=True, slots=True)
class ExecutionGraphView:
    """The operator-shaped view of the run's frozen Execution Graph (topology only)."""

    nodes: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class KnowledgeView:
    """The operator-shaped view of served Knowledge (references + subject/kind, never mutation)."""

    items: tuple[tuple[str, str, str], ...]  # (identity, subject, kind)


@dataclass(frozen=True, slots=True)
class LineageView:
    """The operator-shaped explanation of execution lineage + the Knowledge provenance of the run."""

    stages: tuple[tuple[str, int], ...]  # (producer, contiguous event count)
    total_events: int
    knowledge_provenance: dict[str, object] = field(default_factory=dict)
