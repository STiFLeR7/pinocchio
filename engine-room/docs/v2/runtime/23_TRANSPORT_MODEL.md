# 23 — Transport Model

**Status:** design only — architecture ratification. Defines **Transport**: the optional
protocol-communication sub-layer that lives **inside the adapter's provider-aware region**.
Transport is not a new architectural seam — the canon already states "the adapter owns the
transport" (`11` §2.4) and places "SSH/remote transport, vendor SDKs" behind the adapter
(`03` §3). This document formalizes that role and fixes why **Transport is not Runtime**.
It modifies no ADR, contract, or invariant.

OmniRoute is used **only as one worked example** of a gateway transport; nothing here is
designed for OmniRoute specifically.

Read with: `03` (adapter contract), `08` (streaming), `10` (timeouts), `11` (error model),
`21` (taxonomy — Service/Gateway/Embedded need transport), `22` (layering).

---

## 1. What Transport is

**Transport is the protocol plane that carries an already-decided call to an
already-selected runtime.** It moves bytes correctly and resiliently over a wire; it holds
no Nexus semantics and makes no platform decision. It is **optional**: present for Service,
Gateway, and local-server Embedded runtimes; **absent** for Host and in-process Embedded
runtimes, where the adapter drives a local process directly.

> Transport answers *"how do I reach this runtime and get bytes back reliably?"* It never
> answers *"which runtime, what work, or did it succeed?"* — those are RM (`06`), the
> package (`00`), and Validation (INV-20) respectively.

## 2. Transport responsibilities

All of the following live behind the adapter boundary and are invisible to RM core:

