"""Deterministic identifier derivation for the Recovery Engine.

Every identifier is a pure function of the execution session being recovered (the Validation
Report's session identity) plus a kind tag and an ordinal — no clock, no counter, no
randomness. This is what makes recovery reproducible: the same Validation Report against the
same policy always yields the same Recovery Plan id and event identifiers (doc 19
*deterministic*; INV-16/INV-17/INV-31). Recovery event ids carry a ``rec-`` marker so they
never collide with runtime (``runtime.*``) or validation (``-val-``) events in the shared,
correlated event store.
"""

from __future__ import annotations


def plan_id(session_identity: str) -> str:
    """One execution session ⇒ one stable Recovery Plan id."""
    return f"rp-{session_identity}"


def event_id(session_identity: str, kind: str, sequence: int) -> str:
    """A session-scoped, ordered, dedup-keyed recovery event id (INV-16)."""
    return f"evt-{session_identity}-rec-{kind}-{sequence:04d}"
