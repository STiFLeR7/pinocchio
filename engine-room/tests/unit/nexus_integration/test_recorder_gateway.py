"""Decision recorder + correlation gateway (``recorder.py`` / ``gateway.py``, ADR-008 §3.2).

The recorder emits the three adjudication facts through the gateway, all under the
decision's correlation (INV-39); the gateway is a transport-only passthrough.
"""

from __future__ import annotations

from nexus_integration import (
    CorrelationGateway,
    DecisionDiff,
    DecisionIdentity,
    DecisionRecorder,
    DeterminismClass,
    DiffVerdict,
)
from nexus_integration.events import (
    MIGRATION_DECISION_DIFF,
    MIGRATION_DECISION_RECORDED,
    MIGRATION_SHADOW_DECISION,
)


class _Spy:
    def __init__(self) -> None:
        self.events: list = []

    def emit(self, event) -> None:
        self.events.append(event)


def _identity() -> DecisionIdentity:
    return DecisionIdentity(owner="policy_engine", decision_id="d1", correlation_identifier="cor-1")


def test_recorder_emits_three_correlated_facts() -> None:
    spy = _Spy()
    recorder = DecisionRecorder(CorrelationGateway(spy), now=lambda: "t")
    identity = _identity()
    recorder.record_legacy(identity, "allow", DeterminismClass.DETERMINISTIC)
    recorder.record_shadow(identity, "deny", DeterminismClass.DETERMINISTIC)
    recorder.record_diff(
        identity,
        DecisionDiff(
            "policy_engine",
            "d1",
            DeterminismClass.DETERMINISTIC,
            DiffVerdict.MISMATCH,
            "allow",
            "deny",
        ),
    )
    types = [e.type for e in spy.events]
    assert types == [
        MIGRATION_DECISION_RECORDED,
        MIGRATION_SHADOW_DECISION,
        MIGRATION_DECISION_DIFF,
    ]
    assert all(e.correlation_identifier == "cor-1" for e in spy.events)  # INV-39


def test_gateway_is_transport_only_passthrough() -> None:
    spy = _Spy()
    gateway = CorrelationGateway(spy)
    recorder = DecisionRecorder(gateway, now=lambda: "t")
    event = recorder.record_legacy(_identity(), "allow", DeterminismClass.DETERMINISTIC)
    assert spy.events == [event]  # forwarded unchanged
    assert event.producer == "integration"
