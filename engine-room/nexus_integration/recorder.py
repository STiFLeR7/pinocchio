"""Decision recorder — writes the three Recorded Shadow Adjudication facts (ADR-008 §3.2).

Emits ``migration.decision_recorded`` (the legacy DecisionRecord), ``migration.shadow_decision``
(the constitutional ShadowDecision), and ``migration.decision_diff`` (the classified DecisionDiff)
through the correlation gateway, all under the decision's correlation stream (INV-39), durable
and append-only (ADR-007/INV-13). It records; it never decides. Decision *values* are recorded
opaquely (the substrate has no business logic); callers pass serializable decision values.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event
from nexus_integration.events import (
    MIGRATION_DECISION_DIFF,
    MIGRATION_DECISION_RECORDED,
    MIGRATION_SHADOW_DECISION,
    build_event,
    system_now,
)
from nexus_integration.gateway import CorrelationGateway
from nexus_integration.ids import decision_diff_id, decision_recorded_id, shadow_decision_id
from nexus_integration.model import DecisionDiff, DecisionIdentity, DeterminismClass


class DecisionRecorder:
    """Records the legacy decision, its shadow, and their diff as durable correlated facts."""

    def __init__(
        self, gateway: CorrelationGateway, *, now: Callable[[], str] | None = None
    ) -> None:
        self._gateway = gateway
        self._now = now or system_now

    def record_legacy(
        self, identity: DecisionIdentity, value: Any, determinism_class: DeterminismClass
    ) -> Event:
        """Record the legacy decision at the owner's boundary (ADR-008 *DecisionRecord*)."""
        payload = {
            "owner": identity.owner,
            "decision_id": identity.decision_id,
            "source": "legacy",
            "determinism_class": determinism_class.value,
            "value": value,
        }
        return self._emit(
            decision_recorded_id(
                identity.correlation_identifier, identity.owner, identity.decision_id
            ),
            MIGRATION_DECISION_RECORDED,
            identity,
            payload,
        )

    def record_shadow(
        self, identity: DecisionIdentity, value: Any, determinism_class: DeterminismClass
    ) -> Event:
        """Record the constitutional owner's side-effect-free shadow (ADR-008 *ShadowDecision*)."""
        payload = {
            "owner": identity.owner,
            "decision_id": identity.decision_id,
            "source": "constitutional",
            "determinism_class": determinism_class.value,
            "value": value,
        }
        return self._emit(
            shadow_decision_id(
                identity.correlation_identifier, identity.owner, identity.decision_id
            ),
            MIGRATION_SHADOW_DECISION,
            identity,
            payload,
        )

    def record_diff(self, identity: DecisionIdentity, diff: DecisionDiff) -> Event:
        """Record the classified comparison (ADR-008 *DecisionDiff*)."""
        payload = {
            "owner": diff.owner,
            "decision_id": diff.decision_id,
            "determinism_class": diff.determinism_class.value,
            "verdict": diff.verdict.value,
            "legacy_value": diff.legacy_value,
            "shadow_value": diff.shadow_value,
            "detail": dict(diff.detail),
        }
        return self._emit(
            decision_diff_id(identity.correlation_identifier, identity.owner, identity.decision_id),
            MIGRATION_DECISION_DIFF,
            identity,
            payload,
        )

    def _emit(
        self, identifier: str, event_type: str, identity: DecisionIdentity, payload: Struct
    ) -> Event:
        event = build_event(
            identifier, event_type, identity.correlation_identifier, payload, self._now()
        )
        self._gateway.emit(event)
        return event
