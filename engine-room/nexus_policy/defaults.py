"""Default Policy and the v1 seed policy set — the policy "loader".

The **Default Policy** is the permanent, platform-level fail-closed rule (INV-30):
any *governed* action with no matching policy is denied. It is never weakened to
allow-by-default for governed actions (contract §8 *Default Policy is permanent*).

The **seed set** migrates Nexus v1's static governance defaults into structured,
data-driven policies (ADR-004 §9: "that table is the seed Policy set; migrate each
entry to a structured Policy"). The v1 values are transcribed here with provenance —
v2 never imports the v1 (``nexus``) package. Source of the values:
``nexus/core/policy_defaults.py`` (``ALLOWED_RUNTIMES``, ``GLOBAL_COMMAND_BLACKLIST``,
``REQUIRED_RUNTIME_POLICY``) enforced by ``nexus/execution/governance.py``.

**Verdict parity.** For the governed ``execution`` action class the seed set
reproduces v1's decision: allow when the runtime is approved, the runtime policy is
``approved``, and the command is not blacklisted; deny on any violation (v1 raised
``RepositoryGovernanceError`` — i.e. deny — on each of those checks).
"""

from __future__ import annotations

from nexus_core.contracts.enums import PolicyCategory, PolicyDecision
from nexus_core.contracts.status import PolicyStatus
from nexus_core.domain.policy import Policy

EXECUTION_ACTION_CLASS = "execution"
KNOWLEDGE_GROUNDING_ACTION_CLASS = "knowledge_grounding"
AUTONOMOUS_EXECUTION_ACTION_CLASS = "autonomous_execution"
REPOSITORY_ACTION_CLASS = "repository_action"

# --- transcribed from nexus/core/policy_defaults.py (v1), ADR-004 §9 ----------- #
ALLOWED_RUNTIMES: tuple[str, ...] = ("gemini", "claude", "nexus", "hermes")
GLOBAL_COMMAND_BLACKLIST: tuple[str, ...] = ("rm -rf /", "sudo ", "mv /etc", ":(){ :|:& };:")
REQUIRED_RUNTIME_POLICY = "approved"

_GOVERNANCE = "governance"
_IS_EXECUTION = {"attr": "action_class", "op": "eq", "value": EXECUTION_ACTION_CLASS}

# The fail-closed catch-all (INV-30). Priority is far below any real policy so that, were
# it ever placed in an evaluated set, any specific policy outranks it; the engine uses it
# only as the explicit fallback when no enabled policy matches a governed request.
DEFAULT_POLICY = Policy(
    identity="policy.default",
    version="1",
    purpose="Fail-closed default: deny any governed action with no matching policy (INV-30).",
    conditions={},
    decision=PolicyDecision.DENY,
    priority=-1_000_000,
    owner=_GOVERNANCE,
    status=PolicyStatus.ENABLED,
    category=PolicyCategory.GOVERNANCE,
)


def knowledge_grounding_baseline() -> Policy:
    """The overridable allow-baseline governing Knowledge grounding (P14 learning loop).

    Grounding prior Knowledge onto a future execution is a *governed* action class (INV-30 leans
    governed); this baseline permits it so the learning loop is on by default, while any
    higher-specificity deny policy filters it out per goal/subject. It mirrors
    ``policy.execution.allow-baseline`` — a data-only governance default the consuming learning
    integration *registers* and *queries*; only this engine ever evaluates it (INV-28).
    """
    return Policy(
        identity="policy.knowledge.allow-grounding-baseline",
        version="1",
        purpose="Allow a governed knowledge-grounding action when no deny policy applies.",
        conditions={
            "attr": "action_class",
            "op": "eq",
            "value": KNOWLEDGE_GROUNDING_ACTION_CLASS,
        },
        decision=PolicyDecision.ALLOW,
        priority=0,
        owner=_GOVERNANCE,
        status=PolicyStatus.ENABLED,
        category=PolicyCategory.GOVERNANCE,
        governed_action_class=KNOWLEDGE_GROUNDING_ACTION_CLASS,
    )


