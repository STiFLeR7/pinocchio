"""Search provider port for autonomous runtimes (H-2 / Track H).

A minimal abstraction so agent ``web_search`` is backed by a real, injectable provider rather than
canned text — resolved by constructor injection like ``openrouter_client`` (runtime-abstraction Rule 2).
The concrete production provider is chosen at the integration site; the canned response used in tests
is a test double behind this same port.

Network egress for real search is governed by the active sandbox network policy
(see ``blueprint/implementations/v1.1.0/R-05-shared-resolution.md`` §6) — there is no hidden network
path in the runtime.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SearchProvider(ABC):
    """Port for web/document search injected into runtimes."""

    @abstractmethod
    async def search(self, query: str) -> str:
        """Return search results for ``query`` as text (or raise on provider failure)."""
        ...
