"""``nexus_intent`` — the constitutional Intent Resolution subsystem (P6, the Understand capability).

The **single owner of understanding operator intent** (Constitution capability 1; INV-02). Given a
raw operator request the :class:`~nexus_intent.engine.IntentResolution` engine **understands** and
produces an :class:`~nexus_intent.model.IntentAnalysis`: the frozen
:class:`~nexus_core.domain.intent.Intent` (the one schema for a request / resolved intent — INV-07),
a :class:`~nexus_core.domain.goal.Goal` when resolved, the emitted
:class:`~nexus_intent.model.ClarificationRequest` s, extracted operator preferences, and an
:class:`~nexus_intent.model.IntentConfidence` assessment.

It determines *what* the operator wants; it **never decides how** — no estimation, execution
reasoning, runtime/skill selection, policy evaluation, orchestration, execution, validation,
recovery, or reflection. Ambiguity never silently propagates: below-confidence requests emit
clarification requests and produce **no** Goal ("clarification preferred over incorrect execution").
Clarifications are *emitted*, not handled — Human Interaction is a later program.

Understanding passes through the determinism seam (INV-17): the interpreter (pluggable — an LLM
interpreter attaches behind :class:`~nexus_intent.interpreter.Interpreter`; the default is
deterministic) understands once, the engine records one ``intent.resolved`` fact embedding the
analysis, and replay reconstructs the understanding — including clarifications — without
re-understanding. It reuses the P1 substrate and integrates through additive composition
(:func:`build_intent`).
"""

from __future__ import annotations

from nexus_intent.composition import IntentContext, build_intent
from nexus_intent.engine import IntentResolution
from nexus_intent.events import INTENT_RESOLVED
from nexus_intent.interpreter import INTERPRETER_VERSION, DeterministicInterpreter, Interpreter
from nexus_intent.model import (
    ClarificationKind,
    ClarificationRequest,
    IntentAnalysis,
    IntentConfidence,
    IntentRequest,
    request_from_text,
)
from nexus_intent.observability import IntentObservability
from nexus_intent.persistence import IntentRepositories, build_intent_repositories

__version__ = "2.5.0"

__all__ = [
    "INTENT_RESOLVED",
    "INTERPRETER_VERSION",
    "ClarificationKind",
    "ClarificationRequest",
    "DeterministicInterpreter",
    "IntentAnalysis",
    "IntentConfidence",
    "IntentContext",
    "IntentObservability",
    "IntentRepositories",
    "IntentRequest",
    "IntentResolution",
    "Interpreter",
    "__version__",
    "build_intent",
    "build_intent_repositories",
    "request_from_text",
]
