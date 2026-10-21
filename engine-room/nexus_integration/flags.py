"""Feature-flag infrastructure — the single, durable, event-sourced migration flag seam.

A per-owner flag governs migration authority (ADR-008 §3.6). Flags are:

- **default-off** — an unknown owner is ``DISABLED`` (legacy authoritative);
- **durable & replayable (ADR-007/INV-17)** — every transition is a ``migration.flag_set``
  event; :meth:`FlagStore.rebuild` reconstructs the whole flag set from the log, so a
  restart preserves migration state;
- **versioned** — each set bumps a monotonic per-owner version;
- **deterministic & observable** — same events → same state; each set increments telemetry.

:class:`FlagStore` is the **single evaluation seam** (guardrail: no scattered flag reads):
:meth:`state` is the only place flag state is read, so a flag flip changes routing
everywhere at once with no redeploy.

:class:`CanaryCohort` pins canary membership to a **stable key** (ADR-008 R4) via a
deterministic hash — no randomness, so cohort membership replays identically.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from nexus_core.domain.event import Event
from nexus_infra import content_hash
from nexus_integration.events import MIGRATION_FLAG_SET, build_event, system_now
from nexus_integration.gateway import CorrelationGateway
from nexus_integration.ids import flag_correlation, flag_set_id
from nexus_integration.model import DecisionIdentity, FeatureFlag, FlagState
from nexus_integration.observability import MigrationObservability


class FlagStore:
    """The single, durable, event-sourced seam for per-owner migration flags."""

    def __init__(
        self,
        *,
        gateway: CorrelationGateway | None = None,
        observability: MigrationObservability | None = None,
        now: Callable[[], str] | None = None,
    ) -> None:
        self._state: dict[str, FlagState] = {}
        self._version: dict[str, int] = {}
        self._gateway = gateway
        self._obs = observability or MigrationObservability()
        self._now = now or system_now

    # -- the single evaluation seam ----------------------------------------- #

    def state(self, owner: str) -> FlagState:
        """The current flag state for ``owner`` — ``DISABLED`` by default (default-off)."""
        return self._state.get(owner, FlagState.DISABLED)

    def version(self, owner: str) -> int:
        """The current flag version for ``owner`` (``0`` if never set)."""
        return self._version.get(owner, 0)

    def flag(self, owner: str) -> FeatureFlag:
        """The full versioned flag value for ``owner``."""
        return FeatureFlag(owner=owner, state=self.state(owner), version=self.version(owner))

    def set(self, owner: str, state: FlagState) -> FeatureFlag:
        """Transition ``owner``'s flag; record a durable, versioned ``migration.flag_set`` fact."""
        version = self._version.get(owner, 0) + 1
        if self._gateway is not None:
            payload = {"owner": owner, "state": state.value, "version": version}
            self._gateway.emit(
                build_event(
                    flag_set_id(owner, version),
                    MIGRATION_FLAG_SET,
                    flag_correlation(owner),
                    payload,
                    self._now(),
                )
            )
        self._state[owner] = state
        self._version[owner] = version
        self._obs.flag_set(owner, state)
        return FeatureFlag(owner=owner, state=state, version=version)

    def snapshot(self) -> dict[str, FlagState]:
        """The current state of every known owner (migration telemetry)."""
        return dict(self._state)

    # -- projection rebuild (ADR-007 restart determinism) ------------------- #

    def rebuild(self, events: Iterable[Event]) -> None:
        """Reconstruct the flag set purely from ``migration.flag_set`` facts (no re-emit)."""
        self._state.clear()
        self._version.clear()
        for event in events:
            if event.type != MIGRATION_FLAG_SET:
                continue
            owner = event.payload["owner"]
            version = int(event.payload["version"])
            if version >= self._version.get(owner, 0):
                self._state[owner] = FlagState(event.payload["state"])
                self._version[owner] = version


class CanaryCohort:
    """Deterministic canary-cohort membership pinned to a stable key (ADR-008 R4)."""

    def __init__(self, percentage: int, *, salt: str = "") -> None:
        if not 0 <= percentage <= 100:
            raise ValueError("percentage must be within [0, 100]")
        self._percentage = percentage
        self._salt = salt

    def includes(self, identity: DecisionIdentity) -> bool:
        """Whether ``identity`` falls in the canary cohort (stable, replayable, no randomness)."""
        key = identity.cohort_key or identity.decision_id
        bucket = int(content_hash({"salt": self._salt, "key": key})[:8], 16) % 100
        return bucket < self._percentage


#: A cohort that includes nobody — the safe default for ``CANARY`` without an explicit cohort.
EMPTY_COHORT = CanaryCohort(0)
