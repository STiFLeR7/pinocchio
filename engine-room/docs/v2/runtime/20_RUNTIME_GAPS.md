# 20 — Runtime Gaps

**Status:** design only. An honest enumeration of what is **not yet fully settled** in
the Runtime Manager (RM) architecture — open questions and **deferred decisions** to be
resolved before or within implementation. These are **known and bounded**: none of them
contradicts the canon (`00`/`01`/`02`/`07`/`15`) or undermines the architecture's
soundness. They are recorded here so a future implementation team makes no *new*
architectural decision by accident, and so reviewers can see exactly where the edges
are. This document **modifies no ADR, contract, or invariant**; where a clarification
is recommended, it points to `ARCHITECTURE_REVIEW.md`.

---

## 1. How to read this list

Each gap is: a **1–2 line statement** of what is unsettled, an **urgency**
(low / med / high) for resolving it, and a **recommended resolution direction**.
Urgency is about *when* it must be settled relative to building RM — not about how
hard or risky it is. Several gaps deliberately **mirror Phase-5 observations**
(O-7/O-8/O-10/O-11) because RM faces the same structural questions one layer down.

---

## 2. The gaps

### G-1 — Should Runtime Session / Runtime allocation be FROZEN core contracts?
**Statement.** The Runtime Session (`02`) and the allocation record (`06`) are today
**runtime-layer value objects**, with no frozen `nexus_core` contract — exactly as the
Orchestration Execution Session is a Phase-5 output (`02` §1 notes this mirrors
Phase-5 **O-7**; allocation mirrors **O-10**).
**Urgency:** med.
**Direction.** Keep them as runtime-layer value objects for the first implementation;
only promote to a frozen core contract if a *second* subsystem (Execution Engine,
Supervision) must depend on their shape. Record the call in `ARCHITECTURE_REVIEW.md`;
do not pre-freeze.

### G-2 — "Orchestration assigns runtimes" (doc-07 wording) vs "RM allocates"
**Statement.** The canon is that Orchestration produces **candidates** and RM performs
the **final selection + allocation** (INV-37, `06`); some upstream doc-07 phrasing reads
as "Orchestration assigns runtimes," creating a wording tension, not a logic one.
**Urgency:** high (it is a definitional ambiguity that confuses ownership).
**Direction.** Do **not** change the ADR here. Resolve the wording in
`ARCHITECTURE_REVIEW.md`: Orchestration *nominates* (candidates); RM *allocates*. The
runtime canon already takes the INV-37 reading; the upstream phrasing should be aligned
to it.

### G-3 — Concurrency / capacity model (sessions per runtime, pooling, quotas)
**Statement.** How many concurrent sessions a single runtime may host, and whether
runtimes are pooled or quota-limited, is **flagged but not designed**. Allocation today
reasons over a Registry snapshot, not over live capacity.
**Urgency:** high (real deployments need back-pressure to avoid over-allocation).
**Direction.** Treat capacity as a Registry/availability concern (INV-36 owns
availability; `ResourceAvailability` already includes `busy`/`reserved`). Design a
capacity/quota model as an extension of the Registry view, not as new RM-owned state.
Until then, model one-session-per-runtime conservatively.

### G-4 — Checkpoint / resume depth (which runtimes truly support resume)
**Statement.** The session model makes resume *expressible* (`02` §6–7), but which
runtime categories can *genuinely* resume from a checkpoint (vs only restart) is
undecided — Docker/Browser/remote differ sharply from a stateless Shell.
**Urgency:** med.
**Direction.** Make resume an **adapter-declared capability** (`05`/`03`): a runtime
advertises whether it supports checkpoint-resume; RM exposes the checkpoint reference
only to capable adapters and otherwise restarts cold. Recovery/Strategy decides *use*;
RM remains the mechanism.

### G-5 — Streaming backpressure & persistence limits
**Statement.** The streaming model (`08`) defines runtime-independent stream events, but
backpressure (a runtime out-producing the sink) and how much stream is retained/
persisted are not bounded.
**Urgency:** med.
**Direction.** Define stream events as bounded/throttleable with a documented retention
limit; treat dropped *stream* samples like dropped *observability* (`16`) — lossy, never
state-corrupting, since output that matters is also captured as referenced artifacts
(`13`). Persistence depth is a Phase-2-substrate tuning decision, not an RM contract.

