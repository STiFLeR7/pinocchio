"""Execution Strategy — declares *how* work is coordinated and governed.

Contract: ``contracts/execution_strategy.md``. Produced by Planning. Binding:
ADR-004 (the single approval taxonomy; policy/validation/recovery precedence;
declaration ≠ evaluation), ADR-001 (state is projection). Invariants: INV-05 (the
Strategy declares coordination behavior and never executes; Orchestration enacts
it and never invents coordination not declared here), INV-07, INV-13/14/15.

The Strategy is runtime-, provider-, and transport-agnostic: ``runtime_policy``
is capability-based and never names a runtime implementation (ADR-002 / INV-37).
It declares policy; it never evaluates it.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from nexus_core.contracts.base import Correlation, DomainObject, Struct
from nexus_core.contracts.enums import (
    ApprovalTaxonomy,
    CoordinationModel,
    RecoveryBehavior,
    RetryBehavior,
)
from nexus_core.contracts.status import ExecutionStrategyStatus


class ExecutionStrategy(DomainObject):
    """Declarative coordination/governance policy (contract: execution_strategy.md)."""

    LIFECYCLE_NAME: ClassVar[str] = "execution_strategy"

    # --- required ---------------------------------------------------------- #
    identity: str = Field(min_length=1)
    """Stable unique id; participates in correlation/trace lineage."""
    coordination: CoordinationModel
    """The coordination model; declares ordering/concurrency intent, Orchestration enacts it."""
    runtime_policy: Struct
    """Capability-based runtime requirements/preferences/restrictions; never names a runtime (ADR-002)."""
    approval_policy: ApprovalTaxonomy
    """Required approval level using the single platform taxonomy (ADR-004 §3.3)."""
    retry_policy: RetryBehavior
    """Declarative retry behavior; declares intent, Recovery selects the actual strategy (ADR-004 §3.2)."""
    timeout_policy: Struct
    """Maximum execution / waiting / retry durations; timeout elapse is a recoverable failure."""
    validation_policy: Struct
    """Declares required Evidence, validators, and completion conditions; the verdict is Validation's."""
    recovery_policy: Struct
    """Declarative recovery behavior with deterministic selection rules; Recovery owns selection (INV-22)."""
    checkpoint_policy: Struct
    """Checkpoint frequency, required checkpoints, and recovery checkpoints (INV-18)."""

    # --- optional ---------------------------------------------------------- #
    status: ExecutionStrategyStatus | None = None
    """Current lifecycle state — a projection of the event log (ADR-001); optional until projected."""
    recovery_options: tuple[RecoveryBehavior, ...] = ()
    """Declared recovery options shared with Recovery selection; Recovery owns selection (INV-22)."""
    escalation_policy: Struct | None = None
    """How and to whom unresolved conditions escalate."""
    expected_behavior: Struct | None = None
    """Declared assumptions/coordination description Supervision evaluates execution against."""
    cost_policy: Struct | None = None
    """Declarative cost bounds / cost-awareness inputs."""
    skill_overrides: Struct | None = None
    """Where this Strategy intentionally overrides a Skill's default guidance (ADR-004 §3.4)."""
    correlation: Correlation | None = None
    """Correlation/trace identifiers tying the Strategy to its Plan/Goal lineage."""
    version: str | None = None
    """Strategy version for supersession tracking."""
