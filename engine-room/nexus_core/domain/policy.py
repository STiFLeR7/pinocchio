"""Policy — a versioned, data-driven declarative governance rule.

Contract: ``contracts/policy.md``. Owned by Governance; evaluated by the Policy
Engine. Binding: ADR-004 (policy engine & governance), ADR-001 (event-sourced
state). Invariants: ADR-004 §3.1 (``conditions`` is a structured condition tree
expressed as DATA — typed predicates over named operational attributes, never an
embedded DSL or Turing-complete language); the decision set is closed to exactly
{Allow, Deny, RequireApproval, Delay, Escalate, RequestInformation} — recovery
strategies (Retry / Rollback / Abort) are NEVER Policy Decisions (ADR-004 §3.2);
INV-28 (Policies are evaluated only by the Policy Engine; no subsystem hardcodes
governance rules); INV-30 (fail-closed: when no policy matches a governed action,
the Default Policy denies); deterministic conflict resolution by the fixed order
Specificity → Priority → Version → Default Policy; INV-13/14/15, INV-17, INV-31.

The ``status`` field is the lifecycle status (a projection of the event log),
optional until projected.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from nexus_core.contracts.base import DomainObject, Reference, Struct
from nexus_core.contracts.enums import ApprovalTaxonomy, PolicyCategory, PolicyDecision
from nexus_core.contracts.status import PolicyStatus


class Policy(DomainObject):
    """A data-driven governance rule (contract: policy.md). Evaluated, never self-executing."""

    LIFECYCLE_NAME: ClassVar[str] = "policy"

    # --- required ---------------------------------------------------------- #
    identity: str = Field(min_length=1)
    """Stable, unique identifier, distinct from ``version``; addressable and replayable for life."""
    version: str = Field(min_length=1)
    """Version of this Policy; with ``identity`` it uniquely identifies the exact rule evaluated."""
    purpose: str = Field(min_length=1)
    """The operational intent: what boundary it enforces and why (supports explainability)."""
    conditions: Struct
    """Structured condition tree of typed predicates over named attributes — DATA, not code (§3.1)."""
    decision: PolicyDecision
    """The governance outcome when conditions match; closed set — recovery strategies excluded (§3.2)."""
    priority: int
    """Deterministic tiebreaker applied after specificity when applicable policies are equally specific."""
    owner: str = Field(min_length=1)
    """The authority/domain accountable for this policy; used for audit and change authority."""

    # --- optional ---------------------------------------------------------- #
    status: PolicyStatus | None = None
    """Current lifecycle state — a projection of the event log (ADR-001); optional until projected."""
    constraints: Struct | None = None
    """Bounded operational limits asserted when the policy applies; declarative, never executed."""
    approval_requirement: ApprovalTaxonomy | None = None
    """Required approval level (single platform taxonomy) when ``decision`` is RequireApproval (§3.3)."""
    category: PolicyCategory | None = None
    """The policy's domain classification (Governance / Execution / Planning / Validation / Recovery)."""
    governed_action_class: str | None = None
    """The class of action governed; absent/ungoverned classes are allow-by-default (§3.1)."""
    exceptions: Struct | None = None
    """Declared carve-outs to the policy, expressed as data and recorded for explainability."""
    dependencies: tuple[Reference, ...] = ()
    """References to other policies this policy composes with for complex decisions."""
    audit_requirements: Struct | None = None
    """What an evaluation of this policy must record beyond the platform default."""
    rationale: str | None = None
    """Author-supplied explanation of the rule's reasoning, recorded for change review."""
    metadata: Struct | None = None
    """Non-behavioral descriptive attributes (tags, ownership notes) that do not affect evaluation."""
    effective_window: Struct | None = None
    """Optional validity window (logical, not provider state) during which the policy is eligible."""