def autonomous_execution_baseline() -> Policy:
    """The overridable allow-baseline governing autonomous (scheduled) execution (P16 autonomy).

    Starting a constitutional execution *autonomously* — a Scheduler dispatch with no human in the loop —
    is a *governed* action class: this baseline permits it so governed autonomy is available by default,
    while any higher-specificity deny policy withholds it (per mode / schedule / domain). It mirrors
    ``policy.execution.allow-baseline`` — a data-only governance default the autonomy coordinator
    *registers* and *queries*; only this engine ever evaluates it (INV-28), and autonomy stays fail-closed
    (INV-30) when a deny applies.
    """
    return Policy(
        identity="policy.autonomy.allow-autonomous-baseline",
        version="1",
        purpose="Allow a governed autonomous-execution action when no deny policy applies.",
        conditions={
            "attr": "action_class",
            "op": "eq",
            "value": AUTONOMOUS_EXECUTION_ACTION_CLASS,
        },
        decision=PolicyDecision.ALLOW,
        priority=0,
        owner=_GOVERNANCE,
        status=PolicyStatus.ENABLED,
        category=PolicyCategory.GOVERNANCE,
        governed_action_class=AUTONOMOUS_EXECUTION_ACTION_CLASS,
    )


def repository_action_baseline() -> Policy:
    """Allow the explicit first-party action class; individual denials remain overridable."""
    return Policy(
        identity="policy.repository_action.allow-baseline",
        version="1",
        purpose="Allow only explicitly submitted first-party repository actions unless a specific denial applies.",
        conditions={"attr": "action_class", "op": "eq", "value": REPOSITORY_ACTION_CLASS},
        decision=PolicyDecision.ALLOW,
        priority=0,
        owner=_GOVERNANCE,
        status=PolicyStatus.ENABLED,
        category=PolicyCategory.GOVERNANCE,
        governed_action_class=REPOSITORY_ACTION_CLASS,
    )


def v1_seed_policies() -> tuple[Policy, ...]:
    """The structured policies migrated from v1's governance defaults (ADR-004 §9)."""
    return (
        Policy(
            identity="policy.execution.allow-baseline",
            version="1",
            purpose="Allow a governed execution action when no violation policy applies.",
            conditions=_IS_EXECUTION,
            decision=PolicyDecision.ALLOW,
            priority=0,
            owner=_GOVERNANCE,
            status=PolicyStatus.ENABLED,
            category=PolicyCategory.EXECUTION,
            governed_action_class=EXECUTION_ACTION_CLASS,
        ),
        Policy(
            identity="policy.execution.deny-unapproved-runtime",
            version="1",
            purpose="Deny execution on a runtime outside the platform allow-list (v1 allowed_runtimes).",
            conditions={
                "all": [
                    _IS_EXECUTION,
                    {"attr": "runtime", "op": "not_in", "value": list(ALLOWED_RUNTIMES)},
                ]
            },
            decision=PolicyDecision.DENY,
            priority=100,
            owner=_GOVERNANCE,
            status=PolicyStatus.ENABLED,
            category=PolicyCategory.EXECUTION,
            governed_action_class=EXECUTION_ACTION_CLASS,
        ),
        Policy(
            identity="policy.execution.deny-blacklisted-command",
            version="1",
            purpose="Deny execution whose command contains a globally blacklisted pattern (v1 blacklist).",
            conditions={
                "all": [
                    _IS_EXECUTION,
                    {
                        "attr": "command",
                        "op": "contains_any",
                        "value": list(GLOBAL_COMMAND_BLACKLIST),
                    },
                ]
            },
            decision=PolicyDecision.DENY,
            priority=100,
            owner=_GOVERNANCE,
            status=PolicyStatus.ENABLED,
            category=PolicyCategory.EXECUTION,
            governed_action_class=EXECUTION_ACTION_CLASS,
        ),
        Policy(
            identity="policy.execution.deny-unapproved-runtime-policy",
            version="1",
            purpose="Deny execution whose runtime policy is not 'approved' (v1 required_runtime_policy).",
            conditions={
                "all": [
                    _IS_EXECUTION,
                    {"attr": "runtime_policy", "op": "ne", "value": REQUIRED_RUNTIME_POLICY},
                ]
            },
            decision=PolicyDecision.DENY,
            priority=100,
            owner=_GOVERNANCE,
            status=PolicyStatus.ENABLED,
            category=PolicyCategory.EXECUTION,
            governed_action_class=EXECUTION_ACTION_CLASS,
        ),
    )
