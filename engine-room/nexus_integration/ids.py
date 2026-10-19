"""Deterministic identifier derivation for migration events.

Every id is a pure function of the fact it names — no clock, counter, or randomness —
so adjudication is reproducible and idempotent (INV-16/INV-17): re-recording an
identical fact yields the same id (a no-op in the durable log). The ``mig-`` marker
keeps migration events from colliding with other producers in the shared, correlated
store; ids are namespaced by the decision identity so the three facts of one decision
group under its correlation stream (INV-39).
"""

from __future__ import annotations


def decision_recorded_id(correlation_identifier: str, owner: str, decision_id: str) -> str:
    return f"evt-{correlation_identifier}-mig-record-{owner}-{decision_id}"


def shadow_decision_id(correlation_identifier: str, owner: str, decision_id: str) -> str:
    return f"evt-{correlation_identifier}-mig-shadow-{owner}-{decision_id}"


def decision_diff_id(correlation_identifier: str, owner: str, decision_id: str) -> str:
    return f"evt-{correlation_identifier}-mig-diff-{owner}-{decision_id}"


def flag_set_id(owner: str, version: int) -> str:
    return f"evt-mig-flag-{owner}-{version:06d}"


def flag_correlation(owner: str) -> str:
    """The stable lifecycle stream a per-owner flag's transitions share (INV-39)."""
    return f"migration-flag-{owner}"
