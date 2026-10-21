"""``nexus_recovery`` — the Recovery Engine (deterministic governed continuation).

Recovery is the decision layer between Validation and future execution (doc 19). It consumes a
:class:`~nexus_validation.report.ValidationReport` and the
:class:`~nexus_execution.results.ExecutionResult` it judged, classifies the failure, applies
deterministic policy-driven rules, and produces an immutable **Recovery Plan** that names the
governed next action::

    Validation Report + Execution Result → Recovery Engine → Recovery Plan

It **decides continuation** (INV-21) and never acts: it never executes, retries, restores,
fails over, plans, mutates Validation, or invokes AI (doc 19 boundaries; INV-22). Dependency
direction: ``nexus_recovery → {nexus_validation, nexus_execution, nexus_runtime, nexus_core,
nexus_infra}`` — it consumes validation/execution output downstream and reuses the Phase 2
substrate without modifying it. The decision vocabulary is the program scope:
**Complete / Retry / Resume / Escalate / Await Approval / Abort** (Replan is reserved for a
later program).
"""

from __future__ import annotations

from nexus_recovery.classification import FailureClassifier, FailureSignal
from nexus_recovery.composition import RecoveryContextBundle, build_recovery
from nexus_recovery.engine import RecoveryEngine
from nexus_recovery.evaluator import RecoveryDetermination, RecoveryEvaluator
from nexus_recovery.observability import RecoveryObservability
from nexus_recovery.persistence import RecoveryRepositories, build_recovery_repositories
from nexus_recovery.plan import RecoveryPlan, RecoveryRuleResult
from nexus_recovery.policy import (
    DEFAULT_RECOVERY_POLICY,
    RETRYABLE_CATEGORIES,
    RecoveryPolicy,
    RetryPolicy,
)
from nexus_recovery.rules import (
    DECISION_PRECEDENCE,
    DEFAULT_RULES,
    AbortRule,
    ApprovalRule,
    CompletionRule,
    EscalationRule,
    RecoveryContext,
    RecoveryRule,
    ResumeRule,
    RetryRule,
)
from nexus_recovery.vocabulary import (
    FailureCategory,
    RecoveryDecision,
    RecoveryRuleOutcome,
    RecoveryStage,
    RetryPolicyKind,
)

__version__ = "2.5.0"

__all__ = [
    "DECISION_PRECEDENCE",
    "DEFAULT_RECOVERY_POLICY",
    "DEFAULT_RULES",
    "RETRYABLE_CATEGORIES",
    "AbortRule",
    "ApprovalRule",
    "CompletionRule",
    "EscalationRule",
    "FailureCategory",
    "FailureClassifier",
    "FailureSignal",
    "RecoveryContext",
    "RecoveryContextBundle",
    "RecoveryDecision",
    "RecoveryDetermination",
    "RecoveryEngine",
    "RecoveryEvaluator",
    "RecoveryObservability",
    "RecoveryPlan",
    "RecoveryPolicy",
    "RecoveryRepositories",
    "RecoveryRule",
    "RecoveryRuleOutcome",
    "RecoveryRuleResult",
    "RecoveryStage",
    "ResumeRule",
    "RetryPolicy",
    "RetryPolicyKind",
    "RetryRule",
    "build_recovery",
    "build_recovery_repositories",
]