| Concern | What Transport does | What it must NOT do |
|---|---|---|
| **Authentication** | attach the credential handed to it *by reference at configure-time* (`17` §3) — bearer token, signed header, mTLS | store, log, or persist a secret; invent a credential |
| **Request shaping** | serialize the adapter's request into the provider's wire format (endpoint, headers, body, params) | change *what* is asked (that is the package/adapter) |
| **Streaming (wire)** | consume the provider's stream (SSE/websocket/chunked) into ordered deltas (`08`) | interpret/grade output; emit `runtime.output` (that is the adapter, `22` §3) |
| **Response (wire) normalization** | coerce provider protocol quirks into a standard provider-family result | map to Nexus vocabulary (adapter's semantic normalization) |
| **Retries** | retry *transient* wire failures (5xx, connection reset, transient 429) within one call | decide cross-attempt retry / runtime-switch (that is Recovery) |
| **Circuit breaking** | open/half-open/close per backend to shed load on a failing provider | remove a runtime from candidacy (that is Registry health, INV-36) |
| **Rate-limit handling** | honor `Retry-After`, classify 429 (rate_limit / quota / transient), back off | decide the session's fate (RM classifies the *surfaced* outcome, `11`) |
| **Timeouts (wire)** | enforce connect/read/idle wire timeouts | own the execution/inactivity *policy* bound (that is Strategy/RM, `10`) |

## 3. Why Transport is NOT Runtime

This is the load-bearing distinction of the whole document.

| Property | **Runtime** (`21`) | **Transport** |
|---|---|---|
| Performs work? | yes — at its execution locus | **no** — it carries a call |
| Has an execution locus? | yes (Host/Service/Embedded) | **no** — it is a conduit |
| Owns a Runtime Session? | it is *bound into* one (`02`) | **no** — it holds no session |
| Emits artifacts as Evidence Candidates? | yes (`13`) | **no** — it relays bytes the adapter turns into candidates |
| Advertised as a `RUNTIME` descriptor? | yes (`04`, ADR-002) | **no** — it is a property of *how* a runtime is reached |
| Visible to RM core? | as a capability-matched candidate | **never** — it is provider mechanics (`03` §1) |
| Litmus (`03` §6) | may change *where/how* work is hosted | may only change *how bytes travel*; never *what runs or whether it succeeded* |

A **gateway** (OmniRoute, LiteLLM) is a *multiplexing* transport — the same conduit whose
downstream is several Services with routing/fallback among them. It is emphatically not a
Runtime, a Runtime Manager, an Orchestrator, or a Harness (`21` §4): it executes nothing,
allocates nothing, plans nothing, compiles nothing. Its routing is a *transport* decision
over an already-decided call, made behind the adapter, invisible to RM.

## 4. Transport ⇄ adapter ⇄ RM (the clean handoffs)

```
 RM core ──(nine-concern contract, 03)──▶ Adapter ──(provider request)──▶ Transport ──(wire)──▶ Runtime
    ▲                                        │                                │
    │  runtime.* events (15)                 │ semantic-normalize            │ wire-normalize
    │  session projection (02, ADR-001)      │ (→ Nexus vocabulary)          │ (→ provider-family result)
    └────────────────────────────────────────┴────────────────────────────────┘
                         RM never sees the transport; the adapter never sees the wire
```

- **Adapter → Transport:** hands a provider-shaped request + an injected credential
  reference; asks for a normalized provider result / stream.
- **Transport → Adapter:** returns wire-normalized bytes (deltas, a standard result, or a
  typed transport failure); it decides nothing about session state.
- **Adapter → RM:** turns that into `runtime.output`, artifacts (`13`), capability facts
  (`05`), and a lifecycle-projecting status (`07`). RM records canonical `runtime.*` events.

## 5. When Transport is absent

| Runtime shape (`21`) | Transport? | Adapter drives… |
|---|---|---|
| Host (Shell/Docker/Python/Browser/Claude Code/Gemini CLI) | **no** | a local process/container/session/daemon socket directly |
| Embedded in-process (llama.cpp/ExecuTorch/GGUF) | **no** | an in-memory model (load → infer) |
| Service (OpenAI/Anthropic/OpenRouter/Azure/Vertex) | **yes** | an HTTPS API over the network |
| Gateway → Service (OmniRoute/LiteLLM) | **yes (multiplexing)** | a local/remote gateway fronting many Services |
| Embedded local-server (Ollama/LM Studio) | **yes (loopback)** | a local HTTP inference server on loopback |

The presence/absence of transport is a **property the adapter knows**, never something RM
core branches on. "Needs transport" in the compatibility matrix (`24`) is descriptive, not a
switch in RM.

## 6. Error, timeout, and failure alignment (`11`, `10`)

Transport faults map onto the **existing** provider-independent taxonomy — no new class:

| Transport event | RM error class (`11`) | Notes |
|---|---|---|
| connection refused / DNS / TLS at start | execution-startup-failure | adapter-surfaced → RM-classified |
| socket/stream collapse mid-call | transport-failure (`11` §2.4) | already a canonical class |
| provider 5xx / crash after retries exhausted | provider-failure | provider is the origin |
| 429 rate_limit / quota_exhausted after backoff | provider-failure (or timeout via `10`) | classification detail rides in `detail` |
| wire timeout elapsed | timeout (`10`) | → `Cancelled` or `Failed` → `Destroyed` |
| gateway silent downgrade (200, weaker backend) | *not an error* — recorded as execution-metadata (`13`) | no-silent-default; auditable |

Transport-internal resilience (retries, breaker, fallback) is **one call trying to
succeed** — it is *not* Nexus Recovery. RM sees only the final outcome after transport has
exhausted its internal attempts, classifies it (`11`), emits `runtime.failed`, and hands off
to Recovery (a later phase). This preserves the canon that **RM does not retry** (`11` §5).

## 7. Security (`17`)

- Credentials reach Transport **by injected reference at configure-time** (`17` §3); the
  value lives only in `.env`; Transport never persists or logs it.
- A **gateway's own credential store** (e.g. OmniRoute's encrypted sqlite) must not become a
  second secret store — restrict to no-key backends or strict BYOK pass-through so provider
  keys stay in `.env` (`17` §1; OmniRoute assessment `04`).
- Wire streams and responses are subject to secret **redaction** at the capture edge
  (`17` §6) before becoming `runtime.output`/artifacts.
- **Fail-closed** (`17` §1.4): an unreachable/unauthenticated transport **refuses** the
  session; it never falls through to an unauthenticated call.

## 8. Cross-references

`03` (adapter owns transport; provider mechanics) · `08` (stream events transport carries) ·
`10` (timeout bounds vs wire timeouts) · `11` (transport-failure and the taxonomy) ·
`17` (credential-by-reference, redaction, fail-closed) · `21` (which categories need
transport) · `22` (the two normalizations; layering) · `docs/runtime/assessment/` (OmniRoute
as a worked gateway-transport example).
