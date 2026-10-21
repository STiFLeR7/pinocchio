# Nexus SearchProvider Integration Report (H-2)

> Evidence for the `SearchProvider` abstraction and provider-backed `web_search` that replaces the
> canned response. Verified against current source + the H-2 test suite.

---

## 1. The port (`nexus/execution/runners/search_provider.py`)

```python
class SearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str) -> str:
        """Return search results for `query` as text (or raise on provider failure)."""
```

- Minimal protocol, mirroring the existing collaborator pattern (`openrouter_client`) — **runtime
  abstraction Rule 2**, no new framework.
- Mirrors the established `ResearchProvider` ABC idiom already in `intelligence/research.py:71` (one
  consistent provider pattern in the codebase, Rule 8).

## 2. Dependency injection (constructor seam)

`NexusRuntimeAdapter.__init__` gains an **additive, optional** `search_provider: Any = None`
parameter — injected exactly like `openrouter_client`. No contract change to `AgentRuntimeAdapter`; CLI
adapters (Gemini/Claude) are untouched.

## 3. Provider-backed execution (`_execute_tool` `web_search`)

| Condition | Behavior (after) | Evidence |
|---|---|---|
| Provider injected | `return str(await self.search_provider.search(query))` | `test_web_search_uses_injected_provider` — `FakeSearchProvider` returns `PROVIDER_BACKED_RESULT`; the query is recorded |
| No provider | Honest error: `"Error: no search provider is configured; cannot search for '<q>'."` | `test_web_search_without_provider_is_honest_error` — asserts `"MCP" not in result` and `"error" in result.lower()` |
| Provider raises | `"Error performing search: <e>"` (honest tool error) | exercised by the provider error path |

The canned MCP text is **removed from the runtime** and now exists only as a test double behind the same
port (`test_no_canned_search_literal_in_runtime` guards its absence).

## 4. Runtime trace (provider-backed)

```
=== SUCCESS (provider-backed search -> finish) ===
  step 0: tool=web_search status=completed result="[real-provider results for 'nexus']"
  step 1: tool=finish status=completed result='Agent completed execution.'
```

The `web_search` observation is the **provider's** output, not canned text — the agent then reasons over
a real observation.

## 5. Network egress governance (cross-track, honored)

Real search performs network I/O. Per `R-05-shared-resolution.md` §6 and the H-2 design, egress is
governed by the active sandbox network policy — there is **no hidden network path** in the runtime. H-2
delivers the **abstraction + injection seam**; the concrete production provider and its egress policy
binding are an integration-AP decision (the port makes that a one-line wiring, not a runtime rewrite).
Default deployments inject no provider → `web_search` returns the honest "no provider configured" error
(safe, non-networking default).

## 6. Boundaries preserved

- No new tools — `web_search` stays one of the existing five (`nexus_tools.VALID_TOOLS`).
- `execute_command` still routes through `SandboxManager`; file tools through the S-4 confinement seam —
  unchanged.
- No governance/registry/schema change.

## 7. Verdict

`web_search` is now **provider-driven via an injected `SearchProvider`**, with the canned response
removed from the runtime and a safe, honest no-provider default. AP-105 Gap 1 (search) / Cap 8 closed for
the Experimental bar.
