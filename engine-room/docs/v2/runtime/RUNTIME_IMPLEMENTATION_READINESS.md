# Runtime Implementation Readiness Review

**Status:** design only — the **final architecture ratification** before Phase 8A (Runtime
Core) implementation. Consolidates the architecture audit (terminology, dependency,
lifecycle, event, session, allocation, observability, ownership) and the readiness
evaluation (completeness, ambiguities, risks, extensibility). Concludes with the six
readiness questions.

**This document, and the five docs 21–24 it ratifies, modify no ADR, contract, or
invariant, and add no lifecycle state, event, or dependency edge.** They classify and
formalize concepts already implicit in the canon (transport already lived behind the
adapter — `11` §2.4, `03` §3).

Scope of review: `docs/v2/runtime/00`–`20`, the new `21`–`24`, `ARCHITECTURE_REVIEW.md`,
the shipped `nexus_runtime/` (Phase 8A implementation), and `docs/runtime/assessment/`
(OmniRoute).

---

## Part A — Architecture Audit (Task 5)

### A.1 Terminology consistency

| Term | Definition source | Used consistently? |
|---|---|---|
| Runtime Manager / Runtime / Adapter / Session / Allocation / Candidate / Preparation / Handoff | `00` §7 canon glossary | ✓ — every doc uses the glossary verbatim |
| **Transport** | pre-existing (`11` §2.4 "adapter owns the transport"), now formalized in `23` | ✓ — `23`/`22` align with the prior usage; no redefinition |
| **Host / Service / Gateway / Embedded** | new in `21` | ✓ — a classification lens; no existing term is overloaded or contradicted |
| Lifecycle states (`Created…Destroyed`) | `07` | ✓ — `21`/`22`/`23` reuse them; coin none |
| Error classes (runtime-unavailable, allocation-failure, execution-startup-failure, transport-failure, provider-failure, infrastructure-failure, user-cancellation, timeout) | `11` §2 | ✓ — `23` §6 maps transport faults onto these; adds none |

One pre-existing wording tension is already tracked, not introduced here: **G-2**
("Orchestration assigns" vs "RM allocates") — resolved by canon as *Orchestration nominates
candidates, RM allocates* (`20` G-2, INV-37). The new docs use the correct reading
throughout.

### A.2 Dependency direction

`nexus_runtime → { nexus_core, nexus_infra }` only (`00` §4). Transport and Gateway add
**no** new import and **no** upstream edge — they live behind the adapter boundary inside
`nexus_runtime` (`22` §5, `23` §1). Upstream stays provider-blind (INV-21/32/37). ✓
Verified against the shipped package (Phase 8A imports nothing upstream).

### A.3 Lifecycle consistency

The canonical machine (`07`) is untouched. `21`/`22` note that **weight** varies by category
(Host exercises the full machine; Service/Gateway/Embedded collapse toward execution states)
— but no category adds or removes a state. Phase 8A's realized preparation slice
(`Created→Registered→Allocated→Prepared→Ready` + `Released`/`Failed`) is unaffected. ✓

### A.4 Event consistency

`runtime.*` taxonomy (`15`) is fixed; the new docs emit no new event. Gateway silent
downgrades are recorded as **execution-metadata artifacts** (`13`), not a new event
(`23` §6, `24` note ⁴). ✓

### A.5 Session consistency

`02` is authoritative. A Service/Gateway/Embedded session is short-lived but binds
identically (package ⇄ allocated runtime, by reference; state = event projection). No
category needs a second session shape. ✓ (Session remains a runtime-layer value object per
G-1 — deliberately not pre-frozen.)

### A.6 Allocation consistency

RM owns selection + allocation (`06`, INV-37); `ResourceAllocationState`
(`AVAILABLE→RESERVED→ALLOCATED→RELEASED`). Transport/Gateway change nothing here — a gateway
is not allocated; the *runtime* (the Service behind it) is the allocatable candidate, and
capacity remains a Registry concern (G-3). ✓

