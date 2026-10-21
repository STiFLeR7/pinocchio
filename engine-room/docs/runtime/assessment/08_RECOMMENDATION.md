# 08 — Recommendation

## Verdict: **APPROVE WITH CONSTRAINTS**

Not as a Runtime. Not now. Never in RM core. **Acceptable later** as the optional,
sandboxed provider *backend* of a Nexus-authored **LLM/Model Runtime adapter**, under the
binding constraints below, with **OpenRouter-direct remaining the default**.

The reason it is not a flat REJECT: adopting it requires **zero** change to any frozen
contract, ADR, invariant, lifecycle state, or event (`02`), it maps cleanly behind an
adapter (`07`), and RM absorbs all its failures with no architectural change (`06`). The
reason it is not a flat APPROVE: as constituted it is at the **wrong altitude** (a
completions gateway, not a task runtime — `01`), its "free" tier is unreliable for
tool-calling (`05`), it can violate the `.env`-single-source security rule (`04`), and it
roughly doubles the operational surface (`03`).

## Binding constraints (all must hold)

1. **Never register OmniRoute as a Runtime.** It is transport behind a future LLM Runtime
   adapter — never a Runtime itself, never an entry in RM core, never upstream-visible
   (`01`, `02`, `03` §3).
2. **Defer to a later adapter phase.** Phase 8A (Runtime Core) explicitly excludes all
   adapters. No adapter — OmniRoute or otherwise — is in scope until the adapter phase.
3. **Security: no second credential store.** Restrict to **no-auth providers** (zero stored
   keys) **or** strict **BYOK pass-through** with keys living only in Nexus `.env` and never
   persisted in OmniRoute's sqlite. Any OmniRoute relay token lives in Nexus `.env`, injected
   by reference (`04`, `17` §1/§3).
4. **Harden the deployment:** `API_HOST=127.0.0.1` (loopback only), change `INITIAL_PASSWORD`
   from `CHANGEME`, `OMNIROUTE_NO_UPDATE_NOTIFIER=1`, fail-closed adapter (refuse if
   unreachable/unauthenticated) (`04` §5).
5. **Do not rely on it for tool-calling reliability.** Keep Nexus's deterministic
   intent-coercion/validation. Advertise `tool_use` as satisfied only where a real model
   backs it; record no-auth providers as *unsupported* for tool-calling, never fabricate
   (`05`).
6. **Keep OpenRouter-direct as the default backend.** OmniRoute is an *optional* coexisting
   descriptor (`19` §6); a daemon outage must degrade to the existing direct path, not to
   failure (`03` operational).
7. **Record silent quality-downgrades.** Surface the actually-served provider/model
   (`X-OmniRoute-Provider/-Model`) as execution-metadata so a degraded-but-200 completion is
   auditable (`06` §3, no-silent-default).
8. **Bind to the stable seam only.** Depend on the OpenAI-standard `/v1/chat/completions` +
   `/v1/models`; treat `X-OmniRoute-*` headers and internal routing as best-effort telemetry
   that may change across versions (`03` operational).

## The seven explicit questions

**1. Does OmniRoute belong inside Nexus?**
Not inside RM core, and not as a Runtime. It may live *inside a single adapter* as provider
transport — the one bounded provider-aware region (`00` §4, `03` §3). So: conditionally, at
the adapter-backend layer only, and only under the constraints above. Reasoning: it hosts no
Work Package (INV-09) and no-ops the host-shaped adapter concerns (`01` §1).

**2. Should it be treated as an optional Runtime Adapter?**
Precise answer: **it is not itself an adapter — it is what an adapter calls.** The *adapter*
(a future, Nexus-authored LLM Runtime adapter) is optional; OmniRoute is an optional
*backend* for that adapter, coexisting with a direct-OpenRouter backend and steerable by
policy (`19` §6, `07` §5). Treating OmniRoute *as* the adapter would force it to fake
Start/Configure/Cleanup — forbidden.

**3. Does it require changes to the Runtime architecture?**
**No.** Nothing frozen changes (`19` §4 table; `02` here): not RM core, the Execution
Package, the Session, the lifecycle, the events, the Registry contract, or any ADR/invariant.
It introduces a new runtime *category* (LLM/model runtime), which the open-closed
extensibility design (`19` §7) treats as purely additive — a new adapter + a registration,
by construction not an architectural change.

**4. Does it violate the single-source-of-configuration principle?**
**It can, and must be constrained so it does not.** Storing provider keys in OmniRoute's
`~/.omniroute/storage.sqlite` is a second credential store — a direct violation of `.env`
single-source (`17` §1, `04` §3). It is **compliant** only under no-auth-only or strict
BYOK pass-through (constraint 3). Absent that constraint: **yes, it violates it.**

**5. Is it appropriate for production-quality orchestration?**
**No.** Reliance on reverse-engineered no-auth providers (fragile, ToS-gray, weak
tool-calling — `05`), a heavyweight second daemon as an availability dependency, a second
trust boundary, and ambient network posture (`03`, `04`) make it unsuitable as a production
backbone. Acceptable only as a best-effort/fallback backend, never the primary for
production.

**6. Is it appropriate only for personal deployments?**
**Yes — that is its sweet spot.** Local, personal, cost-avoidance, rate-limit smoothing,
no external phone-home (`03` §3). For a single-user Nexus (the daily-use scenario that
motivated this), constrained per above, it is a reasonable *optional* free/fallback backend.

**7. Would you personally recommend adopting it for Nexus?**
**Not now, and not as a Runtime.** Recommendation: (a) **do not** adopt during Runtime Core;
(b) when the LLM Runtime adapter category is designed, adopt OmniRoute **only** as an
optional, constrained, personal-tier backend behind that adapter, with **OpenRouter-direct
as default**; (c) for the underlying goals — daily-use rate limits and cost — the simpler,
lower-risk fix remains the one-time OpenRouter $10 top-up (1000 req/day permanent) plus
keeping deterministic tool-call coercion. OmniRoute buys provider breadth and outage
smoothing, not model quality, at the cost of a second daemon and a second trust boundary.

## One-paragraph bottom line

OmniRoute is a well-built, privacy-respecting, OpenAI-compatible **completions gateway** —
but it is a *provider transport*, not a Nexus *Runtime*. It fits the architecture only in
one lawful place (inside a future, optional LLM Runtime adapter), requires no change to any
frozen contract to do so, and is fully absorbed by the existing error model. Its free tier
trades tool-calling reliability for zero cost, and it can breach the `.env`-single-source
rule unless deliberately constrained. **APPROVE WITH CONSTRAINTS**, deferred to the adapter
phase, personal-tier and optional, with OpenRouter-direct kept as the default — never as a
first-class Runtime, and never in RM core.
