# 01 — Compatibility

Maps OmniRoute's actual surface onto the frozen Runtime Adapter contract
(`03_RUNTIME_ADAPTERS.md` §2, the nine concerns A–I) and the Runtime/Session/Lifecycle
model (`00`, `02`, `07`). The conclusion is a **structural altitude mismatch**, not a
feature gap.

## 1. The nine adapter concerns vs. what OmniRoute offers

The adapter contract is written for a runtime that *hosts and runs a Work Package*
(INV-09). OmniRoute hosts nothing and runs no Work Package — it answers an HTTP
chat-completions call. Concern-by-concern:

| # | Adapter concern (`03` §2) | OmniRoute reality (source) | Fit |
|---|---|---|---|
| A | **Advertise capabilities** — publish a Runtime Descriptor of abstract capabilities (`04`/`05`) | `GET /v1/models` (`src/app/api/v1/models/route.ts`, `catalog.ts`) lists models with `provider`, `context_length`, `capabilities{vision,tool_calling}`, `pricing`. These are *model* attributes, not abstract Nexus Capabilities (INV-32) | **Partial** — needs an adapter to translate model attrs → abstract capabilities |
| B | **Configure** — accept RM's rendered config (env, working dir, resource limits, isolation profile, injected secret *references*) | OmniRoute takes an HTTP request body + bearer token. No working dir, no isolation profile, no resource limits, no secret-reference model | **Weak** — most of the config surface is meaningless to a stateless HTTP call |
| C | **Start** — bring the runtime up so the Execution Engine can drive the Work Package inside it | Nothing to start. A completion is request→response; there is no runtime instance the engine drives | **Absent** — no startable host |
| D | **Stream** — surface stdout/stderr/structured output as `runtime.output` (`08`) | SSE `text/event-stream` with `[DONE]` (`open-sse/handlers/sseParser.ts`). Streams *token deltas*, not process stdout | **Partial (reinterpreted)** — token stream ≠ process stream |
| E | **Report progress** — map to `runtime.progress`, honestly *unknown* if absent (`12`) | No task-progress signal; only "tokens arriving." Would degrade to *unknown* | **Weak** — only liveness, never real progress |
| F | **Emit artifacts** — files/logs/metrics/structured outputs as Evidence Candidates by reference (`13`, ADR-003) | Emits a completion body + `usage{prompt,completion,total}` + headers `X-OmniRoute-Provider/Model/Cost/Latency/Request-Id` (`domain/omnirouteResponseMeta.ts`). No files, no filesystem artifacts | **Partial** — the *text result* + usage could become a structured-output/execution-metadata candidate; nothing else |
| G | **Honor cancel / timeout / pause** — carry RM control signals (`09`/`10`/`07`) | `AbortController`/`signal` on upstream `fetch` (`.../bifrost/route.ts`); `BIFROST_TIMEOUT_MS` default 30 s, fetch/idle 600 s (`runtimeTimeouts.ts`). No pause/resume | **Partial** — cancel + timeout yes; suspend/resume no (irrelevant to a completion) |
| H | **Report terminal status** — process ended and how, so RM projects `Completed`/`Failed` (`07`) | HTTP status + `usage` on success; classified error on failure. "Terminal" is per-request, not per-runtime-process | **Partial (reinterpreted)** — request-end, not process-end |
| I | **Clean up** — kill processes, remove containers/workspaces, revoke credential handles (`07` §6, `17`) | Nothing to tear down beyond closing a socket. No workspace, no process, no per-session credential handle | **N/A** — no teardown surface because there is no host |

**Reading:** the concerns that carry real weight for a task runtime — Start (C), Configure
isolation (B), Emit file artifacts (F), Clean up (I) — are **absent or vestigial** for
OmniRoute, because it is not a host. The concerns it satisfies (D stream, G cancel/timeout,
H status) are the ones any HTTP backend satisfies. That is the signature of a
**provider transport**, not a runtime.

## 2. What OmniRoute *is*, in Nexus vocabulary

OmniRoute lines up cleanly with the **"provider mechanics"** column of `03` §4 — the
right-hand side that every adapter *translates to* — for the runtimes that happen to be
LLM-backed (Claude Runtime, Gemini Runtime, MCP Runtime in the frozen table front a
provider endpoint). It is the same class of thing as "the Claude Code endpoint" or "the
Gemini CLI process": the concrete backend a **Nexus-authored adapter drives**. It is not
itself the adapter, and not the runtime.

Crucially, the frozen example set (`03` §4: Claude, Gemini, Shell, Docker, Python, Browser,
MCP, Remote-worker) contains **no pure "call an LLM for a completion" runtime**. Every
example runs a *Work Package* — an agent turn, a CLI invocation, a container job. A
"chat-completion" is not a Work Package; it is a primitive an agentic runtime *uses
internally*. So OmniRoute does not match any existing example runtime — it matches the
*layer beneath* them.

## 3. Lifecycle compatibility (`07`)

Phase 8A realizes the preparation slice `Created → Registered → Allocated → Prepared →
Ready` (+ `Released`/`Failed`). Nothing in OmniRoute contradicts these states — but nothing
in OmniRoute *needs* them either, because there is no allocatable host with a lifetime. If
an LLM Runtime adapter fronted OmniRoute, the states would map trivially (Prepared = "we
have a client + model + token"; Ready = "reachable"), and a completion call would live in
the *execution* states (`Running → Completed`) that Phase 8A explicitly defers. So:
**lifecycle-compatible, but the lifecycle mostly collapses** for a stateless backend.

## 4. Identity & determinism (`02` §3)

Nexus identifiers are pure functions of upstream identity + attempt — no clock, no
randomness. OmniRoute assigns its own `X-OmniRoute-Request-Id` and makes non-deterministic
routing decisions (which upstream served the call, retries, fallback tier). That is fine —
it lives entirely *behind* the adapter boundary; RM's deterministic session/allocation ids
are unaffected because RM never sees OmniRoute's request id as an identity. The
non-determinism is **provider mechanics**, correctly hidden by `03`.

## 5. Verdict for this doc

**Partial, at the wrong altitude.** OmniRoute satisfies the transport-shaped concerns
(stream, cancel, timeout, status, usage metadata) and fails or no-ops the host-shaped
concerns (start, isolation config, file artifacts, teardown) — precisely because it is a
provider transport, not a task-executing runtime. It cannot be *the* Runtime Adapter; it
can be the *backend behind* a future LLM Runtime adapter. Continued in
`02_ARCHITECTURAL_FIT.md`.
