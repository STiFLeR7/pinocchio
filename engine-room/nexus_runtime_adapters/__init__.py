"""``nexus_runtime_adapters`` — the runtime adapter ecosystem (Capability Program 2).

Turns Nexus from a control plane with one runtime into a platform that governs many, **without
redesigning Runtime or Execution** — only the adapter ecosystem is extended. It provides:

* :class:`AdapterRegistry` (Milestone 1) — a runtime-independent registry that discovers,
  registers, resolves, and exposes the capabilities of runtime adapters, naming no provider;
* :func:`select_runtime` (Milestone 5) — deterministic selection reusing the Runtime Manager's
  own match → health → policy → choose funnel (capabilities + policy only, never AI);
* :func:`build_default_adapter_registry` — the wiring seam loading the shipped Claude, Gemini,
  and Shell adapters;
* :class:`CrossRuntimeRunner` / :func:`governance_signature` (Milestones 4 & 6) — run the same
  governed workflow across substituted runtimes and prove identical governance.

Dependency direction: the registry/selection core imports only ``{nexus_execution, nexus_core,
nexus_runtime}``; the catalog and cross-runtime runner sit above and wire the concrete adapters
(``nexus_runtime_claude`` / ``nexus_runtime_gemini`` / ``nexus_runtime_shell``) and the
``nexus_workflows`` pipeline. It is imported by nothing upstream.
"""

from __future__ import annotations

from nexus_runtime_adapters.catalog import build_default_adapter_registry
from nexus_runtime_adapters.crossruntime import (
    CrossRuntimeRun,
    CrossRuntimeRunner,
    GovernanceSignature,
    governance_signature,
)
from nexus_runtime_adapters.registry import (
    AdapterFactory,
    AdapterRegistration,
    AdapterRegistry,
    AdapterRegistryError,
    DuplicateAdapterError,
    NotARuntimeError,
    RuntimeInvocationProfile,
    UnknownAdapterError,
)
from nexus_runtime_adapters.selection import select_runtime

__version__ = "2.5.0"

__all__ = [
    "AdapterFactory",
    "AdapterRegistration",
    "AdapterRegistry",
    "AdapterRegistryError",
    "CrossRuntimeRun",
    "CrossRuntimeRunner",
    "DuplicateAdapterError",
    "GovernanceSignature",
    "NotARuntimeError",
    "RuntimeInvocationProfile",
    "UnknownAdapterError",
    "build_default_adapter_registry",
    "governance_signature",
    "select_runtime",
]
