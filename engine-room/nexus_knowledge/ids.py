"""Deterministic identifier derivation for the Knowledge Engine.

The keystone is the **Knowledge Subject Key** (doc 03): the durable Item identity is a pure
function of ``(kind, canonical_subject)``, so recurring Candidates about the *same* subject
resolve to the *same* Item -- which is what makes deduplication and cross-run evolution
deterministic. There is no clock, no counter, and no randomness anywhere in this module
(INV-16/INV-17): the same recurring pattern always maps to the same Item, version, and event
identifiers across runs.

Subject canonicalisation is a fixed, documented normalisation (lower-case, non-alphanumeric
split, **stable token order**), so equivalent subjects collide intentionally. Knowledge event
ids carry a ``know`` marker so they never collide with runtime (``runtime.*``), validation
(``-val-``), recovery (``-rec-``), or reflection (``-refl-``) events in the shared, correlated
event store (doc 07).
"""

from __future__ import annotations

import re

from nexus_core.contracts.enums import KnowledgeType

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_subject(subject: str) -> str:
    """Canonicalise a subject to a stable, order-independent token slug (doc 03).

    Lower-cases, splits on any run of non-alphanumeric characters, drops empties, and joins the
    tokens in **sorted** order so that equivalent subjects (e.g. ``"retry storm"`` and
    ``"storm retry"``) map to one Subject Key. An empty/symbol-only subject slugs to
    ``"unspecified"`` so a key is always well-formed.
    """
    tokens = [token for token in _NON_ALNUM.split(subject.strip().lower()) if token]
    if not tokens:
        return "unspecified"
    return "-".join(sorted(tokens))


def subject_key(kind: KnowledgeType, subject: str) -> str:
    """The deterministic Knowledge Subject Key ``ki-{kind}-{normalized-subject}`` (doc 03)."""
    return f"ki-{kind.value}-{normalize_subject(subject)}"


def version_id(key: str, ordinal: int) -> str:
    """A subject-scoped, ordered Knowledge Version id (``(subject_key, ordinal)``, doc 03/10)."""
    return f"{key}-v{ordinal:04d}"


def event_id(key: str, kind: str, sequence: int) -> str:
    """A subject-scoped, ordered, dedup-keyed knowledge event id (``know`` marker, doc 07)."""
    return f"evt-{key}-know-{kind}-{sequence:04d}"
