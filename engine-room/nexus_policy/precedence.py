"""Conflict resolution — the deterministic precedence engine (ADR-004 §3.1; contract §6).

When several policies apply to one request the winner is chosen by the fixed order
**Specificity → Priority → Version → Default Policy**. Resolution is *total* and
*deterministic*: policy identity is the final ascending tiebreaker, so an identical
request + applicable set always yields the identical winner even under otherwise-equal
policies. Higher specificity, higher priority, and newer version win.
"""

from __future__ import annotations

from nexus_core.domain.policy import Policy


def version_key(version: str) -> tuple[int, tuple[int, ...] | str]:
    """A total, deterministic order over version strings; newer (greater) wins.

    Numeric dotted versions (``"1"``, ``"1.2"``, ``"1.10"``) order numerically; any
    non-numeric version orders below all numeric ones and then lexicographically — a
    stable fallback, not a semantic-versioning claim.
    """
    parts = version.split(".")
    try:
        return (1, tuple(int(part) for part in parts))
    except ValueError:
        return (0, version)


def resolve(applicable: tuple[tuple[Policy, int], ...]) -> Policy:
    """Pick the winning :class:`Policy` from a non-empty ``(policy, specificity)`` set."""
    best: Policy | None = None
    best_key: tuple[int, int, tuple[int, tuple[int, ...] | str]] | None = None
    for policy, spec in applicable:
        key = (spec, policy.priority, version_key(policy.version))
        if (
            best is None
            or best_key is None
            or key > best_key
            or (key == best_key and policy.identity < best.identity)
        ):
            best, best_key = policy, key
    if best is None:
        raise ValueError("resolve() requires a non-empty applicable set")
    return best
