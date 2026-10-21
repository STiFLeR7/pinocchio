"""Deterministic identifier derivation for the Reflection Engine.

Reflection analyses a *history* — a window of completed operations — rather than a single
session, so its identifiers are pure functions of a **scope** (the operational window's stable
identity, e.g. a shared correlation) plus a kind tag and an ordinal — no clock, no counter, no
randomness. This is what makes reflection reproducible: the same history against the same
analyzers always yields the same Report id, Pattern ids, Candidate ids, and event identifiers
(doc 26 *Evidence First* / reproducible; INV-16/INV-17/INV-31). Reflection event ids carry a
``refl-`` marker so they never collide with runtime (``runtime.*``), validation (``-val-``), or
recovery (``-rec-``) events in the shared, correlated event store.
"""

from __future__ import annotations


def report_id(scope: str) -> str:
    """One operational window ⇒ one stable Reflection Report id."""
    return f"rr-{scope}"


def pattern_id(scope: str, kind: str, sequence: int) -> str:
    """A scope-tagged, kind-tagged, ordered Operational Pattern id."""
    return f"pat-{scope}-{kind}-{sequence:04d}"


def candidate_id(scope: str, sequence: int) -> str:
    """A scope-tagged, ordered Knowledge Candidate id."""
    return f"kc-{scope}-{sequence:04d}"


def event_id(scope: str, kind: str, sequence: int) -> str:
    """A scope-scoped, ordered, dedup-keyed reflection event id (INV-16)."""
    return f"evt-{scope}-refl-{kind}-{sequence:04d}"
