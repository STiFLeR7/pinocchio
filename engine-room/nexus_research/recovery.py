"""Recovery outlook — the governed continuations the platform offers a failed research stage.

Milestone 5: *inject failures, verify retry / escalation / resume using the existing Recovery
engine*. This module never decides recovery itself — it drives the existing
:class:`~nexus_recovery.engine.RecoveryEngine` under three research-relevant failure conditions
and reports which governed decision the platform reaches:

* **retry** — a fresh failure with retry budget remaining;
* **escalate** — the same failure once the retry budget is exhausted (the safe floor);
* **resume** — partial progress with a valid checkpoint (progress preservation, doc 19).

The conditions are *injected* (attempt count, checkpoint, a partial verdict); the decision is
entirely the existing engine's. The research workflow's live ``fail=True`` path already exercises
the real retry decision end-to-end — this helper makes the escalate/resume continuations
observable for the same failure without waiting for a real multi-attempt run.

Each hypothetical evaluation runs on its **own** isolated event log (a throwaway
:func:`~nexus_recovery.build_recovery` over a fresh infrastructure): these are what-if probes, so
they must neither collide with one another nor pollute the research run's real log.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.contracts.base import Reference
from nexus_execution.results import ExecutionResult
from nexus_infra import InMemoryObservability, build_infrastructure
from nexus_recovery import build_recovery
from nexus_recovery.plan import RecoveryPlan
from nexus_recovery.policy import DEFAULT_RECOVERY_POLICY, RecoveryPolicy
from nexus_validation.report import ValidationReport
from nexus_validation.vocabulary import ValidationDecision, ValidationStage


@dataclass(frozen=True, slots=True)
class RecoveryOutlook:
    """The governed continuation the existing Recovery engine reaches under each condition."""

    on_first_failure: str
    on_exhausted_retries: str
    on_partial_progress: str

    @property
    def covers_all_governed_continuations(self) -> bool:
        """Whether the three canonical continuations were reached (retry/escalate/resume)."""
        return (
            self.on_first_failure == "retry"
            and self.on_exhausted_retries == "escalate"
            and self.on_partial_progress == "resume"
        )


def _recover(
    report: ValidationReport,
    result: ExecutionResult,
    *,
    policy: RecoveryPolicy,
    attempt: int,
    checkpoint_ref: Reference | None = None,
) -> RecoveryPlan:
    """Drive the existing Recovery engine on an isolated log; return its Plan (what-if probe)."""
    infra = build_infrastructure(observability=InMemoryObservability())
    engine = build_recovery(infra).engine
    return engine.recover(
        report, result, policy=policy, attempt=attempt, checkpoint_ref=checkpoint_ref
    )


def recovery_outlook(
    report: ValidationReport,
    result: ExecutionResult,
    *,
    policy: RecoveryPolicy | None = None,
    checkpoint_ref: Reference | None = None,
) -> RecoveryOutlook:
    """Report the existing Recovery engine's decision under three injected failure conditions.

    ``report`` must be a *failed* validation report (a real failed research stage). The helper
    injects only the attempt count, a checkpoint, and — for the resume case — a partial verdict;
    every decision is produced by the unmodified engine.
    """
    resolved = policy or DEFAULT_RECOVERY_POLICY
    ckpt = checkpoint_ref or Reference(
        target_type="checkpoint", identifier=f"ckpt-{report.session_ref.identifier}"
    )

    retry = _recover(report, result, policy=resolved, attempt=1)
    escalate = _recover(report, result, policy=resolved, attempt=resolved.retry.max_attempts)
    partial_report = report.model_copy(
        update={"decision": ValidationDecision.PARTIAL, "stage": ValidationStage.PARTIAL}
    )
    resume = _recover(partial_report, result, policy=resolved, attempt=1, checkpoint_ref=ckpt)

    return RecoveryOutlook(
        on_first_failure=retry.decision.value,
        on_exhausted_retries=escalate.decision.value,
        on_partial_progress=resume.decision.value,
    )
