"""ADR-008 §9 entry gate — comparison proven on one deterministic and one probabilistic owner.

Deterministic owner (Policy): the real ``nexus_policy`` engine shadows a v1-style verdict;
exact-match works and the shadow is side-effect-free. Probabilistic owner (intent): an
equivalence band avoids a false-mismatch storm on token-level differences.
"""

from __future__ import annotations

import pytest

from nexus_infra import build_infrastructure
from nexus_integration import (
    DecisionIdentity,
    DeterminismClass,
    DiffVerdict,
    FlagState,
    ProbabilisticComparator,
    build_integration,
)
from tests.unit.nexus_integration.fixtures import (
    INTENT_OWNER,
    POLICY_OWNER,
    constitutional_policy_engine,
    intent_equivalence,
    policy_decision_pair,
)

_NOW = "2026-01-01T00:00:00Z"


@pytest.mark.parametrize(
    ("runtime", "command", "runtime_policy", "expected"),
    [
        ("claude", "pytest -q", "approved", "allow"),
        ("evil", "ls", "approved", "deny"),
        ("claude", "sudo rm x", "approved", "deny"),
        ("claude", "ls", "pending", "deny"),
    ],
)
def test_policy_owner_deterministic_shadow_matches_v1(
    runtime, command, runtime_policy, expected
) -> None:
    infra = build_infrastructure()
    ctx = build_integration(infra, now=lambda: _NOW)
    ctx.flags.set(POLICY_OWNER, FlagState.SHADOW)
    engine = constitutional_policy_engine()
    legacy, shadow = policy_decision_pair(
        engine, runtime=runtime, command=command, runtime_policy=runtime_policy
    )

    result = ctx.coordinator.adjudicate(
        DecisionIdentity(
            owner=POLICY_OWNER,
            decision_id=f"{runtime}-{runtime_policy}",
            correlation_identifier="cor",
        ),
        legacy=legacy,
        shadow=shadow,
        determinism_class=DeterminismClass.DETERMINISTIC,
    )
    assert result.legacy_value == expected
    assert result.shadow_value == expected
    assert result.diff.verdict is DiffVerdict.MATCH  # v2 engine exactly reproduces v1's verdict


def test_policy_shadow_is_side_effect_free() -> None:
    infra = build_infrastructure()
    ctx = build_integration(infra, now=lambda: _NOW)
    ctx.flags.set(POLICY_OWNER, FlagState.SHADOW)
    engine = constitutional_policy_engine()
    legacy, shadow = policy_decision_pair(
        engine, runtime="claude", command="ls", runtime_policy="approved"
    )

    ctx.coordinator.adjudicate(
        DecisionIdentity(owner=POLICY_OWNER, decision_id="d", correlation_identifier="cor-p"),
        legacy=legacy,
        shadow=shadow,
        determinism_class=DeterminismClass.DETERMINISTIC,
    )
    under_correlation = [
        e for e in infra.event_store.read_all() if e.correlation_identifier == "cor-p"
    ]
    # The policy engine used as shadow has no emitter, and the substrate emits only migration.*.
    assert under_correlation and all(e.type.startswith("migration.") for e in under_correlation)


def test_intent_owner_probabilistic_no_false_mismatch() -> None:
    ctx = build_integration(build_infrastructure(), now=lambda: _NOW)
    ctx.flags.set(INTENT_OWNER, FlagState.SHADOW)
    band = ProbabilisticComparator(equivalence=intent_equivalence)

    # v1 says "code"; v2 says "software" — token-different but semantically equivalent.
    result = ctx.coordinator.adjudicate(
        DecisionIdentity(owner=INTENT_OWNER, decision_id="i1", correlation_identifier="cor-i"),
        legacy=lambda: "code",
        shadow=lambda: "software",
        determinism_class=DeterminismClass.PROBABILISTIC,
        comparator=band,
    )
    assert result.diff.verdict is DiffVerdict.EQUIVALENT  # not a false MISMATCH


def test_intent_owner_real_divergence_is_flagged() -> None:
    ctx = build_integration(build_infrastructure(), now=lambda: _NOW)
    ctx.flags.set(INTENT_OWNER, FlagState.SHADOW)
    band = ProbabilisticComparator(equivalence=intent_equivalence)
    result = ctx.coordinator.adjudicate(
        DecisionIdentity(owner=INTENT_OWNER, decision_id="i2", correlation_identifier="cor-i2"),
        legacy=lambda: "software",
        shadow=lambda: "research",
        determinism_class=DeterminismClass.PROBABILISTIC,
        comparator=band,
    )
    assert result.diff.verdict is DiffVerdict.MISMATCH  # injected divergence caught