### A.7 Observability consistency

`16` telemetry is derived, never authoritative. Transport-level signals (latency, served
provider, retries, breaker state) enter as **adapter-surfaced facts** — cost/usage as
**events** (G-8), operational latency/health as derived metrics. No transport metric becomes
session state. ✓

### A.8 Ownership — exactly one owner, no overlap (the core of Task 5)

| Responsibility | Owner | Not owned by |
|---|---|---|
| allocation | **Runtime Manager** | adapter, transport, engine |
| session lifecycle | **Runtime Manager** | adapter, transport, engine |
| runtime coordination (discovery, matching, health-filter, policy, approval-pause, configure, supervise, telemetry, release) | **Runtime Manager** | adapter, transport, engine |
| provider-specific translation (nine concerns → provider semantics; provider result → Nexus vocabulary) | **Runtime Adapter** | RM core, transport |
| protocol communication (auth, wire streaming, retries, request shaping, wire-normalization, circuit breaker, rate-limit) | **Transport** (adapter-owned, optional) | RM core, adapter-semantics, engine |
| actual execution (driving the Work Package inside the Ready session) | **Execution Engine** | RM, adapter, transport |

**Three overlap risks were checked and resolved** (this is the value of the audit):

1. **Retries / circuit-breaker / rate-limit — Transport vs Recovery.** Transport retries are
   *one call trying to succeed* (provider mechanics, invisible to RM). Cross-attempt retry /
   runtime-switch is **Recovery** (a later phase) reacting to `runtime.failed`. **RM itself
   never retries** (`11` §5). Resolved: no overlap — different scopes (`23` §6).
2. **Normalization — Transport vs Adapter.** Transport does **wire** normalization (protocol
   → provider-family result); Adapter does **semantic** normalization (→ Nexus vocabulary:
   `runtime.output`, artifacts, capabilities). Two stages, one owner each (`22` §3).
3. **Streaming — Transport vs Adapter vs RM.** Transport parses the wire stream into deltas;
   Adapter maps deltas → `runtime.output` (`08`); RM records the event. Clean chain (`23`
   §4). Resolved: no overlap.

**Audit verdict:** terminology, dependency, lifecycle, event, session, allocation, and
observability are consistent across `00`–`24`; every responsibility has exactly one owner;
the three plausible overlaps are explicitly resolved. No contradiction found.

---

## Part B — Readiness Evaluation

### B.1 Architectural completeness
The subsystem is specified end to end: purpose/deps (`00`), RM pipeline (`01`), session
(`02`), adapter (`03`), registry (`04`), capabilities (`05`), selection (`06`), lifecycle
(`07`), streaming/cancel/timeout/error/progress/artifact (`08`–`13`), approvals (`14`),
events (`15`), observability (`16`), security (`17`), governance (`18`), extensibility
(`19`), gaps (`20`), and now taxonomy/layering/transport/compatibility (`21`–`24`). **Complete.**

### B.2 Implementation readiness
Phase 8A (Runtime Core) is **already implemented and green** (`nexus_runtime/`; 469 tests,
100% coverage; full suite passing; mypy --strict; ruff clean) against `00`–`20`. Docs
`21`–`24` add **classification and boundary clarity only** — they impose **no new
implementation obligation** on Runtime Core (adapters/transport are a later phase, explicitly
out of Phase 8A scope). **Ready.**

### B.3 Remaining ambiguities
All are the **known, bounded** gaps in `20` (G-1…G-10) — none introduced or worsened by
`21`–`24`. The transport/gateway formalization actually *closes* latent ambiguity around
where provider protocol logic and gateway routing belong (answer: transport, behind the
adapter). Highest-urgency open items remain G-2 (wording, doc-only) and G-3 (capacity, a
Registry-side extension) — neither blocks Runtime Core.

