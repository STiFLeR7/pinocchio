# 05 — Tool Calling

The critical section. Nexus is an *orchestration* control plane: its runtimes must reliably
emit **tool/function calls** (the Dex `send_email` path is a live example). This section
separates three distinct things that are easy to conflate: **routing pass-through**,
**model capability**, and **end-to-end reliability**.

## 1. What OmniRoute does with tool calls (routing layer)

Verified in source:

- The relay request schema uses **`.passthrough()`** (`.../relay/chat/completions/bifrost/
  route.ts`, `BifrostRequestSchema`), so OpenAI fields — `tools`, `tool_choice`,
  `response_format` — are **kept intact** and forwarded.
- `tool_choice` forcing is handled (`open-sse/executors/base.ts`: detects
  `tool_choice: "any"` / `{type:"tool"}`).
- Per-provider translation happens in the translator/executor layer (`@omniroute/open-sse/
  translator`); tool lists may be **truncated** to a provider's `effectiveToolLimit`
  (`open-sse/handlers/chatCore/upstreamBody.ts`).
- Responses carrying `tool_calls` are reconstructed through the SSE parser.

> **Routing verdict:** OmniRoute is a faithful pass-through — it does **not** strip, reject,
> or fabricate tool calls. It adds a *per-provider tool-limit truncation* risk (a long tool
> list may be silently trimmed for a given provider).

## 2. The distinction that matters

Tool-calling reliability is a **model** property, not a **routing** property. OmniRoute
passing `tools` through faithfully does nothing to make a weak model emit correct
`tool_calls`. This is the crux of the earlier Dex bug: the failure was the *model's*
function-calling, and no gateway fixes that.

## 3. Three-way comparison

| Property | **OpenRouter** (direct, today) | **OmniRoute** (routing) | **No-auth providers** (behind OmniRoute) |
|---|---|---|---|
| Passes `tools`/`tool_choice` through | yes | yes (`.passthrough()`) | yes, but per upstream |
| Returns `tool_calls` | yes, per model | yes, per model | **varies; unreliable** |
| Tool-limit truncation | provider-dependent | possible (`effectiveToolLimit`) | likely tighter |
| Model quality for function-calling | depends on chosen model; strong models available | **same models** — OmniRoute is just a pipe | **weak/inconsistent** — reverse-engineered, often chat-only |
| Determinism of structured output | model-dependent | model-dependent (routing adds none) | **low** — different upstreams, different behavior |
| ToS / stability of the endpoint | governed, paid/free tiers | n/a (local) | **fragile, gray-area** (opencode/theoldllm/chipotle/ddg) |

**Reading:** OpenRouter and OmniRoute expose the *same* models with the *same* tool-calling
quality when pointed at the same model — OmniRoute adds routing, not intelligence. The
no-auth free providers are where tool-calling **falls apart**: they front unofficial
endpoints (`noauth.ts`), many are chat/text-only, and their structured-output behavior is
inconsistent and undocumented. **Do not depend on no-auth providers for tool-calling.**

## 4. Consequences for Nexus

1. **OmniRoute does not solve the tool-calling problem.** It solves *rate limits and
   provider breadth*. Keep the deterministic intent-coercion in Dex regardless of gateway.
2. **The truly-free tier is the least tool-capable tier.** The "keep it free" goal
   (no-auth providers) and the "reliable tool calls" goal are in direct tension. You can
   have free *chat/summarization*, but agentic tool-calling wants a real model
   (OpenRouter-direct, or a keyed provider under BYOK).
3. **Tool-limit truncation is a silent-default hazard** (`05` capability model forbids
   silent drops). If an adapter forwards a large tool list, it must detect/guard OmniRoute's
   `effectiveToolLimit` trimming, or advertise the tool-use capability as *degraded* rather
   than fully satisfied (`05` §3 negotiation).
4. **Capability honesty (`05` §2).** An LLM Runtime adapter must advertise `tool_use` as
   *satisfied* only for models/providers that actually back it; for no-auth providers it
   must record *unsupported*, never fabricate (`03` §6, `05` §2 honesty rule).

## 5. Verdict for this doc

**Routing: supported and faithful. Reliability: unchanged by OmniRoute, and *worse* on the
free tier.** OmniRoute is a competent pipe for tool calls but adds no tool-calling
reliability; the no-auth providers that make it "free" are exactly the ones that cannot be
trusted for function-calling or deterministic structured output. For agentic orchestration,
tool-calling must ride real models (OpenRouter-direct or keyed BYOK), not the free tier.
Determinism-critical structured output should continue to be coerced/validated in Nexus, not
delegated to the model.
