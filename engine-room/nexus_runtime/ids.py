"""Deterministic identifier derivation for the Runtime Manager.

Every identifier RM produces is a pure function of stable upstream identities (the
Execution Package identity it prepares, the chosen runtime's identity) and the attempt
ordinal — no clock, no counter, no randomness. This is what makes preparation
reproducible: the same intake, resolved against the same Registry snapshot, always
yields the same Runtime Session id, Allocation id, and event identifiers (doc 01 §5;
doc 02 §3 — the headline Phase 8A determinism guarantee).

Because the attempt ordinal is part of the session id, a retry is a *new* session with a
new deterministic id — never a mutation of the prior one (doc 02 §6).
"""

from __future__ import annotations


def runtime_session_id(package_identity: str, attempt: int = 1) -> str:
    """One Execution Package + one attempt ⇒ one stable Runtime Session id (doc 02 §3)."""
    return f"rts-{package_identity}-{attempt:02d}"


def allocation_id(session_identity: str, runtime_identity: str) -> str:
    """Derived from the session id and the chosen runtime identity (doc 02 §3)."""
    return f"alloc-{session_identity}-{runtime_identity}"


def event_id(scope_identity: str, kind: str, sequence: int) -> str:
    """A session-scoped, ordered, dedup-keyed event id (INV-16; mirrors Harness ids)."""
    return f"evt-{scope_identity}-{kind}-{sequence:04d}"


def correlation_id(seed_identity: str) -> str:
    """A deterministic fallback correlation id when none is carried through (INV-39)."""
    return f"cor-{seed_identity}"
