"""OperatorSession — the one coherent operator interface over the platform (Milestone 1).

An :class:`OperatorSession` lets a human operate Nexus without invoking engines directly: submit a
Goal, generate a briefing, then monitor, inspect, search, and aggregate — all through one object.
It is a **consumer**: every submission drives the existing end-to-end pipeline
(:class:`~nexus_workflows.WorkflowCoordinator`) or the existing briefing product
(:class:`~nexus_briefings.BriefingCoordinator`), and every read (timeline, explorer, search,
dashboard) is a pure projection of persisted state. It holds no engine logic.

Learning accumulates across a session: the durable Knowledge repositories are threaded from one
submission to the next, so Knowledge grows, a later submission's Planning consumes it (INV-26), and
the dashboard reflects the growth — exactly the existing feedback loop, driven by the operator.
"""

from __future__ import annotations

from nexus_briefings import Brief, BriefingCoordinator, BriefType
from nexus_execution.adapter import RuntimeAdapter
from nexus_knowledge.persistence import KnowledgeRepositories
from nexus_operator.dashboard import OperationalDashboard, build_dashboard
from nexus_operator.explorer import OperationalExplorer
from nexus_operator.history import SessionHistory, SubmissionKind, SubmissionRecord
from nexus_operator.search import SearchResults, search
from nexus_operator.submission import GoalSubmission, reference_submission, submission_request
from nexus_operator.timeline import OperationalTimeline, TimelineCoordinator
from nexus_runtime_adapters import (
    AdapterRegistry,
    RuntimeInvocationProfile,
    build_default_adapter_registry,
)
from nexus_workflows import (
    PipelineBuilder,
    ReplayTimeline,
    WorkflowCoordinator,
    WorkflowRequest,
    WorkflowRun,
    reconstruct,
)
from nexus_workflows.coordinator import AdapterFactory

_DEFAULT_RUNTIME = "claude-code"


class OperatorSession:
    """One coherent, stateful operator interface over the existing control plane."""

    def __init__(
        self,
        *,
        adapters: AdapterRegistry | None = None,
        briefings: BriefingCoordinator | None = None,
    ) -> None:
        self._adapters = adapters or build_default_adapter_registry()
        self._briefings = briefings or BriefingCoordinator(self._adapters)
        self._history = SessionHistory()
        self._knowledge: KnowledgeRepositories | None = None
        self._seq = 0
        self._timeline = TimelineCoordinator()

    # -- read-only session state --------------------------------------------- #

    @property
    def history(self) -> SessionHistory:
        """Every submission made this session, in order."""
        return self._history

    @property
    def knowledge_repositories(self) -> KnowledgeRepositories | None:
        """The accumulated Knowledge store (``None`` before the first submission)."""
        return self._knowledge

    @property
    def explorer(self) -> OperationalExplorer:
        """A read-only explorer over everything the session has produced (Milestone 3)."""
        return OperationalExplorer(self._history, self._knowledge)

    @property
    def dashboard(self) -> OperationalDashboard:
        """Aggregate operational information derived from persisted state (Milestone 5)."""
        return build_dashboard(self._history, self._knowledge)

    def timeline(self, submission_id: str) -> OperationalTimeline | None:
        """The unified execution timeline for a submission (Milestone 2)."""
        record = self._history.get(submission_id)
        return self._timeline.build(record) if record is not None else None

    def search(self, query: str) -> SearchResults:
        """Deterministically search Goals, Knowledge, Briefings, Validation (Milestone 4)."""
        return search(query, history=self._history, knowledge=self._knowledge)

    def replay(self, submission_id: str) -> ReplayTimeline | None:
        """Reconstruct a submission's history from its event log alone (no live engine)."""
        record = self._history.get(submission_id)
        return reconstruct(record.run.events) if record is not None else None

    # -- submissions (drive the existing pipeline) --------------------------- #

    def submit_goal(
        self,
        submission: GoalSubmission | None = None,
        *,
        runtime_identity: str = _DEFAULT_RUNTIME,
        fail: bool = False,
    ) -> SubmissionRecord:
        """Submit a Goal, drive the full pipeline, and retain the outcome."""
        resolved = submission or reference_submission()
        built = PipelineBuilder(knowledge_repositories=self._knowledge).build()
        request = submission_request(resolved, run=self._next_run(), fail=fail)
        coordinator = WorkflowCoordinator(built, adapter_factory=self._factory(runtime_identity))
        wf_run: WorkflowRun = coordinator.run(request)
        self._knowledge = built.knowledge.repositories
        return self._record(
            SubmissionKind.GOAL, resolved.outcome, runtime_identity, wf_run, brief=None
        )

    def generate_briefing(
        self,
        brief_type: BriefType | None = None,
        *,
        runtime_identity: str = _DEFAULT_RUNTIME,
        fail: bool = False,
    ) -> SubmissionRecord:
        """Generate a briefing through the existing product and retain the outcome."""
        session = self._briefings.generate(
            brief_type,
            runtime_identity=runtime_identity,
            run=self._next_run(),
            fail=fail,
            knowledge_repositories=self._knowledge,
        )
        self._knowledge = session.knowledge_repositories
        return self._record(
            SubmissionKind.BRIEFING,
            session.brief.title,
            runtime_identity,
            session.run,
            brief=session.brief,
        )

    # -- helpers ------------------------------------------------------------- #

    def _record(
        self,
        kind: SubmissionKind,
        title: str,
        runtime_identity: str,
        run: WorkflowRun,
        *,
        brief: Brief | None,
    ) -> SubmissionRecord:
        record = SubmissionRecord(
            submission_id=f"sub-{self._seq}",
            kind=kind,
            title=title,
            runtime_identity=runtime_identity,
            run=run,
            brief=brief,
        )
        self._history = self._history.with_record(record)
        return record

    def _next_run(self) -> str:
        self._seq += 1
        return f"op{self._seq}"

    def _factory(self, runtime_identity: str) -> AdapterFactory:
        def factory(request: WorkflowRequest) -> RuntimeAdapter:
            return self._adapters.create(
                runtime_identity, profile=RuntimeInvocationProfile(fail=request.fail)
            )

        return factory
