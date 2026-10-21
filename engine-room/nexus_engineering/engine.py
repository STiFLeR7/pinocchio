"""Engineering Intelligence — the single constitutional owner of engineering reasoning (Reason).

Given the immutable :class:`~nexus_engineering.model.ReasoningInputs` (Goal, Estimation, Policy
ceiling, Knowledge, Repository Understanding, Preferences, Environment) EI **reasons** and produces
exactly one immutable :class:`~nexus_engineering.model.EngineeringStrategy` — a coherent,
declarative decision about *how work should proceed*. It reasons; it never executes, plans,
evaluates policy, estimates quantitatively, selects a runtime, resolves a Skill, or judges
completion (`engineering/01`, `03`).

The reasoner runs once (`reasoner.py`, the determinism seam) and the engine records **one**
``engineering.strategized`` fact embedding the Strategy (INV-17): reason first, emit once, replay
forever. Persistence rides the P1/ADR-007 substrate through the injected infrastructure, so replay
reconstructs the decision identically after restart without re-inference.
"""

from __future__ import annotations

from collections.abc import Callable

from nexus_core.domain.event import Event
from nexus_core.events.interfaces import EventEmitter
from nexus_engineering import ids
from nexus_engineering.events import ENGINEERING_STRATEGIZED, build_event, system_now
from nexus_engineering.model import EngineeringStrategy, ReasoningInputs
from nexus_engineering.observability import EngineeringObservability
from nexus_engineering.persistence import EngineeringRepositories
from nexus_engineering.reasoner import DeterministicReasoner, Reasoner


class EngineeringIntelligence:
    """Reasons over immutable inputs to one immutable, explainable, replayable Engineering Strategy."""

    def __init__(
        self,
        reasoner: Reasoner | None = None,
        *,
        emitter: EventEmitter | None = None,
        repositories: EngineeringRepositories | None = None,
        observability: EngineeringObservability | None = None,
        now: Callable[[], str] | None = None,
    ) -> None:
        self._reasoner: Reasoner = reasoner or DeterministicReasoner()
        self._emitter = emitter
        self._repos = repositories
        self._obs = observability or EngineeringObservability()
        self._now = now or system_now

    @property
    def reasoner_version(self) -> str:
        """The version of the reasoning strategy in use (recorded on every Strategy — INV-17)."""
        return self._reasoner.version

    def strategize(self, inputs: ReasoningInputs, *, persist: bool = True) -> EngineeringStrategy:
        """Reason over ``inputs`` to one immutable Strategy (identical inputs → identical Strategy)."""
        strategy = self._reasoner.reason(inputs, now=self._now())
        if persist:
            self._record(strategy)
        return strategy

    # -- persistence + events ----------------------------------------------- #

    def _record(self, strategy: EngineeringStrategy) -> None:
        self._obs.strategized(
            strategy.classification.selection[0],
            strategy.autonomy_level.selection[0],
            strategy.risk_assessment.selection[0],
        )
        if self._repos is not None:
            self._repos.strategies.add(strategy)
        if self._emitter is not None:
            self._emitter.emit(self._strategized_event(strategy))

    def _strategized_event(self, strategy: EngineeringStrategy) -> Event:
        payload = {
            "subject": strategy.subject_identifier,
            "reasoner_version": strategy.reasoner_version,
            "classification": strategy.classification.selection[0],
            "autonomy": strategy.autonomy_level.selection[0],
            "risk": strategy.risk_assessment.selection[0],
            "strategy": strategy.model_dump(mode="json"),
        }
        return build_event(
            ids.strategized_event_id(strategy.correlation_identifier, payload),
            ENGINEERING_STRATEGIZED,
            strategy.correlation_identifier,
            payload,
            self._now(),
        )
