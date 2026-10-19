# 02 — Architectural Fit

Where — if anywhere — OmniRoute can sit in the platform spine without violating the
dependency direction (`00` §4), the adapter boundary (`03` §3), the extensibility posture
(`19`), or the invariants. Covers capability model, session model, and the "does it force
architectural change?" question.

## 1. The only lawful position

```
 Planning ─▶ Context ─▶ Orchestration ─▶ Harness ─▶ │ Runtime Manager │ ─▶ Execution Engine
 ──────────── provider-blind (INV-32/37) ───────────┴─ provider-aware ─┘
                                                       │
                                    ┌──────────────────┴───────────────────┐
                                    │  RM core (generic, closed to change)  │
                                    │  ── ADAPTERS (the only provider region)│
                                    │        └─ LLM/Model Runtime adapter    │  ← Nexus-authored, future
                                    │              └─ OmniRoute (transport)  │  ← optional backend
                                    │                    └─ provider          │
                                    └───────────────────────────────────────┘
```

OmniRoute may exist **only** as provider mechanics *inside* a Nexus-authored adapter, in
the single provider-aware region (`00` §4, `03` §3). It may never appear in RM core, in the
Registry contract, in the lifecycle/event vocabulary, or anywhere upstream. This is the
same rule that confines "Docker" or "Claude" to their adapters — OmniRoute is confined one
level deeper still, because it is the adapter's *backend*, not the adapter.

## 2. Does it force any change to the Runtime architecture?

**No change to anything frozen.** Checked against `19` §4 ("provably does not change"):

| Frozen surface | Impact of adopting OmniRoute |
|---|---|
| Planning / Context / Orchestration / Harness | none — all capability-shaped (INV-21/32/37); OmniRoute is invisible to them |
| Execution Package shape | none — no provider field exists to add |
| RM core pipeline (`01`) | none — a new descriptor flows through the existing funnel |
| Runtime Session (`02`) | none — binds a package to an allocated runtime by reference |
| Lifecycle (`07`) / Events (`15`) | none — no new state, no new event |
| Registry contract (`04`) | none — a new `RUNTIME` descriptor is a new *record*, not a new registry (ADR-002) |
| Invariants / ADRs | none amended — the adapter *honors* INV-21/32/36/37, ADR-002/003 |

What it *does* introduce is a **new runtime category not present in the frozen example
set**: an "LLM/Model Runtime" whose Work Package is "produce a completion/agentic turn."
Per `19`, adding a runtime is *by design* additive — a new adapter + a Registry
registration — and explicitly does **not** count as changing the architecture. Phase 8A
also explicitly defers **all** adapters, so this belongs to a later adapter phase, not to
Runtime Core.

> Net: **no architectural change required; one new (optional) adapter permitted by the
> open-closed posture (`19` §7).** The architecture already anticipated exactly this.

## 3. Capability-model fit (`05`)

Nexus matches **abstract capabilities** (INV-32), not models or providers. OmniRoute
exposes *model* attributes (`capabilities.tool_calling`, `capabilities.vision`,
`context_length`). The LLM Runtime adapter would have to **translate**: advertise abstract
Capability references (e.g. `code_generation`, `tool_use`) on its Runtime Descriptor,
derived from the OmniRoute model catalog. That translation is exactly an adapter's job
(`03` §2 concern A; `05` §1 "provider identity enters only at adapter binding"). Fit is
**clean, through translation** — no capability-model change.

Caveat: OmniRoute's per-model `tool_calling` boolean is a *claim*, and for the reverse-
engineered no-auth providers the claim is unreliable (see `05_TOOL_CALLING.md`). The
capability model already handles this honestly — an advertised-but-unbacked capability must
be recorded as *unsupported*, never fabricated (`05` §3 negotiation, §2 honesty rule).

## 4. Session-model fit (`02`)

A Runtime Session binds one package to one allocated runtime for one attempt, as
references, with state as an event-log projection (ADR-001). An OmniRoute-backed session
binds trivially: `runtime_ref` = the LLM Runtime descriptor, `allocation_ref` = RM's
reservation, artifacts = the completion-as-structured-output + usage metadata (`13`). No
embedding, no mutable field bag — compatible. The only oddity is that such a session is
*extremely short-lived* (one HTTP round-trip), which the model tolerates (a session need
not be long).

## 5. Determinism & event-sourcing fit

RM's determinism (pure-function ids, injected `TimestampSource`, event-sourced projection)
is untouched: OmniRoute's internal non-determinism (routing, retries, fallback tier,
`X-OmniRoute-Request-Id`) is provider mechanics behind the adapter (`03` §1). RM records
only *facts it is handed* (result reference, usage, provider-served, latency) as canonical
events — themselves deterministic in id and structure. Fit is **preserved**.

## 6. Where it would leak if done wrong (anti-patterns to forbid)

- **Registering OmniRoute itself as a Runtime.** Category error — it hosts no Work Package;
  the "adapter" would have to fake Start/Configure/Cleanup (`01` §1 above). Forbidden.
- **Letting RM core branch on `X-Routing-Backend`/`X-OmniRoute-Provider`.** That is
  `if runtime == "..."` in disguise — a direct `03` §3 violation.
- **Treating OmniRoute's model catalog as the capability source.** Capabilities are
  abstract (INV-32); the catalog is provider data the adapter *translates*, never the
  authority upstream reads.
- **Storing provider keys in OmniRoute's sqlite store.** A second credential store — see
  `04_SECURITY_REVIEW.md`; violates the security spine unless no-auth-only.

## 7. Verdict for this doc

**Fits — but only as the sandboxed backend of a future, optional, Nexus-authored LLM
Runtime adapter, and only in the provider-aware region of RM.** It requires **zero** change
to any frozen contract, ADR, invariant, lifecycle state, or event. It introduces a new
runtime *category*, which the extensibility design (`19`) explicitly welcomes as additive.
It must never be a Runtime itself, never enter RM core, and never become upstream-visible.
