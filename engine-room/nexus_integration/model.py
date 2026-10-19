"""Integration-substrate value objects — the migration decision model (ADR-008).

Pure, reusable values with **no business logic**: the substrate never computes a
decision, plans, evaluates policy, executes, validates, or recovers. It coordinates
*migration* — recording a legacy decision, its constitutional shadow, and their
classified diff (Recorded Shadow Adjudication, ADR-008 §3.2), and routing authority by
a per-owner feature flag (§3.6).

- :class:`FlagState` — the four deterministic migration states (§3.6 / Feature Flag Model).
- :class:`DeterminismClass` — drives which comparator is used (§3.3): deterministic
  decisions compare exactly; probabilistic (LLM) decisions compare by semantic hook
  only; external-state decisions compare evidence-aware.
- :class:`DecisionIdentity` — the stable identity of one adjudicated decision (owner,
  a caller-unique ``decision_id``, correlation, and an optional cohort key), so records
  and diffs are addressable and replayable (INV-17/INV-39).
- :class:`DecisionDiff` / :class:`AdjudicationResult` — the recorded comparison and the
  routed outcome (which side is authoritative, per the flag).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from nexus_core.contracts.base import Struct


class FlagState(StrEnum):
    """The deterministic migration states of a per-owner feature flag (ADR-008 §3.6)."""

    DISABLED = "disabled"  # legacy authoritative; constitutional owner inactive
    SHADOW = "shadow"  # constitutional owner computes side-effect-free; legacy authoritative
    CANARY = "canary"  # constitutional owner authoritative for a pinned cohort; legacy for the rest
    ENABLED = "enabled"  # constitutional owner authoritative; legacy shadows as a safety net


class DeterminismClass(StrEnum):
    """A decision's determinism class — selects the comparison strategy (ADR-008 §3.3)."""

    DETERMINISTIC = "deterministic"  # rule/config/state-machine → exact equality
    PROBABILISTIC = "probabilistic"  # LLM/cognition → semantic hook only, never exact-match
    EXTERNAL_STATE = "external_state"  # depends on live external state → evidence-aware


class DiffVerdict(StrEnum):
    """The comparator's classified verdict for one legacy-vs-shadow pair."""

    MATCH = "match"  # exactly equal (deterministic)
    EQUIVALENT = "equivalent"  # within the semantic/evidence equivalence band
    MISMATCH = "mismatch"  # a real divergence
    UNDETERMINED = "undetermined"  # no comparator available (probabilistic without a hook) → human


class Authority(StrEnum):
    """Which side of an adjudication is authoritative for the returned decision."""

    LEGACY = "legacy"
    CONSTITUTIONAL = "constitutional"


@dataclass(frozen=True, slots=True)
class DecisionIdentity:
    """The stable identity of one adjudicated decision (INV-17 replay; INV-39 correlation).

    ``decision_id`` must be unique per decision instance (the caller's responsibility) so
    the three recorded events (record / shadow / diff) address exactly one decision.
    ``cohort_key`` pins canary-cohort membership to a stable key (ADR-008 R4).
    """

    owner: str
    decision_id: str
    correlation_identifier: str
    cohort_key: str | None = None


@dataclass(frozen=True, slots=True)
class FeatureFlag:
    """A per-owner migration flag: its state and its monotonic version (versioned, §Flag Model)."""

    owner: str
    state: FlagState
    version: int


@dataclass(frozen=True, slots=True)
class DecisionDiff:
    """The recorded, deterministic comparison of a legacy decision and its shadow."""

    owner: str
    decision_id: str
    determinism_class: DeterminismClass
    verdict: DiffVerdict
    legacy_value: Any
    shadow_value: Any
    detail: Struct = field(default_factory=dict)

    @property
    def is_divergent(self) -> bool:
        """Whether the verdict is a real divergence (a mismatch)."""
        return self.verdict is DiffVerdict.MISMATCH


@dataclass(frozen=True, slots=True)
class AdjudicationResult:
    """The outcome of one adjudication: the routed authoritative decision plus its evidence."""

    identity: DecisionIdentity
    flag_state: FlagState
    authority: Authority
    authoritative_value: Any
    legacy_value: Any
    shadow_value: Any = None
    diff: DecisionDiff | None = None

    @property
    def constitutional_active(self) -> bool:
        """Whether the constitutional owner was authoritative for this decision."""
        return self.authority is Authority.CONSTITUTIONAL
