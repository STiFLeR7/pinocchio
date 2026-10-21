"""Deterministic identifier derivation for the Validation Engine.

Every identifier is a pure function of the execution session it validates (the
``ExecutionResult``'s session identity) plus a source/kind tag and an ordinal — no clock,
no counter, no randomness. This is what makes validation reproducible: the same evidence
against the same rules always yields the same Evidence ids, Report id, and event identifiers
(doc 14 *Deterministic*; INV-16/INV-17). Validation event ids carry a ``val-`` marker so
they never collide with the runtime's events in the shared, correlated event store.
"""

from __future__ import annotations


def report_id(session_identity: str) -> str:
    """One execution session ⇒ one stable Validation Report id."""
    return f"vr-{session_identity}"


def evidence_id(session_identity: str, source: str, sequence: int) -> str:
    """A session-scoped, source-tagged, ordered Evidence id."""
    return f"ev-{session_identity}-{source}-{sequence:04d}"


def event_id(session_identity: str, kind: str, sequence: int) -> str:
    """A session-scoped, ordered, dedup-keyed validation event id (INV-16)."""
    return f"evt-{session_identity}-val-{kind}-{sequence:04d}"
