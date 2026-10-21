"""Intent Resolution — the single constitutional owner of understanding operator intent (Understand).

Given an immutable :class:`~nexus_intent.model.IntentRequest` it **understands** and produces an
:class:`~nexus_intent.model.IntentAnalysis`: the frozen Intent, a Goal when resolved, the emitted
clarification requests, and the confidence assessment. It determines *what* the operator wants; it
never decides *how* — no estimation, no execution reasoning, no runtime/skill choice, no policy, no
orchestration, no execution/validation/recovery/reflection.

The interpreter understands once (`interpreter.py`, the determinism seam) and the engine records
**one** ``intent.resolved`` fact embedding the analysis (INV-17): understand first, emit once, replay
forever. Clarification requests are *emitted* (recorded in the fact), never handled — Human
Interaction is a later program. Persistence rides the P1/ADR-007 substrate.
"""

from __future__ import annotations

from collections.abc import Callable

from nexus_core.domain.event import Event
from nexus_core.events.interfaces import EventEmitter
from nexus_intent import ids
from nexus_intent.events import INTENT_RESOLVED, build_event, system_now
from nexus_intent.interpreter import DeterministicInterpreter, Interpreter
from nexus_intent.model import IntentAnalysis, IntentRequest
from nexus_intent.observability import IntentObservability
from nexus_intent.persistence import IntentRepositories


class IntentResolution:
    """Understands a raw operator request into one immutable, explainable, replayable analysis."""

    def __init__(
        self,
        interpreter: Interpreter | None = None,
        *,
        emitter: EventEmitter | None = None,
        repositories: IntentRepositories | None = None,
        observability: IntentObservability | None = None,
        now: Callable[[], str] | None = None,
    ) -> None:
        self._interpreter: Interpreter = interpreter or DeterministicInterpreter()
        self._emitter = emitter
        self._repos = repositories
        self._obs = observability or IntentObservability()
        self._now = now or system_now

    @property
    def interpreter_version(self) -> str:
        """The version of the interpretation strategy in use (recorded on every analysis — INV-17)."""
        return self._interpreter.version

    def resolve(self, request: IntentRequest, *, persist: bool = True) -> IntentAnalysis:
        """Understand ``request`` into one immutable analysis (identical request → identical analysis)."""
        analysis = self._interpreter.interpret(request, now=self._now())
        if persist:
            self._record(analysis)
        return analysis

    # -- persistence + events ----------------------------------------------- #

    def _record(self, analysis: IntentAnalysis) -> None:
        self._obs.resolved(
            resolved=analysis.resolved,
            confidence=analysis.confidence.level.value,
            clarifications=len(analysis.clarifications),
        )
        if self._repos is not None:
            self._repos.analyses.add(analysis)
        if self._emitter is not None:
            self._emitter.emit(self._resolved_event(analysis))

    def _resolved_event(self, analysis: IntentAnalysis) -> Event:
        payload = {
            "intent": analysis.intent.identity,
            "interpreter_version": analysis.interpreter_version,
            "resolved": analysis.resolved,
            "confidence": analysis.confidence.level.value,
            "clarifications": [c.identity for c in analysis.clarifications],
            "goal": analysis.goal.identity if analysis.goal is not None else None,
            "analysis": analysis.model_dump(mode="json"),
        }
        return build_event(
            ids.resolved_event_id(analysis.correlation_identifier, payload),
            INTENT_RESOLVED,
            analysis.correlation_identifier,
            payload,
            self._now(),
        )
