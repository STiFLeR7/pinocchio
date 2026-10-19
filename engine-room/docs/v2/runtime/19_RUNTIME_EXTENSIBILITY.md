# 19 — Runtime Extensibility

**Status:** design only. This document shows that a **new runtime** — Claude Code,
Gemini CLI, Python, Docker, Browser, Shell, MCP, a remote worker, or one not yet
imagined — can be added to Nexus by changing **only the Runtime Manager**, and within
RM by adding **only a new Adapter plus a Registry registration**. It explains *why* the
upstream layers are structurally insulated, walks through adding a hypothetical future
runtime, proves what does and does not change, and states the open-closed posture and
multi-adapter coexistence rules.

Read alongside: `03_RUNTIME_ADAPTERS.md` (the adapter contract), `04_RUNTIME_REGISTRY.md`
(registration/discovery), `05_RUNTIME_CAPABILITIES.md` (capability advertisement),
`06_RUNTIME_SELECTION.md` (how an adapter's runtime becomes selectable),
`00_RUNTIME_OVERVIEW.md` (dependency direction), `15_RUNTIME_EVENTS.md` (the fixed
event taxonomy).

---

## 1. The extensibility claim

> Adding a runtime requires **(a) a new Runtime Adapter** and **(b) a Registry
> registration of its descriptor**. Nothing else in Nexus changes. Planning, Context
> Engineering, Orchestration, and Harness are **untouched**; RM's own core is
> **untouched**; the Execution Package shape, the lifecycle (`07`), and the event
> taxonomy (`15`) are **untouched**.

This is not an aspiration; it is a consequence of two existing invariants. **Upstream
layers speak capabilities, not runtimes (INV-32).** And **Orchestration emits candidates
by capability, never by provider name (INV-37).** Because no upstream artifact ever
mentions a concrete runtime, a new runtime is invisible to all of them by construction.

## 2. Why the upstream layers are insulated

Trace what each layer actually carries about runtimes:

- **Planning** decomposes into Work Packages; a Work Package **never selects its own
  runtime (INV-21)**. It states *what must be done*, never *what runs it*.
- **Context Engineering** assembles operational understanding (a Context View). It
  references capabilities and knowledge, not providers.
- **Orchestration** builds the `RuntimeRequest`. Its inputs are
  `required_capability_refs` and the declarative `runtime_policy`; its candidate list,
  `candidate_harness_refs`, is produced by `discover_by_capability` (candidates only —
  INV-37) over the Registry. The provider identities it lists are **opaque references**
  it never interprets — it does not branch on "is this Docker?" It cannot, because it
  holds no provider semantics.
- **Harness** compiles the immutable **Execution Package** from capabilities, skills,
  context, policy, and strategy. The package is **capability-shaped**: it says "needs
  capability X under policy Y," never "run on runtime Z."

The dependency direction makes this structural, not merely conventional:
`nexus_runtime → {nexus_core, nexus_infra}` only, and **nothing upstream imports
`nexus_runtime`** (`00` §4). A new runtime lives entirely inside `nexus_runtime` (behind
an adapter), in a subsystem the upstream layers cannot even reference. There is no import
path along which a new runtime could leak upward.

```
   Planning ─▶ Context ─▶ Orchestration ─▶ Harness ─▶ │ Runtime Manager │ ─▶ Execution Engine
   (caps)      (caps)     (caps+candidate   (capability  │  ADAPTERS (the   │
                          refs, INV-37)      Execution    │  ONLY place a    │
                                             Package)     │  provider lives) │
   ───────────── all provider-blind (INV-32) ────────────┴── provider-aware ─┘
                                                              (added here only)
```

The provider-aware region is a **single, bounded place**: the adapter layer inside RM.
Everything to its left is provider-blind. That asymmetry is the whole insulation story.

## 3. The insulation table

Each upstream layer, and *why* it never needs to know a new runtime exists:

| Layer | What it carries about runtimes | Why a new runtime is invisible to it |
|---|---|---|
| **Planning** | nothing — a Work Package never names a runtime | INV-21: the package states work, not host; selection is RM's |
| **Context Engineering** | capability & knowledge references | speaks capabilities (INV-32); no provider vocabulary exists in a Context View |
| **Orchestration** | `required_capability_refs`, declarative `runtime_policy`, and `candidate_harness_refs` (opaque refs) | INV-37: emits candidates **by capability**, never provider names; never interprets a candidate's identity |
| **Harness** | a capability-shaped **Execution Package** + Manifest | the package's runtime requirements are `runtime_policy` (capability-based); no provider field exists to change |
| **RM core** (non-adapter) | the generic pipeline (`01`), session (`02`), lifecycle (`07`), events (`15`) | it drives every runtime through the *same* adapter contract (`03`); a new adapter satisfies the existing contract |
| **Execution Engine** (downstream) | a `Ready` session bound to an already-allocated runtime | it drives whatever the adapter exposes through the generic contract; it never branches on provider |

The only row in the platform where a new runtime is **visible** is the one this document
adds to: **a new adapter + its Registry registration.**

## 4. What changes vs. what provably does not

### Changes (and *only* these)

| Change | Where | What it is |
|---|---|---|
| **New Runtime Adapter** | `nexus_runtime`, behind the adapter boundary (`03`) | the provider-specific code that drives this runtime through the conceptual adapter contract — start/stream/cancel/cleanup/health, configuration rendering |
| **Capability advertisement** | the adapter's descriptor | the abstract `advertised_capabilities` (references) the runtime can satisfy (INV-32) |
| **Registry registration** | the Registry view over the Harness Registry (`04`) | register a `HarnessDescriptor` of category `RUNTIME` (identity, version, advertised capabilities, availability, health, configuration) so discovery/selection can see it |

### Provably does NOT change

| Unchanged | Why it cannot need to change |
|---|---|
| **Planning, Context Engineering, Orchestration, Harness** | none holds provider vocabulary; all are capability-shaped (INV-21/32/37) |
| **The Execution Package shape** | it is capability-based; a new runtime adds no field, because the package never names a runtime |
| **RM core pipeline** (`01`) | the funnel (`06`) operates on descriptors and capabilities, not provider branches; a new descriptor flows through unchanged |
| **The Runtime Session** (`02`) | it binds *a* package to *an* allocated runtime by reference; the runtime's identity is just another reference |
| **The lifecycle** (`07`) | `Created … Destroyed` are runtime-independent; no new state is invented for a new runtime |
| **The event taxonomy** (`15`) | `runtime.*` events are runtime-independent facts; a new runtime emits the *same* events through the adapter |
| **The Registry contract** (`04`) | a new runtime is a new *record*, not a new *registry*; it reuses `HarnessDescriptor` and `register` |
| **Invariants / ADRs** | INV-21/32/36/37, ADR-002/004 are untouched; the new runtime *honors* them, it does not amend them |

If any of these *did* have to change to add a runtime, the abstraction would have leaked.
The design's correctness criterion is precisely that they do not.

## 5. Walkthrough — adding a hypothetical future runtime

Suppose a future "Quantum Worker" runtime appears (a remote service exposing a job
interface). Adding it:

```
   STEP 1  Author a "Quantum Worker" Runtime Adapter inside nexus_runtime.
           - It satisfies the existing conceptual adapter contract (03):
             configure, start, stream output, report progress/heartbeat,
             cancel (graceful/forced), emit artifacts as Evidence Candidates,
             expose a health signal, and run cleanup on teardown.
           - All provider specifics (its job protocol, its remote endpoint
             handling) live ONLY here, behind the adapter boundary.

   STEP 2  Advertise its capabilities on its Runtime Descriptor.
           - List the abstract Capability references it can satisfy (INV-32) —
             e.g. the same capability refs upstream uses to express the need.
           - No provider name ever enters a capability; the descriptor maps a
             provider (the adapter) to abstract capabilities.

   STEP 3  Register the descriptor in the Registry view (04).
           - Register a HarnessDescriptor of category RUNTIME (identity,
             version, advertised_capabilities, availability, health,
             configuration). INV-36 keeps availability/health owned by the
             Harness Registry; RM only reads it.

   DONE.   The Quantum Worker is now a CANDIDATE wherever its advertised
           capabilities match a required capability — automatically, because
           Orchestration's discover_by_capability (INV-37) will surface it with
           no change to Orchestration.
```

From that point the new runtime flows through the **unchanged** machinery: it appears in
`candidate_harness_refs` (Orchestration, no change), is matched (`05`), health-filtered
(`04`), policy-filtered (`18`), possibly approval-gated (`14`), selected and allocated
(`06`), bound to a session (`02`), driven to `Ready` (`07`), and supervised via the same
`runtime.*` events (`15`). **No upstream code, no package field, no lifecycle state, and
no event name was added or edited to make a brand-new runtime fully first-class.**

What a maintainer touched: **one adapter, one set of advertised capabilities, one
registration.** What a maintainer did not touch: **everything else.**

## 6. Versioning & coexistence of adapters

Multiple adapters — and multiple versions of one adapter — coexist by design:

- **Identity + version on the descriptor.** `HarnessDescriptor` carries `identity` and
  `version` (`04`). Two versions of the same runtime are two descriptors; both can be
  registered, both can be candidates, and selection (`06`) chooses among them by the same
  capability/health/policy funnel — version is just another descriptor attribute the
  funnel can consider (e.g. via policy allow-lists or declarative preference).
- **Many providers, one capability.** Several runtimes may advertise the *same* abstract
  capability (INV-32). That is the normal case, not a conflict: they form the candidate
  set for that capability, and the deterministic selection in `06` picks one. Adding the
  Nth provider for a capability changes nothing upstream — it just enlarges a candidate
  set the funnel already handles.
- **Deprecation/rollout.** Retiring a runtime is a Registry concern: mark its descriptor
  unavailable (or deregister it). It then simply stops appearing as a healthy candidate
  (`06` stage C). No upstream artifact references it, so nothing upstream breaks. A
  staged rollout is two coexisting descriptors with policy steering selection between
  them — still no upstream change.
- **No global switch.** There is no central "list of supported runtimes" in RM core to
  edit. Support is expressed entirely as *registered descriptors* backed by *adapters*.
  Adding/removing support is registration, not modification.

## 7. Open–closed posture

RM realizes the open/closed principle at the resource layer:

| Aspect | Posture |
|---|---|
| **RM core** (pipeline `01`, session `02`, lifecycle `07`, events `15`, selection `06`) | **Closed to modification.** Adding a runtime requires no edit here. |
| **Runtime support** (the set of runtimes Nexus can host) | **Open to extension** via new adapters + registrations. |
| **The adapter contract** (`03`) | **Stable.** A new runtime *satisfies* it; it does not redefine it. The contract is the extension seam. |
| **Provider knowledge** | **Confined.** It exists only inside adapters — the single provider-aware region (`00` §4, §2 above). |

The litmus test mirrors `01`'s boundary test: if adding a runtime forced an edit outside
an adapter and its registration, an abstraction leaked and the design — not the new
runtime — is at fault. The reason RM core can stay closed is that every runtime is driven
through the **one** adapter contract, and every selection input (`06`) is an abstract
capability, a Registry-owned health signal, or a declarative policy — never a provider
branch.

## 8. Why this matters (the payoff)

Because the provider-aware surface is one bounded layer:

- **No provider assumptions in RM core** — satisfying the mandate that Claude Code,
  Gemini CLI, Python, Docker, Browser, Shell, MCP, remote workers, *and unknown future
  runtimes* are all first-class without special cases.
- **Upstream stability** — Planning/Context/Orchestration/Harness never re-ship to
  support a new runtime, so their contracts and tests stay frozen as runtimes evolve.
- **Auditable extension** — adding a runtime is a reviewable, localized change (one
  adapter + one registration), with the same `runtime.*` audit trail (`15`) as every
  existing runtime.

## 9. Invariants and canon honored here

| Invariant / ADR | How extensibility honors it |
|---|---|
| **INV-21** a Work Package never selects its runtime | upstream stays provider-blind; a new runtime is only ever a *candidate*, chosen by RM (`06`) |
| **INV-32** capabilities are provider-independent | a new runtime *advertises* abstract capabilities; upstream still speaks only capabilities |
| **INV-36** the Registry owns availability/health | a new runtime registers a descriptor; the Harness Registry keeps owning its availability/health |
| **INV-37** Orchestration produces candidates, not selections | a new runtime auto-appears in `candidate_harness_refs` with no Orchestration change |
| **ADR-002** a Runtime is a `RUNTIME` Harness; four registries | extension reuses `HarnessDescriptor` + `register`; **no second registry** is created |
| **Dependency direction** (`00` §4) | the new runtime lives in `nexus_runtime` behind an adapter; nothing upstream imports it |

## 10. Cross-references

- `03_RUNTIME_ADAPTERS.md` — the conceptual adapter contract a new runtime satisfies.
- `04_RUNTIME_REGISTRY.md` — registering the descriptor; discovery; availability/health.
- `05_RUNTIME_CAPABILITIES.md` — advertising and matching capabilities (INV-32).
- `06_RUNTIME_SELECTION.md` — how a registered runtime becomes a candidate, then allocated.
- `00_RUNTIME_OVERVIEW.md` — dependency direction and the single provider-aware region.
- `07_RUNTIME_LIFECYCLE.md` / `15_RUNTIME_EVENTS.md` — the unchanged lifecycle and event taxonomy a new runtime reuses.
- `ARCHITECTURE_REVIEW.md` — scalability/risk notes, including the multi-adapter and rollout considerations referenced in §6.
