"""``nexus_operator`` — the Nexus Operator Experience (Productization Program 1).

The operational interface over the existing platform: a human operates Nexus through one coherent
:class:`OperatorSession` without invoking engines directly. It is a **consumer** — it introduces no
new engine, contract, ADR, or invariant, and every capability consumes existing public APIs:

* **submit a Goal** and drive the full pipeline (Context → … → Knowledge → Briefings);
* **monitor** via a unified :class:`OperationalTimeline` where every entry links to persisted
  evidence (Milestone 2);
* **inspect** Goals, Plans, Work Packages, Runtime Sessions, Validation Reports, Recovery Plans,
  Reflection Reports, Knowledge Items, and Briefings through a read-only
  :class:`OperationalExplorer` (Milestone 3);
* **search** Goals, Knowledge, Briefings, and Validation Reports deterministically — no vectors, no
  embeddings (Milestone 4);
* review an :class:`OperationalDashboard` aggregated entirely from persisted state (Milestone 5).

Dependency direction: ``nexus_operator`` sits above the integration layers it consumes
(``nexus_workflows``, ``nexus_runtime_adapters``, ``nexus_briefings``) and every engine; it is
imported by nothing. It modifies no engine, contract, ADR, or invariant.
"""

from __future__ import annotations

from nexus_operator.dashboard import OperationalDashboard, build_dashboard
from nexus_operator.explorer import (
    BriefingView,
    GoalView,
    KnowledgeItemView,
    OperationalExplorer,
    PlanView,
    RecoveryPlanView,
    ReflectionReportView,
    RuntimeSessionView,
    ValidationReportView,
    WorkPackageView,
)
from nexus_operator.history import SessionHistory, SubmissionKind, SubmissionRecord
from nexus_operator.search import SearchDomain, SearchHit, SearchResults, search
from nexus_operator.session import OperatorSession
from nexus_operator.submission import (
    OPERATOR_CAPABILITY,
    GoalSubmission,
    reference_submission,
    submission_request,
)
from nexus_operator.timeline import (
    OperationalTimeline,
    TimelineCoordinator,
    TimelineEntry,
)

__version__ = "2.5.0"

__all__ = [
    "OPERATOR_CAPABILITY",
    "BriefingView",
    "GoalSubmission",
    "GoalView",
    "KnowledgeItemView",
    "OperationalDashboard",
    "OperationalExplorer",
    "OperationalTimeline",
    "OperatorSession",
    "PlanView",
    "RecoveryPlanView",
    "ReflectionReportView",
    "RuntimeSessionView",
    "SearchDomain",
    "SearchHit",
    "SearchResults",
    "SessionHistory",
    "SubmissionKind",
    "SubmissionRecord",
    "TimelineCoordinator",
    "TimelineEntry",
    "ValidationReportView",
    "WorkPackageView",
    "build_dashboard",
    "reference_submission",
    "search",
    "submission_request",
]
