"""Context Engineering vocabularies — the closed, canonical enumerations.

These are the stable vocabularies Phase 4 reasons over:

- :class:`ContextCategory` — the **eight** canonical Context Categories (contract
  ``context_package.md`` §4 / doc 03). Each value is *exactly* the corresponding
  field name on :class:`~nexus_core.domain.context_package.ContextCategories`, so the
  builder can route a normalized item into its category by value with no mapping
  table to drift.
- :class:`ContextSource` — the five canonical source *classes* (doc 03 *Context
  Sources*). Sources are open-ended in the real world; this enum names the classes
  Context Engineering organizes them under, not every concrete provider.
- :class:`FreshnessState` — the freshness verdict assigned to each context item.
- :class:`ConflictKind` — the kinds of conflict the detector surfaces (never
  silently resolves).
"""

from __future__ import annotations

from enum import StrEnum


class ContextCategory(StrEnum):
    """The eight canonical Context Categories; values match ``ContextCategories`` fields."""

    GOAL = "goal_context"
    DOMAIN = "domain_context"
    WORKSPACE = "workspace_context"
    HISTORICAL = "historical_context"
    OPERATIONAL = "operational_context"
    CONSTRAINT = "constraint_context"
    RESOURCE = "resource_context"
    EXECUTION = "execution_context"


class ContextSource(StrEnum):
    """The five canonical source classes context is gathered from (doc 03)."""

    WORKSPACE = "workspace"
    KNOWLEDGE = "knowledge"
    OPERATOR = "operator"
    RUNTIME = "runtime"
    ENVIRONMENT = "environment"


class FreshnessState(StrEnum):
    """Freshness verdict for a context item (doc 03 *Context Validation*)."""

    VALID = "valid"
    STALE = "stale"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class ConflictKind(StrEnum):
    """The kinds of context conflict the detector surfaces rather than resolving."""

    DUPLICATE = "duplicate"
    CONTRADICTION = "contradiction"
    STALE = "stale"
    MISSING_DEPENDENCY = "missing_dependency"
