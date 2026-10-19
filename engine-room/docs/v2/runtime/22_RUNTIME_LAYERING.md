# 22 — Runtime Layering

**Status:** design only — architecture ratification. Illustrates the **complete execution
boundary** end to end and fixes the responsibility of **every** boundary, so that no two
layers share a responsibility and no responsibility is unassigned. Adds no state, event, or
dependency edge; formalizes the **Transport** sub-layer that already lived behind the
adapter in the canon (`11` §2.4 "the adapter owns the transport"; `03` §3).

Read with: `00` (dependency direction), `01` (RM pipeline), `03` (adapter contract),
`21` (taxonomy), `23` (transport model).

---

## 1. The full stack (preparation path + execution path)

```
   Goal
     │  intent
     ▼
   Context Engineering ── assembles the immutable Context View (capabilities/knowledge)
     │
     ▼
   Planning ─────────── decomposes into Work Packages (INV-21: never names a runtime)
     │
     ▼
   Orchestration ────── Execution Graph + Strategy; RuntimeRequest with capability-based
     │                  candidates (INV-37), never provider names
     ▼
   Harness ──────────── compiles the immutable Execution Package + Manifest
     │
     ▼
   Execution Package ── the authority on WHAT to run (capability-shaped)
     │
     ▼
 ┌────────────────────────── nexus_runtime (provider-aware only below RM core) ──────────┐
 │ Runtime Manager ── discover · match caps · filter health · policy · approve · SELECT   │
 │  (RM CORE,          + ALLOCATE · create Runtime Session · configure · drive to Ready · │
 │   generic)          supervise · collect artifacts · telemetry · release · destroy      │
 │     │  drives generically via the ONE adapter contract (03)                            │
 │     ▼                                                                                  │
 │ Runtime Adapter ── PROVIDER-SPECIFIC TRANSLATION of the nine concerns (03 §2):         │
 │  (provider-aware)   config→provider setup, result→runtime.output/artifacts,            │
 │     │               provider caps→abstract caps, control signals→provider mechanics    │
 │     ▼                                                                                  │
 │ Transport ──────── OPTIONAL protocol communication (23): auth, wire streaming, retries,│
 │  (optional,         request shaping, response (wire) normalization, circuit breakers,  │
 │   adapter-owned)    rate-limit handling. Absent for local Host/in-process Embedded.    │
 │     │                                                                                  │
 └─────┼──────────────────────────────────────────────────────────────────────────────── ┘
       ▼
   Runtime ─────────── the integration boundary that performs work (Host / Service /
     │                 Gateway-fronted Service / Embedded) — a RUNTIME Harness (ADR-002)
     ▼
   Execution Engine ── DRIVES the Work Package inside the Ready session and PERFORMS it
                       (Phase 8, downstream) — RM prepared; the Engine performs
```

Two arrows through the same stack: **RM prepares** *down to* `Ready` (owning the session
throughout), then the **Execution Engine performs** *through* the adapter/transport into the
runtime. The Engine does not sit "beneath" the runtime in dependency terms — it drives
across the adapter boundary after RM's handoff (`00` §1: "RM prepares; the Engine performs").

## 2. Responsibility of every boundary (exactly one owner each)

| Boundary | Owns (sole responsibility) | Explicitly does NOT own |
|---|---|---|
| **Context Engineering** | the immutable Context View (operational understanding) | planning, runtime choice |
| **Planning** | Work Package decomposition | runtime selection (INV-21) |
| **Orchestration** | Execution Graph + Strategy; capability-based **candidates** (INV-37) | final selection/allocation; provider names |
| **Harness** | the immutable Execution Package + Manifest | execution; runtime choice |
| **Execution Package** | the authoritative statement of *what to run* (capability-shaped) | *how/where* it runs |
| **Runtime Manager (core)** | **allocation**, **session lifecycle**, **runtime coordination** (discovery, matching, health-filter, policy, approval-pause, configure, supervise, telemetry, release) | provider specifics; performing work; validation; recovery |
| **Runtime Adapter** | **provider-specific translation** of the nine concerns (`03` §2) | deciding *which* runtime (selection); *when* to cancel/retry; grading results |
| **Transport** (optional) | **protocol communication** (`23`): auth, wire streaming, retries, request shaping, wire-normalization, circuit breaker, rate-limit handling | semantic meaning of the payload; Nexus vocabulary; selection/validation/recovery |
| **Runtime** | performing the Work Package at its execution locus (`21`) | selecting itself (INV-21); declaring itself validated (INV-20) |
| **Execution Engine** | **actual execution** — driving the Work Package inside the Ready session | preparation (RM's); validation (Validation's); recovery (Recovery's) |

## 3. The two normalizations (the boundary that is easy to blur)

"Normalization" appears at two layers and must not overlap:

- **Transport does *wire* normalization** — turns provider protocol reality into a clean,
  provider-*family* result: parse SSE into deltas, coerce a provider's JSON quirks into a
  standard (e.g. OpenAI-shaped) response, retry transient 5xx, honor rate-limit headers.
  It produces *a normalized provider result*, still in provider vocabulary.
- **Adapter does *semantic* normalization** — maps that normalized provider result into
  **Nexus vocabulary**: `runtime.output` stream events (`08`), Evidence-Candidate artifacts
  (`13`), abstract capability satisfaction (`05`), lifecycle-projecting status (`07`).

So a stream flows: runtime → **transport** (wire → deltas) → **adapter** (deltas →
`runtime.output`) → RM (record as event). No layer repeats another's work.

## 4. Where the taxonomy (`21`) changes the picture — and where it does not

| Category | Transport present? | Start (C) weight | Artifacts (F) | Lifecycle (`07`) weight |
|---|---|---|---|---|
| **Host** | no (local process) | full (spawn/launch) | files + logs | full |
| **Service** | **yes** (network) | client construct only | result + usage | collapses toward execution states |
| **Gateway** → Service | **yes** (multiplexing transport) | client construct only | Service pass-through | collapses; downgrades recorded as metadata |
| **Embedded** (in-process) | no | load model | result + usage | partial |
| **Embedded** (local server) | **yes** (loopback) | client construct only | result + usage | partial |

What **never** changes across the rows: the RM-core column (allocation, session, coordination)
and the adapter *contract* (the nine concerns). Only the adapter's *translation* and the
*presence of transport* vary — exactly the invariance `03` §4 and `21` §7 promise.

## 5. Dependency direction is unchanged (`00` §4)

```
nexus_runtime → { nexus_core, nexus_infra }     (still the only imports)
```

Transport and Gateway add **no** new dependency edge and **no** upstream import: they live
strictly inside `nexus_runtime`, behind the adapter boundary, in the single provider-aware
region (`00` §4, `03` §3). Nothing upstream can reference them. RM core still imports no
adapter, no transport, and branches on no provider (`03` §3 litmus). The layering refines
*within* the existing spine; it does not bend it.

## 6. One-paragraph mental model

The stack is provider-blind from Goal to Execution Package (capabilities only), then RM core
selects and allocates one runtime and owns its session generically, then a single
provider-aware region translates: the **adapter** speaks the provider's semantics and, when
the runtime is remote or served, an optional **transport** speaks the provider's protocol.
Below that is the runtime itself — Host, Service, Gateway-fronted Service, or Embedded — and
the **Execution Engine** drives the work inside the Ready session RM prepared. Every
responsibility has exactly one owner; the only layers that ever know a provider exists are
the adapter and its optional transport.
