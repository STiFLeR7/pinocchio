"""Execution History — the single constitutional owner of historical operational facts (Grounding).

Given a query, it **reconstructs history once** from the authoritative event log and produces one
immutable, facts-only :class:`~nexus_history.model.ExecutionHistoryProfile`: previous executions,
timeline, runtime/validation/recovery/reflection history, knowledge lineage, artifacts, evidence,
frequency, and goal/work-package/runtime-selection/operator/repository history. It only *retrieves*:
it never classifies, estimates, reasons, plans, executes, recovers, validates, reflects, or decides
policy (each proven by an import-level guardrail).

History is **reconstructed from authoritative events, never duplicated** — the projection reads
``runtime.*`` / ``validation.*`` / ``recovery.*`` / ``reflection.*`` / ``knowledge.*`` (and the
orchestration/plan facts around them), excluding the subsystem's own ``execution_history.*`` facts so
repeated projections stay idempotent. The projection runs once, the engine records **one**
``execution_history.projected`` fact embedding the profile (INV-17), and replay reconstructs the view
without re-projecting. Persistence rides the P1/ADR-007 substrate through the injected infrastructure,
so restart reconstructs an identical view.
"""

from __future__ import annotations

from collections.abc import Callable

from nexus_core.domain.event import Event
from nexus_core.events.interfaces import EventEmitter
from nexus_core.persistence.interfaces import EventStore
from nexus_history import ids
from nexus_history.events import EXECUTION_HISTORY_PROJECTED, build_event, system_now
from nexus_history.model import ExecutionHistoryProfile, HistoryQuery
from nexus_history.observability import HistoryObservability
from nexus_history.persistence import HistoryRepositories
from nexus_history.projection import project

PROJECTOR_VERSION = "1"


class ExecutionHistory:
    """Deterministic, facts-only historical retrieval (reconstruct once, emit once, replay forever)."""

    def __init__(
        self,
        *,
        reader: EventStore | None = None,
        emitter: EventEmitter | None = None,
        repositories: HistoryRepositories | None = None,
        observability: HistoryObservability | None = None,
        now: Callable[[], str] | None = None,
        projector_version: str = PROJECTOR_VERSION,
    ) -> None:
        self._reader = reader
        self._emitter = emitter
        self._repos = repositories
        self._obs = observability or HistoryObservability()
        self._now = now or system_now
        self._version = projector_version

    @property
    def projector_version(self) -> str:
        """The version of the projector (a versioned input recorded on every profile — INV-17)."""
        return self._version

    def profile(
        self, query: HistoryQuery | None = None, *, persist: bool = True
    ) -> ExecutionHistoryProfile:
        """Reconstruct one immutable, facts-only historical view (identical log → identical view)."""
        query = query or HistoryQuery()
        events = tuple(self._reader.read_all()) if self._reader is not None else ()
        draft = project(events, query, self._version)
        profile = self._finish(draft, query)
        if persist:
            self._record(profile)
        return profile

    # -- assembly ----------------------------------------------------------- #

    def _finish(
        self, draft: ExecutionHistoryProfile, query: HistoryQuery
    ) -> ExecutionHistoryProfile:
        identity = ids.profile_id(draft.scope, draft.model_dump(mode="json"))
        return draft.model_copy(
            update={
                "identity": identity,
                "correlation_identifier": query.correlation_identifier or identity,
                "timestamp": self._now(),
            }
        )

    # -- persistence + events ----------------------------------------------- #

    def _record(self, profile: ExecutionHistoryProfile) -> None:
        self._obs.projected(
            scope=profile.scope,
            event_count=profile.event_count,
            execution_count=profile.execution_count,
        )
        if self._repos is not None:
            self._repos.profiles.add(profile)
        if self._emitter is not None:
            self._emitter.emit(self._projected_event(profile))

    def _projected_event(self, profile: ExecutionHistoryProfile) -> Event:
        payload = {
            "scope": profile.scope,
            "projector_version": profile.projector_version,
            "event_count": profile.event_count,
            "execution_count": profile.execution_count,
            "profile": profile.model_dump(mode="json"),
        }
        return build_event(
            ids.projected_event_id(profile.correlation_identifier, payload),
            EXECUTION_HISTORY_PROJECTED,
            profile.correlation_identifier,
            payload,
            self._now(),
        )
