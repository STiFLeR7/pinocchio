"""03 - Policy Governance: one decision, evaluated twice, two different verdicts.

Demonstrates the Policy Engine standalone - the single, fail-closed governance owner every
other subsystem consults before acting (INV-30: an action with no matching policy is denied,
never allowed). Uses the platform's own seeded default policies (migrated from Nexus v1's
static governance table, ADR-004 SS9) rather than inventing a new rule.

See README.md in this directory for the full walkthrough.
"""

from __future__ import annotations

import sys

from nexus_infra import build_infrastructure
from nexus_policy import EXECUTION_ACTION_CLASS, DecisionRequest, build_policy


def main() -> None:
    sys.stdout.reconfigure(
        encoding="utf-8"
    )  # policy reasoning traces may include Unicode (e.g. "->")
    infra = build_infrastructure()
    policy = build_policy(infra)  # seed=True by default: registers the v1-migrated defaults

    # A governed "execution" request with an approved runtime and an ordinary command.
    allowed = policy.engine.evaluate(
        DecisionRequest(
            action_class=EXECUTION_ACTION_CLASS,
            correlation_identifier="cor-allowed-example",
            attributes={
                "runtime": "claude",
                "runtime_policy": "approved",
                "command": "pytest tests/unit",
            },
        )
    )

    # The same action class, but the command matches the global blacklist (ADR-004 SS9).
    denied = policy.engine.evaluate(
        DecisionRequest(
            action_class=EXECUTION_ACTION_CLASS,
            correlation_identifier="cor-denied-example",
            attributes={
                "runtime": "claude",
                "runtime_policy": "approved",
                "command": "rm -rf /",
            },
        )
    )

    for label, evaluation in (("ALLOWED command", allowed), ("BLACKLISTED command", denied)):
        print(f"-- {label} --")
        print(f"  decision:          {evaluation.decision.value}")
        print(f"  matched policy:    {evaluation.matched_policy}")
        print(f"  default applied:   {evaluation.default_applied}")
        print(f"  reasoning:         {evaluation.reasoning_trace}")
        print()


if __name__ == "__main__":
    main()
