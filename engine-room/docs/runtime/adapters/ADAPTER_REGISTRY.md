# Runtime Adapter Registry — Implementation

`nexus_runtime_adapters` turns Nexus from a control plane with one runtime into a platform
that governs many — **without redesigning Runtime or Execution**. Only the adapter ecosystem
is extended. The registry (Milestone 1) is the missing seam between two things that already
existed: the Harness/Runtime Registry (which holds *descriptors* — what a runtime advertises)
and the Execution Engine (which needs a concrete *adapter instance* to drive).

## Responsibilities

`AdapterRegistry` (`registry.py`) does exactly the four things the mission names, and nothing
else:

| Concern | Method | Notes |
|---|---|---|
| **discover** | `discover_by_capability(cap)` / `identities()` / `descriptors()` | candidates only, deterministic order (INV-37) |
| **register** | `register(AdapterRegistration)` | fail-fast on non-`RUNTIME` category, identity/descriptor mismatch, or duplicate |
| **resolve** | `resolve(identity)` / `create(identity, profile=…)` | resolve returns the registration; `create` builds a fresh adapter |
| **expose capabilities** | `capabilities(identity)` / `descriptor(identity)` | reads the advertised abstract capabilities |

## Runtime-independent by construction

The registry names **no** provider. Its only imports are the
`nexus_execution.adapter.RuntimeAdapter` *protocol* and `nexus_core` — never
`nexus_runtime_claude` / `_gemini` / `_shell` (asserted by
`test_registry_and_selection_name_no_concrete_provider`). Concrete adapters are wired *in from
the outside*: `catalog.build_default_adapter_registry()` is the one composition seam that names
Claude, Gemini, and Shell. Adding a fourth execution environment is a one-line registration
there (or from anywhere else) — **no registry, selector, or engine change**. That is the whole
thesis: the Runtime abstraction is genuinely provider-agnostic.

## The registration record

```python
@dataclass(frozen=True, slots=True)
class AdapterRegistration:
    identity: str                 # the runtime identity (must equal descriptor.identity)
    descriptor: HarnessDescriptor # the abstract capabilities it advertises (RUNTIME category)
    factory: AdapterFactory       # (RuntimeInvocationProfile) -> RuntimeAdapter
```

`AdapterFactory` builds a **fresh** adapter per call (adapters carry per-session state), honoring
a `RuntimeInvocationProfile` — the deterministic-run knobs (`fail`, `hang`) every stub invoker in
the codebase already accepts. A profile is *not* a provider choice or a selection input; it only
shapes the reproducible event stream the chosen adapter produces, so the failure and cancel/timeout
paths stay reachable.

## Relationship to the existing registries

The `AdapterRegistry` is **not** a competing registry. Selection still reads through the Runtime
Manager's `RUNTIME`-category `RuntimeRegistry` lens (see `SELECTION`/`CROSS_RUNTIME`); the
`AdapterRegistry` only adds the descriptor→**adapter instance** resolution the engine needs — a
capability the descriptor-only registries never had. The two compose: `selection.py` projects the
adapter registry's descriptors into a `RuntimeRegistry` and runs the Runtime Manager's own funnel.
