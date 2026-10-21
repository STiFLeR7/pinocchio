"""Deterministic runtime selection over the adapter registry (Milestone 5).

Selection depends **only** on required capabilities, declared runtime capabilities, and
declarative policy — never on heuristics, never on AI (INV-21, doc 06). Rather than invent a
second selection algorithm, this module *reuses* the Runtime Manager's own
:class:`~nexus_runtime.allocation.RuntimeSelector` — the single, audited match → health →
policy → choose funnel — projecting the adapter registry's descriptors into the
``RUNTIME``-category Registry view the selector reads. The chosen runtime is a pure function
of its inputs: identical inputs always choose the identical runtime (fail-closed on an empty
survivor set).

This is the selection layer only. Resolving the chosen identity back to a concrete adapter is
:meth:`~nexus_runtime_adapters.registry.AdapterRegistry.create`; driving it is the Execution
Engine's. Neither is changed here.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, Struct
from nexus_core.registries.interfaces import HarnessDescriptor
from nexus_runtime import (
    InMemoryHarnessRegistry,
    RuntimeRegistry,
    RuntimeSelector,
    SelectionResult,
)
from nexus_runtime_adapters.registry import AdapterRegistry


def _registry_view(
    adapters: AdapterRegistry, candidate_ids: tuple[str, ...]
) -> tuple[RuntimeRegistry, tuple[HarnessDescriptor, ...]]:
    """Project the adapter registry's descriptors into a ``RUNTIME`` Registry view."""
    harness = InMemoryHarnessRegistry()
    for identity in candidate_ids:
        harness.register(adapters.descriptor(identity))
    view = RuntimeRegistry(harness)
    resolved = tuple(adapters.descriptor(identity) for identity in candidate_ids)
    return view, resolved


def select_runtime(
    adapters: AdapterRegistry,
    required_capability_refs: tuple[Reference, ...],
    runtime_policy: Struct,
    *,
    candidate_ids: tuple[str, ...] | None = None,
) -> SelectionResult:
    """Deterministically choose one runtime from ``adapters`` (match → health → policy → choose).

    ``candidate_ids`` scopes selection to a subset of registered runtimes (defaults to all,
    in deterministic order). The result is the Runtime Manager's own auditable
    :class:`SelectionResult`, so the chosen runtime and the full funnel are inspectable.
    """
    ids = candidate_ids if candidate_ids is not None else adapters.identities()
    view, resolved = _registry_view(adapters, ids)
    selector = RuntimeSelector(view)
    return selector.select(resolved, required_capability_refs, runtime_policy)