### G-6 — Multi-node / distributed RM
**Statement.** The design assumes a single logical RM control plane; running multiple RM
instances (HA, sharding by correlation) and how allocations stay consistent across them
is **not designed**.
**Urgency:** low (single-node is sufficient for the first implementation).
**Direction.** Lean on deterministic identifiers (`02` §3) and idempotent event
consumption (INV-16): allocation is event-sourced, so a distributed RM is a *later*
consistency problem over the same log, not a redesign. Defer until horizontal scale is
an actual requirement.

### G-7 — How Supervision (future) intervenes vs RM
**Statement.** RM emits the facts and derived health (`16`), but the boundary between
**Supervision recommending** an intervention (`OperationalHealth`,
`InterventionRecommendation`, INV-23) and **RM enacting** a control transition
(`pause/resume/cancel`, `07`/`09`) is sketched, not specified.
**Urgency:** med.
**Direction.** Hold the canonical split: Supervision **recommends** (it owns no
lifecycle transition); RM **enacts** the control transitions it already owns, on a
Supervision signal, exactly as it does for governance/approval (`14`). Specify the
signal seam when the Supervision phase lands.

### G-8 — Cost accounting: source of truth
**Statement.** Policy may impose a **cost ceiling** (`18`, pipeline step 5), but where
authoritative cost figures come from (adapter-reported, provider billing, derived
metrics) is undecided. Derived metrics (`16`) are explicitly *not* authoritative.
**Urgency:** med.
**Direction.** Cost facts must enter as **events** (adapter-reported usage on the
`runtime.*` log), never as observability metrics, so cost is auditable and replayable.
Treat the `16` cost figures as derived *views* only; define a cost-event source before
enforcing a hard ceiling.

### G-9 — Should a dedicated Registry phase own the concrete registries?
**Statement.** RM consumes the Registry as a `RUNTIME`-category **view** over the
existing Harness Registry (`04`, INV-36) and invents no second store; whether a
dedicated Registry phase should own the *concrete* registries is open (mirrors Phase-5
**O-8** / **O-11**).
**Urgency:** low.
**Direction.** Keep the view-only stance for RM (it owns no registry). If the concrete
registries need a home of their own, that is a **separate phase's** decision; record the
observation in `ARCHITECTURE_REVIEW.md`, do not absorb it into RM.

### G-10 — Health-probe ownership vs Registry-owned health
**Statement.** RM **may probe** a runtime via the adapter (`01` §2.4, `16` §6) while the
Registry **owns** health/availability (INV-36); the exact rule for when a probe result
may inform RM's filtering without becoming a competing health state needs nailing down.
**Urgency:** low.
**Direction.** Treat every probe result as a **read-only reading** surfaced as a derived
observation; it may *trigger* a re-read of Registry health but never *override* it. RM
writes no health record. Document this as the binding rule in implementation.

---

## 3. Gap summary

| ID | Gap | Urgency | Mirrors |
|---|---|---|---|
| G-1 | Freeze Session / allocation as core contracts? | med | Phase-5 O-7 / O-10 |
| G-2 | "Orchestration assigns" vs "RM allocates" wording | high | — |
| G-3 | Concurrency / capacity / pooling / quotas | high | — |
| G-4 | Checkpoint / resume depth per runtime | med | — |
| G-5 | Streaming backpressure & persistence limits | med | — |
| G-6 | Multi-node / distributed RM | low | — |
| G-7 | Supervision intervention vs RM enactment | med | — |
| G-8 | Cost accounting source of truth | med | — |
| G-9 | Dedicated Registry phase for concrete registries | low | Phase-5 O-8 / O-11 |
| G-10 | Health-probe reading vs Registry-owned health | low | — |

## 4. Why these are not blockers

Every gap above sits **inside** the existing seams, not across them:

- None requires a new lifecycle state (`07`), a new event (`15`), or a new dependency
  direction (`00`). They are refinements of *policy*, *capacity*, *wording*, or *future
  phases* — the architecture's spine (RM prepares & supervises; the engine performs) is
  untouched.
- The two **high-urgency** items (G-2 wording, G-3 capacity) are a documentation
  alignment and a Registry-side extension respectively — both resolvable without
  reopening any ADR.
- The deferred-contract questions (G-1, G-9) are deliberately *postponed*, mirroring how
  Phase 5 left its analogous observations open: promote to a frozen contract only when a
  second consumer demands the shape, never speculatively.

These are the **known edges** of a sound design. Listing them honestly is what keeps the
implementation team from rediscovering them as surprises — and keeps the canon from
being quietly contradicted to paper over an open question.
