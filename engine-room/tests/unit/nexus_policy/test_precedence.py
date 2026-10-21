"""Deterministic conflict resolution (``nexus_policy.precedence``).

Proves the fixed order Specificity → Priority → Version → (identity, total tiebreak),
and that ``version_key`` orders numeric dotted versions numerically (newer wins).
"""

from __future__ import annotations

from nexus_core.contracts.enums import PolicyDecision
from nexus_core.domain.policy import Policy
from nexus_policy.precedence import resolve, version_key


def _p(
    identity: str, *, priority: int = 0, version: str = "1", specificity: int = 0
) -> tuple[Policy, int]:
    policy = Policy(
        identity=identity,
        version=version,
        purpose="test",
        conditions={},
        decision=PolicyDecision.ALLOW,
        priority=priority,
        owner="governance",
    )
    return (policy, specificity)


def test_specificity_dominates() -> None:
    winner = resolve((_p("a", priority=999, specificity=1), _p("b", priority=0, specificity=2)))
    assert winner.identity == "b"  # higher specificity beats higher priority


def test_priority_breaks_specificity_tie() -> None:
    winner = resolve((_p("a", priority=10, specificity=2), _p("b", priority=50, specificity=2)))
    assert winner.identity == "b"


def test_version_breaks_priority_tie() -> None:
    winner = resolve(
        (
            _p("a", priority=5, version="1", specificity=2),
            _p("b", priority=5, version="2", specificity=2),
        )
    )
    assert winner.identity == "b"  # newer version wins


def test_identity_is_total_final_tiebreak() -> None:
    # Fully equal on specificity, priority, version → smallest identity wins (deterministic).
    winner = resolve((_p("zzz", specificity=1), _p("aaa", specificity=1)))
    assert winner.identity == "aaa"


def test_version_key_orders_numerically() -> None:
    assert version_key("2") > version_key("1")
    assert version_key("1.10") > version_key("1.9")  # not lexicographic
    assert version_key("1.2.3") > version_key("1.2")


def test_version_key_non_numeric_sorts_below_numeric() -> None:
    assert version_key("1") > version_key("draft")
    assert version_key("draft-b") > version_key("draft-a")
