"""``nexus_engineering`` — the constitutional Engineering Intelligence subsystem (P5, the Reason capability).

The **single owner of engineering reasoning** (Constitution Article IV; INV-02). Given immutable,
read-only inputs — a Goal (from Intent Resolution), an Estimation Report (Estimation feeds EI), a
Policy ceiling (the sole evaluator — INV-28), Knowledge, Repository Understanding, Operator
Preferences, and Environment Facts — the :class:`~nexus_engineering.engine.EngineeringIntelligence`
**reasons** and produces exactly one immutable, explainable
:class:`~nexus_engineering.model.EngineeringStrategy`: how the work should proceed.

It reasons; it **never executes** — it plans no work packages, schedules nothing, selects no
runtime, resolves no Skill, evaluates no policy, estimates nothing quantitatively, validates
nothing, recovers nothing, and persists no Knowledge (`engineering/01`, `03`). Every recommendation
is intent-bearing (not instruction-bearing) and self-explaining: reasoning chain, contributing
evidence, assumptions, confidence, and its policy / estimation / knowledge influences (INV-31).

Reasoning passes through the determinism seam (INV-17): the reasoner (pluggable — an LLM reasoner
attaches behind :class:`~nexus_engineering.reasoner.Reasoner`; the default is deterministic) reasons
once, the engine records one ``engineering.strategized`` fact embedding the Strategy, and replay
reconstructs the decision without re-inference. It reuses the P1/P2/P4 substrate and integrates
through additive composition (:func:`build_engineering`).
"""

from __future__ import annotations

from nexus_engineering.composition import (
    EngineeringContext,
    build_engineering,
    signals_from_goal,
)
from nexus_engineering.engine import EngineeringIntelligence
from nexus_engineering.events import ENGINEERING_STRATEGIZED
from nexus_engineering.model import (
    EngineeringStrategy,
    PolicyContext,
    ReasoningInputs,
    Recommendation,
)
from nexus_engineering.observability import EngineeringObservability
from nexus_engineering.persistence import EngineeringRepositories, build_engineering_repositories
from nexus_engineering.reasoner import REASONER_VERSION, DeterministicReasoner, Reasoner
from nexus_engineering.vocabulary import (
    ApproachType,
    AutonomyLevel,
    ExecutionStyle,
    ObservabilityLevel,
    RecoveryPosture,
    RiskLevel,
    ValidationRigor,
    WorkClassification,
)

__version__ = "2.5.0"

__all__ = [
    "ENGINEERING_STRATEGIZED",
    "REASONER_VERSION",
    "ApproachType",
    "AutonomyLevel",
    "DeterministicReasoner",
    "EngineeringContext",
    "EngineeringIntelligence",
    "EngineeringObservability",
    "EngineeringRepositories",
    "EngineeringStrategy",
    "ExecutionStyle",
    "ObservabilityLevel",
    "PolicyContext",
    "Reasoner",
    "ReasoningInputs",
    "Recommendation",
    "RecoveryPosture",
    "RiskLevel",
    "ValidationRigor",
    "WorkClassification",
    "__version__",
    "build_engineering",
    "build_engineering_repositories",
    "signals_from_goal",
]
