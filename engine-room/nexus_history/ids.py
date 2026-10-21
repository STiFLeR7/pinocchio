"""Deterministic identifier derivation for execution-history profiles and their events.

The profile identity is a content hash of the **historical facts** (every facet except the volatile
identity/timestamp/correlation), so an identical operational log — projected now or after restart —
reproduces an identical identity (idempotent, replayable; INV-16/INV-17). Projection happens once;
the id lets replay recognize the *same* historical view.
"""

from __future__ import annotations

import re

from nexus_core.contracts.base import Struct
from nexus_infra import content_hash

_VOLATILE = ("identity", "timestamp", "correlation_identifier")


def facts_digest(profile_dump: Struct) -> str:
    """Content digest over the historical facts (volatile fields excluded)."""
    facts = {k: v for k, v in profile_dump.items() if k not in _VOLATILE}
    return content_hash(facts)[:16]


def _scope_token(scope: str) -> str:
    """A short, id-safe token for a query scope (deterministic)."""
    token = re.sub(r"[^A-Za-z0-9]+", "-", scope).strip("-")
    return token[:32] or "global"


def profile_id(scope: str, profile_dump: Struct) -> str:
    """A content-addressed id for one ExecutionHistoryProfile (idempotent on an identical log)."""
    return f"eh-{_scope_token(scope)}-{facts_digest(profile_dump)}"


def projected_event_id(correlation_identifier: str, payload: Struct) -> str:
    """A correlation-scoped, content-addressed id for one ``execution_history.projected`` fact."""
    return f"evt-{correlation_identifier}-hist-{content_hash(payload)[:16]}"
