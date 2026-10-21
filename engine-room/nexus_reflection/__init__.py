"""``nexus_reflection`` — the Reflection Engine (deterministic operational insight).

Reflection is the **analytical layer** over completed operational history (doc 26). It consumes
the immutable outputs of the pipeline — Execution Results, Validation Reports, Recovery Plans,
runtime events, and metrics — correlates them into operational episodes, runs deterministic
analyzers, and produces an immutable **Reflection Report** with detected patterns and advisory
Knowledge *Candidates*::

    Execution Results + Validation Reports + Recovery Plans → Reflection Engine → Reflection Report

It **explains** behaviour and never changes it: it never executes, retries, plans, mutates
policy, updates Knowledge, or invokes AI (doc 26 boundaries; INV-25 — it produces Knowledge
*Candidates*, never persistent Knowledge; INV-26 — Planning never depends directly on it).
Dependency direction: ``nexus_reflection → {nexus_recovery, nexus_validation, nexus_execution,
nexus_runtime, nexus_core, nexus_infra}`` — strictly downstream; it reuses the Phase 2 substrate
without modifying it. Confidence is doc-26 canon (Experimental / Observed / Validated / Proven),
derived deterministically from repetition count.
"""

from __future__ import annotations

from nexus_reflection.analyzers import (
    DEFAULT_ANALYZERS,
    AnalysisContext,
    BottleneckAnalyzer,
    ExecutionDurationAnalyzer,
    OperationalAnalyzer,
    RecoveryDecisionAnalyzer,
    RepeatedFailureAnalyzer,
    RepeatedSuccessAnalyzer,
    RetryFrequencyAnalyzer,
    RuntimeUtilizationAnalyzer,
    ValidationOutcomeAnalyzer,
)
from nexus_reflection.collector import OperationalHistory, ReflectionCollector
from nexus_reflection.composition import ReflectionContextBundle, build_reflection
from nexus_reflection.engine import ReflectionEngine
from nexus_reflection.episode import OperationalEpisode
from nexus_reflection.observability import ReflectionObservability
from nexus_reflection.patterns import (
    KnowledgeCandidate,
    OperationalPattern,
    confidence_for,
)
from nexus_reflection.persistence import ReflectionRepositories, build_reflection_repositories
from nexus_reflection.report import ReflectionReport
from nexus_reflection.synthesis import ReflectionInsight, ReflectionSynthesizer
from nexus_reflection.vocabulary import (
    ConfidenceLevel,
    PatternKind,
    ReflectionStage,
)

__version__ = "2.5.0"

__all__ = [
    "DEFAULT_ANALYZERS",
    "AnalysisContext",
    "BottleneckAnalyzer",
    "ConfidenceLevel",
    "ExecutionDurationAnalyzer",
    "KnowledgeCandidate",
    "OperationalAnalyzer",
    "OperationalEpisode",
    "OperationalHistory",
    "OperationalPattern",
    "PatternKind",
    "RecoveryDecisionAnalyzer",
    "ReflectionCollector",
    "ReflectionContextBundle",
    "ReflectionEngine",
    "ReflectionInsight",
    "ReflectionObservability",
    "ReflectionReport",
    "ReflectionRepositories",
    "ReflectionStage",
    "ReflectionSynthesizer",
    "RepeatedFailureAnalyzer",
    "RepeatedSuccessAnalyzer",
    "RetryFrequencyAnalyzer",
    "RuntimeUtilizationAnalyzer",
    "ValidationOutcomeAnalyzer",
    "build_reflection",
    "build_reflection_repositories",
    "confidence_for",
]
