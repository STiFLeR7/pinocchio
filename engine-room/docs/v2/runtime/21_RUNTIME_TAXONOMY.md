# 21 — Runtime Taxonomy

**Status:** design only — architecture ratification. Defines the **classification of
runtimes** the Runtime Manager (RM) must support, so that Host, Service, Gateway, and
Embedded runtimes are all first-class through the **same** adapter contract (`03`) with **no
change** to RM core, the lifecycle (`07`), the events (`15`), or any upstream layer
(`19`). This document **modifies no ADR, contract, or invariant**; it is a lens over the
existing canon ("a Runtime is a Harness of category `RUNTIME`", `00` §7, ADR-002).

Read with: `03_RUNTIME_ADAPTERS.md` (the one contract every category satisfies),
`22_RUNTIME_LAYERING.md` (where each sits on the execution boundary),
`23_TRANSPORT_MODEL.md` (the optional protocol sub-layer), `24_RUNTIME_COMPATIBILITY.md`
(the classification matrix).

---

## 1. Two orthogonal axes (the key to the taxonomy)

The four categories are not four peers on one axis. They are two independent questions:

- **Execution locus — *where the work actually happens.*** Three answers: **Host** (this
  machine), **Service** (a remote provider), **Embedded** (in-process / on-device).
- **Path shape — *how RM reaches that locus.*** Direct (adapter only), through a
  **transport** (a protocol sub-layer, `23`), or through a **gateway** (a *multiplexing*
  transport fronting several Services).

**Gateway is a path shape, not an execution locus.** A gateway executes nothing; it is a
transport topology. It is enumerated as a fourth "runtime category" because operators think
of it as one, but architecturally it lives on the Transport layer (`23`), never on the
execution plane. This is precisely *why it occupies a distinct role* (§4).

> Every category is driven through the identical nine-concern adapter contract (`03` §2).
> The taxonomy changes **what the adapter translates to**, never **what RM asks of the
> adapter.** That invariance is the reason all four are first-class without redesign.

## 2. Host Runtime

**Definition.** A runtime that **executes work directly on the local machine** — the
execution locus is *here*. RM (via the adapter) starts a real local process/container/
session and drives the Work Package inside it.

**Examples.** Claude Code, Gemini CLI, Shell, Docker, Python, Browser automation.

**Characteristics.**
- Has a **startable host with a lifetime** — the full lifecycle (`07`) applies with weight
  (real `Created→Prepared→Ready→Running→…→Destroyed`).
- Owns a **filesystem workspace** and emits **file artifacts** (`13`) as Evidence
  Candidates.
- Carries the **strongest isolation profiles** (`17` §2: OS process, container namespaces,
  ephemeral browser profile).
- **Usually needs no transport** — the adapter drives a local process/socket directly
  (`23` §5). (Any local daemon socket, e.g. the Docker API, is adapter-internal host
  mechanics, not a Nexus Transport.)
- All nine adapter concerns (`03` §2) are **materially exercised**, including Start (C),
  isolation Configure (B), file-artifact Emit (F), and Clean up (I).

## 3. Service Runtime

**Definition.** A runtime that **delegates execution to a remote service** over a network
API — the execution locus is *elsewhere, on someone else's infrastructure*. Nexus sends a
request and consumes a response/stream; it hosts nothing.

**Examples.** OpenAI, Anthropic, OpenRouter, Azure OpenAI, Vertex AI.

**Characteristics.**
- **No local host to start** — Start (C) collapses to "construct/validate a client";
  Clean up (I) is "close the connection." (`01_COMPATIBILITY` of the OmniRoute assessment
  describes this vestigiality for the LLM-service case.)
- **Always needs a transport** (`23`): HTTPS, auth, retries, streaming, request shaping,
  response normalization, rate-limit/circuit-breaker handling.
- Artifacts (F) are **result-shaped**, not file-shaped: the completion/response as
  structured-output, plus `usage`/latency/served-model as execution-metadata (`13`).
- Isolation (`17`) is **network posture only** — there is no filesystem/process sandbox;
  least-privilege is expressed as scoped credentials + declared egress.
- Secrets (API keys) reach it **by injected reference at configure-time** from `.env`
  (`17` §3) — never persisted outside `.env`.
- OpenRouter note: it is itself a *hosted gateway/router*, but Nexus consumes it **as a
  Service** — its routing is remote and opaque, behind one endpoint. The gateway-ness is
  not Nexus's transport concern (contrast §4, a *local* gateway).

## 4. Gateway Runtime (a transport topology, not an execution locus)

**Definition.** A **multiplexing transport that sits between Nexus and one or more Service
Runtimes**, presenting a unified (typically OpenAI-compatible) surface and routing/failing
over among backends. **It executes no work of its own.**

**Examples.** OmniRoute, LiteLLM, OpenWebUI-compatible gateways, future provider routers.

**Why it occupies a distinct architectural role.** A gateway is deliberately fenced off
from three roles it superficially resembles:

