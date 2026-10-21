"""Recovery vocabularies — the closed enumerations and reference tags of the layer.

Recovery is the deterministic decision layer between Validation and future execution
(doc 19). It **decides continuation** (INV-21) and never acts: it never executes, retries,
restores, or plans work itself — it produces a Recovery Plan that names the governed next
action.

The **decision vocabulary is the program scope**: ``Complete / Retry / Resume / Escalate /
Await Approval / Abort``. These are a subset of doc-19's Recovery Strategies (``Continue /
Retry / Resume / Rollback / Checkpoint Restore / Switch Runtime / Request Context / Human
Review / Abort``); the remaining strategies (Rollback, Switch Runtime, Request Context) and
``Replan`` are reserved for a later program and are **not** implemented here (see
``docs/runtime/recovery/RECOVERY_DECISIONS.md`` for the mapping).

The failure categories and lifecycle stages are doc-19 canon. There is no frozen core
contract for a Recovery Plan — it is a Recovery *output* (the same pattern as the Runtime
Session / Execution Result / Validation Report), so it is a Recovery-layer value object.
Only the closed vocabularies and canonical ``Reference`` ``target_type`` strings live here.
"""

from __future__ import annotations

from enum import StrEnum


class RecoveryDecision(StrEnum):
    """The governed continuation a Recovery Plan selects (program scope; doc 19 subset)."""

    COMPLETE = "complete"
    RETRY = "retry"
    RESUME = "resume"
    ESCALATE = "escalate"
    AWAIT_APPROVAL = "await_approval"
    ABORT = "abort"


class RecoveryStage(StrEnum):
    """The Recovery lifecycle (doc 19 *Recovery State*; the deterministic subset).

    The engine drives the classify -> decide subset and reaches a terminal stage that
    projects the decision. Restoration/retry *execution* stages (``Restoring`` / ``Retrying``
    / ``Recovered``) belong to the actor that performs the action, not the decision layer.
    """

    MONITORING = "monitoring"
    CLASSIFYING = "classifying"
    DECIDING = "deciding"
    COMPLETE = "complete"
    RETRY = "retry"
    RESUME = "resume"
    ESCALATED = "escalated"
    WAITING_APPROVAL = "waiting_approval"
    ABORTED = "aborted"


class FailureCategory(StrEnum):
    """The deterministic classification of what failed (doc 19 *Failure Categories*)."""

    NONE = "none"
    RUNTIME = "runtime"
    RESOURCE = "resource"
    CONTEXT = "context"
    GOVERNANCE = "governance"
    VALIDATION = "validation"
    DEPENDENCY = "dependency"


class RetryPolicyKind(StrEnum):
    """How retries are governed (doc 19 *Retry Policy*; never indefinite)."""

    NEVER = "never"
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    PROGRESSIVE = "progressive"
    RUNTIME_FAILOVER = "runtime_failover"
    HUMAN_ESCALATION = "human_escalation"


class RecoveryRuleOutcome(StrEnum):
    """Whether a recovery rule applies to the situation and proposes its decision."""

    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"


# --- canonical Reference target_type strings ---------------------------------- #
RECOVERY_PLAN_TARGET_TYPE = "recovery_plan"
VALIDATION_REPORT_TARGET_TYPE = "validation_report"
EXECUTION_RESULT_TARGET_TYPE = "execution_result"
CHECKPOINT_TARGET_TYPE = "checkpoint"
