"""Recorded Shadow Adjudication + per-owner rollback (ADR-008 §3.2/§3.5/§3.6).

:class:`ShadowDecisionCoordinator.adjudicate` runs the five-stage flow for one decision:
record the legacy decision → (unless disabled) compute the constitutional shadow
side-effect-free → compare by determinism class → record the diff → route authority by the
per-owner flag. It is a **reusable coordinator with no business logic**: it never computes a
decision, plans, evaluates policy, executes, validates, or recovers — it invokes the
injected ``legacy`` and ``shadow`` decision callables (pure decision evaluations; the caller
performs any authoritative side effect afterward) and records the facts.

Authority routing (ADR-008 §3.6):

- ``DISABLED`` — legacy authoritative; the constitutional owner is **not invoked** (legacy
  path unchanged; the owner is active *only* when enabled/canary-for-cohort).
- ``SHADOW`` — legacy authoritative; the shadow computes side-effect-free for comparison.
- ``CANARY`` — the constitutional owner is authoritative for the pinned cohort, legacy for
  the rest; both are recorded (legacy reverse-shadows).
- ``ENABLED`` — the constitutional owner is authoritative; legacy shadows as a safety net.

The shadow is **side-effect-free** (§3.5): the only events under the decision's correlation
are the three ``migration.*`` records — enforced by a guardrail test.

:class:`RollbackCoordinator` rolls a single owner back with one atomic flag write —
owner-scoped (never global), immediate, deterministic, observable, and durable/replayable —
returning authority to the retained legacy path (§3.6).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nexus_integration.comparator import Comparator, ComparatorRegistry
from nexus_integration.flags import EMPTY_COHORT, CanaryCohort, FlagStore
from nexus_integration.model import (
    AdjudicationResult,
    Authority,
    DecisionDiff,
    DecisionIdentity,
    DeterminismClass,
    FlagState,
)
from nexus_integration.observability import MigrationObservability
from nexus_integration.recorder import DecisionRecorder


class ShadowDecisionCoordinator:
    """Coordinates Recorded Shadow Adjudication for one decision at a time (ADR-008)."""

    def __init__(
        self,
        flags: FlagStore,
        recorder: DecisionRecorder,
        comparators: ComparatorRegistry,
        *,
        observability: MigrationObservability | None = None,
    ) -> None:
        self._flags = flags
        self._recorder = recorder
        self._comparators = comparators
        self._obs = observability or MigrationObservability()

    def adjudicate(
        self,
        identity: DecisionIdentity,
        *,
        legacy: Callable[[], Any],
        shadow: Callable[[], Any],
        determinism_class: DeterminismClass,
        comparator: Comparator | None = None,
        cohort: CanaryCohort | None = None,
    ) -> AdjudicationResult:
        """Adjudicate one decision; record the facts; return the flag-routed authoritative value."""
        state = self._flags.state(identity.owner)  # the single flag seam

        legacy_value = legacy()
        self._recorder.record_legacy(identity, legacy_value, determinism_class)
        self._obs.decision_recorded(identity.owner)

        if state is FlagState.DISABLED:
            # Constitutional owner inactive: legacy path unchanged, no shadow computed.
            self._obs.routed(Authority.LEGACY)
            return AdjudicationResult(
                identity=identity,
                flag_state=state,
                authority=Authority.LEGACY,
                authoritative_value=legacy_value,
                legacy_value=legacy_value,
            )

        shadow_value = shadow()  # a pure, side-effect-free decision evaluation (ADR-008 §3.5)
        self._recorder.record_shadow(identity, shadow_value, determinism_class)
        self._obs.shadow_decision(identity.owner)

        chosen = comparator or self._comparators.for_class(determinism_class)
        verdict, detail = chosen.compare(legacy_value, shadow_value)
        diff = DecisionDiff(
            owner=identity.owner,
            decision_id=identity.decision_id,
            determinism_class=determinism_class,
            verdict=verdict,
            legacy_value=legacy_value,
            shadow_value=shadow_value,
            detail=detail,
        )
        self._recorder.record_diff(identity, diff)
        self._obs.diff(verdict)

        authority = self._route(state, identity, cohort)
        self._obs.routed(authority)
        authoritative = shadow_value if authority is Authority.CONSTITUTIONAL else legacy_value
        return AdjudicationResult(
            identity=identity,
            flag_state=state,
            authority=authority,
            authoritative_value=authoritative,
            legacy_value=legacy_value,
            shadow_value=shadow_value,
            diff=diff,
        )

    def _route(
        self, state: FlagState, identity: DecisionIdentity, cohort: CanaryCohort | None
    ) -> Authority:
        if state is FlagState.ENABLED:
            return Authority.CONSTITUTIONAL
        if state is FlagState.CANARY:
            in_cohort = (cohort or EMPTY_COHORT).includes(identity)
            return Authority.CONSTITUTIONAL if in_cohort else Authority.LEGACY
        return Authority.LEGACY  # SHADOW (DISABLED handled before shadow is computed)


class RollbackCoordinator:
    """Per-owner, atomic, deterministic rollback to the retained legacy path (ADR-008 §3.6)."""

    def __init__(
        self, flags: FlagStore, *, observability: MigrationObservability | None = None
    ) -> None:
        self._flags = flags
        self._obs = observability or MigrationObservability()

    def rollback(self, owner: str) -> None:
        """Return authority for ``owner`` to legacy with one atomic, durable flag write."""
        self._flags.set(owner, FlagState.DISABLED)
        self._obs.rolled_back(owner)

    def rollback_to(self, owner: str, state: FlagState) -> None:
        """Roll ``owner`` back to a specific earlier state (e.g. ``SHADOW``), owner-scoped."""
        self._flags.set(owner, state)
        self._obs.rolled_back(owner)
