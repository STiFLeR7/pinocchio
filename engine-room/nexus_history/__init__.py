"""``nexus_history`` — the constitutional Execution History subsystem (Grounding).

The **single owner of historical operational facts** (Constitution, Grounding plane; INV-02). Given a
query the :class:`~nexus_history.engine.ExecutionHistory` engine **reconstructs history once** from
the authoritative event log and produces one immutable, facts-only
:class:`~nexus_history.model.ExecutionHistoryProfile`: previous executions, execution timeline,
runtime history, runtime-selection history, validation history, recovery history, reflection history,
knowledge lineage, historical artifacts, historical evidence, execution frequency, goal history, work
package history, operator history, and repository execution history — grounded facts only.

It only retrieves. It **never** classifies, estimates, reasons, plans, executes, recovers, validates,
reflects, or decides policy (each proven by an import-level guardrail). The profile contains **no
recommendations, no scoring, no confidence, no reasoning** — only historical understanding, a pure
function of the operational log.

History is reconstructed from authoritative events, **never duplicated**: the projection reads
``runtime.*`` / ``validation.*`` / ``recovery.*`` / ``reflection.*`` / ``knowledge.*`` (and the
orchestration/plan facts around them) and excludes the subsystem's own ``execution_history.*`` facts,
so repeated projections stay idempotent and replay/restart reconstruct an identical view. Repository
Intelligence consumes history through its execution-history seam; Engineering Intelligence consumes
historical facts — both by value, neither queries the log itself. Execution History imports neither.
It reuses the P1 substrate and integrates through additive composition (:func:`build_history`).
"""

from __future__ import annotations

from nexus_history.composition import HistoryContext, build_history
from nexus_history.engine import PROJECTOR_VERSION, ExecutionHistory
from nexus_history.events import EXECUTION_HISTORY_PROJECTED
from nexus_history.model import (
    ArtifactHistory,
    EventFrequency,
    EvidenceHistory,
    ExecutionEpisode,
    ExecutionHistoryProfile,
    GoalHistory,
    HistoryQuery,
    KnowledgeLineage,
    OperatorHistory,
    RecoveryHistory,
    ReflectionHistory,
    RepositoryExecutionHistory,
    RepositorySeam,
    RuntimeHistory,
    TimelineEntry,
    ValidationHistory,
    WorkPackageHistory,
)
from nexus_history.persistence import HistoryRepositories, build_history_repositories

__version__ = "2.5.0"

__all__ = [
    "EXECUTION_HISTORY_PROJECTED",
    "PROJECTOR_VERSION",
    "ArtifactHistory",
    "EventFrequency",
    "EvidenceHistory",
    "ExecutionEpisode",
    "ExecutionHistory",
    "ExecutionHistoryProfile",
    "GoalHistory",
    "HistoryContext",
    "HistoryQuery",
    "HistoryRepositories",
    "KnowledgeLineage",
    "OperatorHistory",
    "RecoveryHistory",
    "ReflectionHistory",
    "RepositoryExecutionHistory",
    "RepositorySeam",
    "RuntimeHistory",
    "TimelineEntry",
    "ValidationHistory",
    "WorkPackageHistory",
    "__version__",
    "build_history",
    "build_history_repositories",
]
