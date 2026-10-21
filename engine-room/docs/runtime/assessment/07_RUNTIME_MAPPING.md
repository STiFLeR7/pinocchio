# 07 — Runtime Adapter Mapping (conceptual)

Architecture only — **no code**. Shows how OmniRoute would sit under a hypothetical,
Nexus-authored **LLM Runtime adapter**, and how the frozen chain RM → Runtime Session →
Adapter → backend → provider maps onto OmniRoute's concrete surface. This is the "if we ever
did it" design, deferred to a later adapter phase (Phase 8A defers all adapters).

## 1. The mapping

```
   Runtime Manager (RM core, generic)                        [01, generic — no OmniRoute here]
        │  selects + allocates by capability (INV-32/37)
        ▼
   Runtime Session  (binds package ⇄ allocated runtime)      [02]
        │  Ready → handed to Execution Engine (later phase)
        ▼
   ┌───────────────────────────────────────────────────────────────────────┐
   │  LLM Runtime Adapter  (Nexus-authored, the ONLY provider-aware code)    │  [03]
   │   • concern A: advertise abstract caps  ← translate /v1/models catalog   │
   │   • concern B: configure                ← model id, token(ref), params   │
   │   • concern C: start                    ← construct client (no host)     │
   │   • concern D: stream                   ← consume SSE, emit runtime.output│
   │   • concern F: emit artifacts           ← completion + usage → candidate  │
   │   • concern G: cancel/timeout           ← AbortController / timeouts       │
   │   • concern H: terminal status          ← request-end → Completed/Failed  │
   │   • concern I: cleanup                  ← close socket; scrub token(ref)   │
   └───────────────────────────────────────────────────────────────────────┘
        │  OpenAI-compatible HTTP (the stable seam)
        ▼
   OmniRoute  (local gateway daemon, provider mechanics)     [D:/_eval/OmniRoute]
        │  POST /v1/chat/completions · GET /v1/models · SSE
        │  internal: routing (ts/bifrost), 429 classify, breaker, tier fallback
        ▼
   Provider  (OpenRouter / keyed provider / no-auth free upstream)
```

The provider-aware region is a **single bounded box** (`00` §4, `03` §3): the LLM Runtime
adapter. OmniRoute is the transport *inside* that box; RM core above it is untouched.

## 2. Concern-by-concern realization

| Concern (`03` §2) | Adapter action | OmniRoute surface used |
|---|---|---|
| A advertise | translate model catalog → abstract Capability refs (INV-32); advertise `tool_use` only where truly backed (`05`) | `GET /v1/models` (`catalog.ts`): id, provider, `context_length`, `capabilities`, `pricing` |
| B configure | render model id, params, and the token as an **injected reference** from `.env` (`17` §3) | request body + `Authorization` bearer |
| C start | construct/validate an HTTP client + reachability check (there is no process to spawn) | `GET /api/health/ping` (liveness) |
| D stream | consume SSE deltas, emit `runtime.output` (`08`); redact echoed secrets (`17` §6) | `text/event-stream`, `[DONE]` (`sseParser.ts`) |
| E progress | emit `runtime.progress` = **unknown** (no task-progress signal); tokens are liveness only | SSE heartbeat / delta arrival |
| F artifacts | completion text → structured-output candidate; `usage` + served provider/model/latency → execution-metadata candidate (`13`), by reference | body `usage{…}`, `X-OmniRoute-Provider/-Model/-Latency-Ms/-Cost` |
| G cancel/timeout | forward RM cancel; enforce Strategy timeouts | `AbortController`/`signal`; `*_TIMEOUT_MS` |
| H terminal status | request-end → `Completed` (process/request ended ≠ validated, INV-20); error → classified `Failed` (`11`) | HTTP status + `classify429` result |
| I cleanup | close connection; scrub injected token reference; no workspace to remove | socket close |

## 3. What maps trivially, what is vestigial

- **Trivial:** D (stream), G (cancel/timeout), H (status), F-partial (result + usage as
  candidates), A (via catalog translation).
- **Vestigial (collapses for a stateless backend):** C (no host to start), E (no real
  progress), I (nothing to tear down but a socket), and the whole of `17` §2's
  filesystem/process isolation (there is none — network posture only).

This vestigiality is the mapping-level restatement of the altitude finding: OmniRoute fills
the *transport* concerns and no-ops the *host* concerns.

## 4. Capability & selection flow (unchanged, `05`/`06`)

1. Orchestration emits `required_capability_refs` + `candidate_harness_refs` by capability
   (INV-37) — never "OmniRoute".
2. The LLM Runtime descriptor (registered via `04`) advertises abstract capabilities
   translated from OmniRoute's catalog.
3. RM matches (`05`), health-filters (Registry, INV-36 — health from `/api/health/ping`
   surfaced onto the descriptor), policy-filters (`18`), selects + allocates (`06`)
   deterministically.
4. A Runtime Session (`02`) binds the package to the allocated LLM runtime; driven to
   `Ready`; handed off. **Every step is the existing machinery** — OmniRoute changed none of
   it.

## 5. Multi-adapter coexistence (`19` §6)

An OmniRoute-backed LLM runtime coexists with a direct-OpenRouter LLM runtime as **two
descriptors advertising the same capabilities** — the normal many-providers-one-capability
case. Policy/preference (`06`, `18`) steers selection (e.g. prefer direct-OpenRouter, fall
to OmniRoute). Retiring OmniRoute is a Registry deregistration — nothing upstream breaks.
This is the clean way to keep OpenRouter-direct as default while OmniRoute is optional.

## 6. Verdict for this doc

**Mappable, cleanly, with no change to RM core, the Session, the lifecycle, or the events.**
OmniRoute sits as transport inside a future LLM Runtime adapter; the host-shaped concerns go
vestigial, the transport-shaped concerns map directly, and selection/coexistence use the
existing funnel. This is the *design that would be built later* — not now, and not as a
Runtime in its own right.
