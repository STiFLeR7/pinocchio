"""``nexus_integration`` — the constitutional Integration Substrate (P3).

Reusable migration primitives implementing **Recorded Shadow Adjudication** (ADR-008):
per constitutional owner, a legacy decision, its side-effect-free constitutional shadow,
and their determinism-class-classified diff are recorded as durable, correlated,
append-only ``migration.*`` events (ADR-007/INV-13/INV-39); authority is routed by a
per-owner feature flag (disabled → shadow → canary → enabled) and rolled back per owner
with one atomic flag write.

This layer **coordinates migration only** — it contains no business logic and never plans,
evaluates policy, executes, classifies intent, estimates, orchestrates, validates, or
recovers. It invokes injected ``legacy``/``shadow`` decision callables and records facts.
It depends only on ``nexus_core`` and ``nexus_infra`` (never on an engine), and integrates
through additive composition (:func:`build_integration`).
"""

from __future__ import annotations

from nexus_integration.comparator import (
    Comparator,
    ComparatorRegistry,
    DeterministicComparator,
    ExternalStateComparator,
    ProbabilisticComparator,
    default_comparators,
)
from nexus_integration.composition import IntegrationContext, build_integration
from nexus_integration.coordinator import RollbackCoordinator, ShadowDecisionCoordinator
from nexus_integration.events import (
    MIGRATION_DECISION_DIFF,
    MIGRATION_DECISION_RECORDED,
    MIGRATION_FLAG_SET,
    MIGRATION_SHADOW_DECISION,
)
from nexus_integration.flags import EMPTY_COHORT, CanaryCohort, FlagStore
from nexus_integration.gateway import CorrelationGateway
from nexus_integration.model import (
    AdjudicationResult,
    Authority,
    DecisionDiff,
    DecisionIdentity,
    DeterminismClass,
    DiffVerdict,
    FeatureFlag,
    FlagState,
)
from nexus_integration.observability import MigrationObservability
from nexus_integration.recorder import DecisionRecorder

__version__ = "2.5.0"

__all__ = [
    "EMPTY_COHORT",
    "MIGRATION_DECISION_DIFF",
    "MIGRATION_DECISION_RECORDED",
    "MIGRATION_FLAG_SET",
    "MIGRATION_SHADOW_DECISION",
    "AdjudicationResult",
    "Authority",
    "CanaryCohort",
    "Comparator",
    "ComparatorRegistry",
    "CorrelationGateway",
    "DecisionDiff",
    "DecisionIdentity",
    "DecisionRecorder",
    "DeterminismClass",
    "DeterministicComparator",
    "DiffVerdict",
    "ExternalStateComparator",
    "FeatureFlag",
    "FlagState",
    "FlagStore",
    "IntegrationContext",
    "MigrationObservability",
    "ProbabilisticComparator",
    "RollbackCoordinator",
    "ShadowDecisionCoordinator",
    "__version__",
    "build_integration",
    "default_comparators",
]
