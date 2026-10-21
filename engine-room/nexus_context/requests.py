"""Context Engineering inputs and outputs — the deterministic value models.

Phase 4 contains no AI. The raw operational information arrives as explicit,
immutable :class:`RawContextFragment` values (surfaced by collectors), and the
policies that govern relevance and freshness arrive as part of an immutable
:class:`ContextRequest`. Because every input is a frozen value object and every
derivation is mechanical, the same Goal and request always yield the same Context
Package.

The atoms:

- :class:`RawContextFragment` — a single heterogeneous datum *before* normalization.
- :class:`ContextItem` — a canonical, normalized unit *after* normalization; the
  ranker and freshness validator return enriched copies of it.
- :class:`FreshnessPolicy` — deterministic age thresholds plus the explicit
  evaluation instant (never the wall clock).
- :class:`ContextRequest` — the complete immutable input to one cycle.
- :class:`Conflict` — a surfaced (never auto-resolved) context conflict.
- :class:`ContextResult` — the complete output of one cycle.
"""

from __future__ import annotations

from pydantic import Field

from nexus_context.categories import (
    ConflictKind,
    ContextCategory,
    ContextSource,
    FreshnessState,
)
from nexus_core.contracts.base import Constraint, Reference, Struct, ValueObject
from nexus_core.domain.context_package import ContextPackage


class RawContextFragment(ValueObject):
    """One heterogeneous datum a collector surfaces, before normalization.

    ``source`` names the gathering source class; ``category`` is the collector's
    claimed Context Category; ``key`` is a stable handle unique within
    ``(source, category)``. ``observed_at`` is the ISO-8601 instant the underlying
    datum was true (used only for freshness, never for identity), and
    ``supersedes`` names other keys this datum explicitly makes stale.
    """

    source: ContextSource
    category: ContextCategory
    key: str
    payload: Struct = Field(default_factory=dict)
    observed_at: str | None = None
    references: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()


class ContextItem(ValueObject):
    """A canonical, normalized unit of context (the post-normalization atom).

    ``relevance`` is assigned by the ranker and ``freshness`` by the freshness
    validator; both default to their neutral values so a freshly normalized item is
    valid on its own. Items are immutable — each pipeline stage returns enriched
    copies via :meth:`model_copy`.
    """

    identity: str
    category: ContextCategory
    key: str
    source: ContextSource
    value: Struct = Field(default_factory=dict)
    observed_at: str | None = None
    references: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()
    relevance: int = 0
    freshness: FreshnessState = FreshnessState.UNKNOWN


class FreshnessPolicy(ValueObject):
    """Deterministic freshness thresholds and the explicit evaluation instant.

    ``evaluation_instant`` is the ISO-8601 'now' against which item ages are
    measured; it is an explicit input (never the wall clock) so freshness stays
    reproducible. ``default_max_age_seconds`` applies to any category without an
    entry in ``by_category`` (category value → max age in seconds). With no
    applicable threshold an item that carries a timestamp is considered ``VALID``.
    """

    evaluation_instant: str | None = None
    default_max_age_seconds: int | None = None
    by_category: Struct = Field(default_factory=dict)


class ContextRequest(ValueObject):
    """The complete, immutable input to one context-engineering cycle.

    ``fragments`` are operator-/environment-supplied seed data the default
    collectors surface. ``declared_dependencies`` are context keys that *must* be
    present (their absence is surfaced as a ``missing_dependency`` conflict).
    ``relevance_weights`` carries explicit per-category / per-source additive weight
    overrides for deterministic ranking.
    """

    fragments: tuple[RawContextFragment, ...] = ()
    constraints: tuple[Constraint, ...] = ()
    resources: tuple[Reference, ...] = ()
    supporting_artifacts: tuple[Reference, ...] = ()
    references: tuple[str, ...] = ()
    declared_dependencies: tuple[str, ...] = ()
    known_unknowns: tuple[str, ...] = ()
    freshness_policy: FreshnessPolicy = Field(default_factory=FreshnessPolicy)
    relevance_weights: Struct = Field(default_factory=dict)
    correlation_identifier: str | None = None
    package_version: str = "1"


class Conflict(ValueObject):
    """A surfaced context conflict — identified, never silently resolved.

    ``item_refs`` names the context-item identities involved so the conflict is
    auditable; ``detail`` carries kind-specific specifics.
    """

    kind: ConflictKind
    category: ContextCategory | None
    key: str
    item_refs: tuple[str, ...] = ()
    detail: Struct = Field(default_factory=dict)


class ContextResult(ValueObject):
    """The complete output of a context-engineering cycle — immutable.

    The :class:`ContextPackage` is the artifact Planning consumes; ``items`` and
    ``conflicts`` expose the assembled, ranked, freshness-evaluated working set and
    everything Context Engineering surfaced for inspection.
    """

    package: ContextPackage
    items: tuple[ContextItem, ...]
    conflicts: tuple[Conflict, ...]


def context_reference(package: ContextPackage) -> Reference:
    """Build the by-id Reference Planning consumes (the ``context_ref`` seam, ADR-003 §7).

    Wires ``Goal → Context → Context Package → Planning`` by composition: the result
    of one context cycle is referenced as ``PlanningRequest.context_ref`` with no
    coupling between the two layers and no change to either's frozen surface.
    """
    return Reference(target_type="context_package", identifier=package.identity)
