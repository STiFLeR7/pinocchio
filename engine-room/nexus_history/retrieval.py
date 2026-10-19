"""Deterministic retrieval — scope the authoritative log to a query, and read event facts.

Retrieval **selects, never reasons**: given the whole event log and a :class:`HistoryQuery`, it
returns exactly the events that match the query's recorded facts (correlation, goal, repository,
runtime, operator), in the log's own global order. It also **excludes the subsystem's own
``execution_history.*`` facts** — history is reconstructed from operational events only, never from
its own projections, which is what keeps repeated projections idempotent and replay deterministic.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from nexus_core.domain.event import Event
from nexus_history.events import HISTORY_EVENT_PREFIX
from nexus_history.model import HistoryQuery

_GOAL_KEYS = ("goal", "goal_identifier", "subject", "subject_identifier")
_REPO_KEYS = ("root", "repository_root", "repository")
_RUNTIME_KEYS = ("runtime", "runtime_ref", "chosen", "provider")
_OPERATOR_KEYS = ("operator", "user")


def first(payload: Mapping[str, Any], *keys: str) -> Any:
    """The first present, non-empty value among ``keys`` in ``payload`` (defensive fact read)."""
    for key in keys:
        value = payload.get(key)
        if value not in (None, "", (), []):
            return value
    return None


def _matches(event: Event, query: HistoryQuery) -> bool:
    payload = event.payload or {}
    if (
        query.correlation_identifier
        and event.correlation_identifier != query.correlation_identifier
    ):
        return False
    if query.goal_identifier:
        goal = first(payload, *_GOAL_KEYS)
        if query.goal_identifier not in (goal, event.correlation_identifier):
            return False
    if query.repository_root and first(payload, *_REPO_KEYS) != query.repository_root:
        return False
    if query.runtime and first(payload, *_RUNTIME_KEYS) != query.runtime:
        return False
    return not (
        query.operator and query.operator not in (first(payload, *_OPERATOR_KEYS), event.source)
    )


def filter_events(events: Iterable[Event], query: HistoryQuery) -> tuple[Event, ...]:
    """The operational events in scope for ``query`` (own ``execution_history.*`` facts excluded)."""
    return tuple(
        e for e in events if not e.type.startswith(HISTORY_EVENT_PREFIX) and _matches(e, query)
    )
