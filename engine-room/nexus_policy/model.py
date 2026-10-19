"""Policy Engine value objects — the deterministic decision model.

A :class:`DecisionRequest` is the immutable *input* to evaluation (the named
operational attributes a policy's condition tree is matched against); a
:class:`PolicyEvaluation` is the immutable, explainable *output* (INV-31): the
decision, the exact policy that won, the full applicable set, and the reasoning
trace. Both are pure values — the Policy Engine performs no action (INV-29); it is
*queried* with a request and *returns* an evaluation.

These are Policy-Engine value objects, not frozen core contracts: ``Policy`` itself
is the frozen contract (``contracts/policy.md``); the request/result model how the
engine (doc 20 *Policy Evaluation*) is queried and what it yields.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from nexus_core.contracts.base import Struct
from nexus_core.contracts.enums import ApprovalTaxonomy, PolicyDecision


@dataclass(frozen=True, slots=True)
class PolicyRef:
    """A by-(identity, version) pointer to the exact Policy evaluated (replayable, INV-17)."""

    identity: str
    version: str


@dataclass(frozen=True, slots=True)
class DecisionRequest:
    """A query to the Policy Engine: "is this action allowed?" (doc 20 *Policy Evaluation*).

    ``attributes`` are the named operational attributes (``risk_level``, ``domain``,
    ``runtime``, ``command``, ``cost_estimate``, ``actor`` …) the condition trees match
    against. ``action_class`` names the class of governed action and is exposed to
    condition trees as the ``action_class`` attribute. ``governed`` is ``True`` by
    default — fail-closed leans governed (INV-30); only an *explicitly* ungoverned
    action class is allow-by-default. ``correlation_identifier`` ties the resulting
    decision event to its operation (INV-39).
    """

    action_class: str
    correlation_identifier: str
    attributes: Mapping[str, Any] = field(default_factory=dict)
    governed: bool = True

    def evaluation_view(self) -> dict[str, Any]:
        """The attribute space the condition trees see (``attributes`` + ``action_class``)."""
        return {**self.attributes, "action_class": self.action_class}


@dataclass(frozen=True, slots=True)
class PolicyEvaluation:
    """The immutable, explainable result of one evaluation (INV-31; doc 20 *Explainable*)."""

    decision: PolicyDecision
    action_class: str
    correlation_identifier: str
    governed: bool
    default_applied: bool
    specificity: int
    matched_policy: PolicyRef | None
    applicable_policies: tuple[PolicyRef, ...]
    reasoning_trace: tuple[str, ...]
    request_attributes: Struct
    approval_requirement: ApprovalTaxonomy | None = None
    constraints: Struct | None = None

    @property
    def allowed(self) -> bool:
        """Whether the decision is an outright ``Allow``."""
        return self.decision is PolicyDecision.ALLOW
