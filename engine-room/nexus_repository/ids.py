"""Deterministic identifier derivation for repository profiles and their events.

The profile identity is a content hash of the **repository facts** (every facet except the volatile
identity/timestamp/correlation and the execution-history lookup seam), so an identical tree — scanned
now or after restart — reproduces an identical identity (idempotent, replayable; INV-16/INV-17). The
scan happens once; the id lets replay recognize the *same* understanding.
"""

from __future__ import annotations

import os

from nexus_core.contracts.base import Struct
from nexus_infra import content_hash

_VOLATILE = ("identity", "timestamp", "correlation_identifier", "execution_history")


def facts_digest(profile_dump: Struct) -> str:
    """Content digest over the repository facts (volatile/lookup fields excluded)."""
    facts = {k: v for k, v in profile_dump.items() if k not in _VOLATILE}
    return content_hash(facts)[:16]


def profile_id(root: str, profile_dump: Struct) -> str:
    """A content-addressed id for one RepositoryProfile (idempotent on identical trees)."""
    name = os.path.basename(os.path.normpath(root)) or "repo"
    return f"rp-{name}-{facts_digest(profile_dump)}"


def profiled_event_id(correlation_identifier: str, payload: Struct) -> str:
    """A correlation-scoped, content-addressed id for one ``repository.profiled`` fact."""
    return f"evt-{correlation_identifier}-repo-{content_hash(payload)[:16]}"