### B.4 Dependency risks
- Operational (external): a Gateway/Service adds a network/daemon dependency and a second
  trust boundary — an **adapter-phase** concern, contained behind the boundary
  (`docs/runtime/assessment/03`,`04`). Not a Runtime-Core risk.
- Architectural: **none new** — dependency direction unchanged (A.2).

### B.5 Extensibility
The open-closed posture (`19`) now demonstrably covers **four categories and future
providers** (`24` §4): Azure/Vertex → Service, LiteLLM → Gateway, WASM sandbox → Host,
ExecuTorch → in-process Embedded — each a new adapter (+ optional transport) + a
registration, with **zero** upstream change. **Strong.**

### B.6 Operational risks
Concentrated in the **Gateway/Service** categories (heavyweight daemons, free-tier
variance, second credential surface, silent quality downgrade) and fully characterized in
the OmniRoute assessment with binding constraints (no second secret store; loopback bind;
fail-closed; OpenRouter-direct default; record downgrades). These are **adapter-phase
deployment risks**, not architecture risks, and each has a documented mitigation.

---

## Part C — The Six Readiness Questions

**1. Can Runtime Core now be implemented without architectural redesign?**
**Yes — and it already is.** Phase 8A is implemented and green against the frozen `00`–`20`;
`21`–`24` add only classification/boundary clarity and impose no redesign. Remaining work is
engineering (adapters, transport, capacity per G-3), not architecture.

**2. Is every responsibility assigned to exactly one layer?**
**Yes.** RM owns allocation + session lifecycle + coordination; the Adapter owns
provider-specific translation; Transport owns protocol communication; the Execution Engine
owns actual execution (A.8). The three plausible overlaps (retries, normalization,
streaming) are explicitly resolved with distinct scopes.

**3. Does OmniRoute require architectural changes?**
**No.** OmniRoute is a **Gateway transport** (`21` §4, `23` §3) that sits behind a future
LLM Runtime adapter. Adopting it changes no contract, ADR, invariant, lifecycle state, or
event (`docs/runtime/assessment/02`); RM absorbs all its failures via the existing taxonomy
(`assessment/06`). It is APPROVE-WITH-CONSTRAINTS, deferred to the adapter phase — never a
Runtime, never in RM core.

**4. Are Host and Service runtimes equally supported?**
**Yes — through the identical nine-concern adapter contract (`03`).** They differ only in
adapter *translation* and *transport presence* (`22` §4): Host exercises the full lifecycle,
file artifacts, and strong isolation; Service collapses host-shaped concerns and always uses
a transport with result-shaped artifacts. Neither is privileged in RM core; both are
first-class (`24`). Embedded and Gateway are equally accommodated by the same contract.

**5. Are future transports accommodated?**
**Yes.** Transport is an optional, adapter-owned sub-layer (`23`); a new transport (a new
gateway, a new protocol, a remote hop for an otherwise-local runtime) is absorbed behind the
adapter with no RM-core, lifecycle, event, or upstream change (`23` §5, `24` §4, `19`). The
error taxonomy already covers unknown transport faults (`11` §2.4, `23` §6).

**6. Is the execution boundary now fully frozen?**
**Yes.** The boundary — Goal → … → Execution Package → **RM → Adapter → (Transport?) →
Runtime**, with the **Execution Engine performing** what RM prepared — is fully specified
(`22`), every boundary has one owner (A.8), all four runtime categories are classified
(`21`/`24`), and no open gap (`20`) crosses a seam. **The Runtime architecture is
ratified and frozen.**

---

## Conclusion

**The Runtime subsystem is architecturally frozen.** Host, Service, Gateway, and Embedded
runtimes are cleanly supported through one adapter contract with an optional transport, while
Planning, Context Engineering, Orchestration, and Harness remain provider-blind and
untouched. Phase 8A required — and continues to require — **engineering decisions only, not
architectural ones.** Remaining work (adapters, transport implementations, the bounded gaps
in `20`) proceeds without reopening the architecture.
