"""``nexus_policy`` — the constitutional Policy Engine (P2).

The **single** owner of governance decisions (INV-28): given a
:class:`~nexus_policy.model.DecisionRequest` the :class:`~nexus_policy.engine.PolicyEngine`
returns an immutable :class:`~nexus_policy.model.PolicyEvaluation` from the closed
:class:`~nexus_core.contracts.enums.PolicyDecision` set. It *decides*; it performs no
action (INV-29). Every governed action with no matching policy is denied (INV-30,
fail-closed). Every decision is deterministic, explainable (INV-31), and recorded as a
correlated ``policy.evaluated`` event (INV-39) that replays without re-inference (INV-17).

The engine consumes the frozen ``policy`` contract (``contracts/policy.md`` /
``nexus_core.domain.Policy``) and reuses the Phase 2 / P1 substrate unchanged: durable
persistence (ADR-007) is transparent through :func:`~nexus_policy.composition.build_policy`.
This layer evaluates policy *only* — it never plans, executes, validates, recovers,
orchestrates, or interacts with humans.
"""

from __future__ import annotations

from nexus_policy.composition import PolicyContext, build_policy
from nexus_policy.conditions import MalformedConditionError, matches, specificity
from nexus_policy.defaults import (
    ALLOWED_RUNTIMES,
    AUTONOMOUS_EXECUTION_ACTION_CLASS,
    DEFAULT_POLICY,
    EXECUTION_ACTION_CLASS,
    GLOBAL_COMMAND_BLACKLIST,
    KNOWLEDGE_GROUNDING_ACTION_CLASS,
    REPOSITORY_ACTION_CLASS,
    REQUIRED_RUNTIME_POLICY,
    autonomous_execution_baseline,
    knowledge_grounding_baseline,
    repository_action_baseline,
    v1_seed_policies,
)
from nexus_policy.engine import PolicyEngine
from nexus_policy.events import POLICY_EVALUATED, POLICY_REGISTERED
from nexus_policy.model import DecisionRequest, PolicyEvaluation, PolicyRef
from nexus_policy.observability import PolicyObservability
from nexus_policy.precedence import resolve, version_key
from nexus_policy.registry import InMemoryPolicyRegistry

__version__ = "2.5.0"

__all__ = [
    "ALLOWED_RUNTIMES",
    "AUTONOMOUS_EXECUTION_ACTION_CLASS",
    "DEFAULT_POLICY",
    "EXECUTION_ACTION_CLASS",
    "GLOBAL_COMMAND_BLACKLIST",
    "KNOWLEDGE_GROUNDING_ACTION_CLASS",
    "POLICY_EVALUATED",
    "POLICY_REGISTERED",
    "REPOSITORY_ACTION_CLASS",
    "REQUIRED_RUNTIME_POLICY",
    "DecisionRequest",
    "InMemoryPolicyRegistry",
    "MalformedConditionError",
    "PolicyContext",
    "PolicyEngine",
    "PolicyEvaluation",
    "PolicyObservability",
    "PolicyRef",
    "__version__",
    "autonomous_execution_baseline",
    "build_policy",
    "knowledge_grounding_baseline",
    "matches",
    "repository_action_baseline",
    "resolve",
    "specificity",
    "v1_seed_policies",
    "version_key",
]
