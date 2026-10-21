"""``nexus_validation`` — the Validation Engine (evidence-driven governance after execution).

Validation **judges** whether an execution achieved its objective, using deterministic
evidence alone (doc 14; INV-20 — never the runtime's self-report). It consumes an
:class:`~nexus_execution.results.ExecutionResult` and the runtime event log, collects
immutable **Evidence** (INV-12), evaluates deterministic **rules**, and produces an
immutable **Validation Report** that *references* Evidence by id::

    Execution Engine → Execution Result → Validation Engine → Evidence → Validation Report

It never executes, retries, recovers, plans, mutates artifacts, or invokes AI (doc 14
boundaries). Dependency direction:
``nexus_validation → {nexus_execution, nexus_core, nexus_infra}`` — it consumes execution
output downstream and reuses the Phase 2 substrate without modifying it. The decision
vocabulary is doc-14 canon: **Passed / Failed / Partial / Requires Review**.
"""

from __future__ import annotations

from nexus_validation.collector import (
    ArtifactInspector,
    EvidenceCollector,
    MetadataCollector,
    OutputCollector,
)
from nexus_validation.composition import ValidationContext, build_validation
from nexus_validation.engine import ValidationEngine
from nexus_validation.evaluator import Decision, DecisionEvaluator
from nexus_validation.evidence import Evidence
from nexus_validation.observability import ValidationObservability
from nexus_validation.persistence import ValidationRepositories, build_validation_repositories
from nexus_validation.report import RuleResult, ValidationReport
from nexus_validation.rules import (
    DEFAULT_RULES,
    ArtifactCorroborationRule,
    CompletionCriteriaRule,
    ErrorAbsenceRule,
    ExitStatusRule,
    ProcessOutcomeRule,
    RuleContext,
    ValidationPolicy,
    ValidationRule,
)
from nexus_validation.vocabulary import (
    EvidenceSource,
    RuleOutcome,
    ValidationDecision,
    ValidationStage,
)

__version__ = "2.5.0"

__all__ = [
    "DEFAULT_RULES",
    "ArtifactCorroborationRule",
    "ArtifactInspector",
    "CompletionCriteriaRule",
    "Decision",
    "DecisionEvaluator",
    "ErrorAbsenceRule",
    "Evidence",
    "EvidenceCollector",
    "EvidenceSource",
    "ExitStatusRule",
    "MetadataCollector",
    "OutputCollector",
    "ProcessOutcomeRule",
    "RuleContext",
    "RuleOutcome",
    "RuleResult",
    "ValidationContext",
    "ValidationDecision",
    "ValidationEngine",
    "ValidationObservability",
    "ValidationPolicy",
    "ValidationReport",
    "ValidationRepositories",
    "ValidationRule",
    "ValidationStage",
    "build_validation",
    "build_validation_repositories",
]