| A gateway is **NOT** a… | Because… |
|---|---|
| **Runtime Manager** | RM owns allocation, session lifecycle, and coordination (`00` §5). A gateway owns none of these; it routes bytes. RM decides *which* runtime; a gateway only *reaches* one. |
| **Orchestrator** | Orchestration produces capability-based candidates (INV-37). A gateway makes provider-level routing choices *behind the adapter*, invisible to RM, over an *already-decided* call — it changes *where a call lands*, never *what runs or whether it succeeded* (`03` §6 litmus). |
| **Harness** | The Harness compiles the immutable Execution Package. A gateway compiles nothing and holds no package. |

Architecturally, therefore, a Gateway is realized on the **Transport layer** (`23`): it is
a *transport variant* whose downstream is several Services rather than one. A
"Gateway Runtime" descriptor is what an adapter advertises when its transport is a gateway;
the **execution locus is still Service** (the model that ultimately answers). RM sees only
the adapter contract and never learns a gateway is involved.

**Characteristics.**
- **Is** the transport (`23`) — it *is* what "needs transport" points at.
- Adds provider **breadth + resilience** (routing, fallback tiers, circuit breakers,
  429 classification) entirely **behind the adapter** — provider mechanics RM never sees
  (`06_FAILURE_MODES` of the OmniRoute assessment §3).
- Can **silently downgrade** quality (fall to a weaker backend and still return `200`);
  the adapter must record the actually-served backend as execution-metadata so the
  downgrade is auditable, not hidden (no-silent-default).
- Introduces its own **trust boundary and (often) a second credential surface** — which
  must not become a second secret store (`17` §1; OmniRoute assessment `04`).

## 5. Embedded Runtime

**Definition.** A runtime that performs **inference on-device**, either **in-process**
(linked library) or via a **local inference server** — the execution locus is *this
machine*, but the "work" is model inference, not a spawned task process.

**Examples.** llama.cpp, Ollama, LM Studio, ExecuTorch, GGUF inference, future on-device
runtimes.

**How it differs from Host and Service.**

| Axis | Host | Service | **Embedded** |
|---|---|---|---|
| Execution locus | local machine | remote provider | **local machine (on-device)** |
| What executes | a task process/container/session | a remote request | **local model inference** |
| Transport | usually none (local process) | always (network) | **in-process → none; local-server → loopback transport** |
| Artifacts | files + logs | result + usage | **result + usage (like Service), no filesystem workspace** |
| Isolation (`17`) | OS/container/browser sandbox | network posture only | **process/memory bound; no network egress by default (a security *positive*)** |
| Credentials | scoped local creds | remote API key (`.env`) | **usually none — no external key** |
| Cost | local compute | per-token billing | **local compute only (no per-call cost)** |

**Key distinctions.**
- It is **locally hosted like a Host runtime** but its output is **result-shaped like a
  Service runtime** — it straddles the two, which is exactly why it warrants its own
  category rather than being forced into either.
- **Two sub-forms:** *in-process* (llama.cpp/ExecuTorch linked — no transport, Start (C)
  = load model into memory) and *local-server* (Ollama/LM Studio — reached over a
  **loopback** transport, `23`, but still on-device).
- **No external network and typically no credential** → the strongest *privacy* posture
  and no `.env` secret at all for the no-key case. Least-privilege (`17` §4) is naturally
  satisfied.
- Health/availability (INV-36) is **local resource pressure** (VRAM/RAM/model loaded), not
  a remote status — surfaced onto the descriptor exactly like any other health signal.

## 6. The taxonomy on one page

| Category | Execution locus | Path shape | Startable host? | Artifacts | Transport (`23`) | Secrets |
|---|---|---|---|---|---|---|
| **Host** | local machine | direct | yes (process/container/session) | files + logs | usually none | scoped local |
| **Service** | remote provider | transport | no (client only) | result + usage | always (network) | API key via `.env` ref |
| **Gateway** | *none* (fronts Services) | **is the transport** | no | pass-through of Service | it *is* transport (multiplexing) | gateway token via `.env` ref; must not store keys |
| **Embedded** | local machine (on-device) | in-process or loopback | in-process: load model; server: no | result + usage | in-process none / server loopback | usually none |

## 7. What the taxonomy guarantees

- **One contract, four categories.** Each is driven through the same nine adapter concerns
  (`03` §2); the category only changes the adapter's *translation target*, never RM's
  requests. New categories join by the open-closed rule (`19`): a new adapter + a Registry
  registration, no upstream change.
- **No new lifecycle/event/dependency.** Nothing here adds a state (`07`), an event
  (`15`), or a dependency edge (`00` §4). Gateway/Transport are refinements *inside* the
  adapter's provider-aware region — where transport already lived in the canon (`11` §2.4,
  `03` §3).
- **Provider-blind upstream preserved.** Planning/Context/Orchestration/Harness still speak
  only capabilities (INV-21/32/37); none of them can tell a Host from a Service from a
  Gateway from an Embedded runtime — by construction.

## 8. Cross-references

`00` (canon glossary, dependency direction) · `03` (the one adapter contract) ·
`04`/`05` (registry & capability advertisement per category) · `17` (per-category
isolation & secrets) · `19` (adding a category without upstream change) ·
`22` (layering) · `23` (transport / gateway realization) · `24` (compatibility matrix) ·
`docs/runtime/assessment/` (OmniRoute — the worked Gateway example).
