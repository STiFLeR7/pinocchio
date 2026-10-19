# 04 — Security Review

Assessed against the Runtime security spine (`17_RUNTIME_SECURITY.md` §1) and the
platform-wide, **binding** rule that **`.env` is the single source of truth for secrets**.
This is the section with a hard conflict.

## 1. The security spine (what Nexus requires)

`17` §1, non-negotiable:

1. **`.env` is the single source of truth for secrets** — values live *only* in `.env`.
2. Secrets reach a runtime by **injected reference, through the adapter, at configure-time** —
   never baked into anything persistent.
3. **Least privilege** — a session gets only what its package declared.
4. **Fail-closed** — a missing/unresolved credential or failed isolation **refuses** the
   session; no degraded-but-running state (A-001-style: absence of a positive grant = deny).

## 2. OmniRoute's credential model (what it actually does)

Verified in source:

- Provider API keys are stored **encrypted at rest in SQLite** at `DATA_DIR` (default
  `~/.omniroute/`), encrypted via `API_KEY_SECRET` (AES-GCM) — `src/lib/db/apiKeys.ts`,
  `.env.example`. The DB may be further encrypted via `STORAGE_ENCRYPTION_KEY`.
- OmniRoute's own secrets (`API_KEY_SECRET`, `STORAGE_ENCRYPTION_KEY`, `JWT_SECRET`,
  `INITIAL_PASSWORD`) live in `~/.omniroute/.env`.
- **No-auth providers store zero keys** (`noAuth: true` — `src/shared/constants/providers/
  noauth.ts`): opencode, duckduckgo-web, theoldllm, chipotle, and similar.
- Auth posture: **loopback bypasses *dashboard* auth** (`isLoopbackRequest` in
  `src/shared/utils/apiAuth.ts` matches `127.0.0.0/8`, `localhost`, `::1`), but the
  **relay completion route still requires a bearer token** (`.../relay/chat/completions/
  bifrost/route.ts`). *(This refines an earlier, looser "localhost = no auth" note — the
  API is more locked down than that; treat the exact per-route posture as configuration to
  verify at deploy, and adopt a fail-closed default regardless — see §5.)*
- Default binding is **`0.0.0.0`** (all interfaces — `.env.example` `API_HOST=0.0.0.0`);
  default `INITIAL_PASSWORD=CHANGEME`.

## 3. The conflict

> **If OmniRoute holds any provider API key, it is a second credential store — a direct
> violation of `17` §1 rule 1 (`.env` single source of truth).** The key value would live
> in `~/.omniroute/storage.sqlite`, outside `.env`, encrypted by a key in
> `~/.omniroute/.env` — a whole parallel secret domain Nexus does not govern.

This is not a soft preference; it is the platform's first security rule and a standing
project constraint. Storing OpenRouter/OpenAI/Anthropic keys inside OmniRoute is
**disallowed**.

## 4. The compliant path (and it is real)

The conflict **dissolves** under either restriction:

| Mode | Where keys live | `.env`-single-source? |
|---|---|---|
| **No-auth providers only** (opencode/ddg/etc.) | nowhere — zero keys stored | ✅ compliant (no provider secret exists) |
| **Keyed providers via BYOK, key injected per-request** | in Nexus `.env`, passed through at call-time as an injected reference (never persisted in OmniRoute) | ✅ compliant *iff* OmniRoute is configured to not persist it |
| **Keyed providers stored in OmniRoute sqlite** | `~/.omniroute/storage.sqlite` | ❌ **violates** — second store |

Additionally, OmniRoute's own relay bearer token (if the relay route requires one) is
itself a secret Nexus must hold — that token belongs in **Nexus `.env`**, injected to the
adapter at configure-time (`17` §3), never hard-coded. One secret in `.env` is fine; a
parallel key vault is not.

Secret propagation would then follow `17` §3 exactly: `.env` → adapter `configure` (by
reference) → OmniRoute call → scrubbed at teardown. Redaction (`17` §6) applies to the
completion stream/artifact so an echoed secret cannot land in a `runtime.output` or an
artifact.

## 5. Deployment hardening (mandatory if adopted)

- `API_HOST=127.0.0.1` — **loopback only**; never expose `0.0.0.0` on a shared network.
- Change `INITIAL_PASSWORD` from `CHANGEME`.
- `OMNIROUTE_NO_UPDATE_NOTIFIER=1`.
- **Fail-closed default:** the adapter must *require* a token and refuse if the backend is
  unreachable or unauthenticated (`17` §1 rule 4) — never fall through to an unauthenticated
  call just because it happens to be loopback. Absence of a positive grant = deny.
- Never let a provider key be echoed into a `runtime.*` event, log, stream chunk, or
  artifact (`17` §3/§6). Redact at the stream/artifact edge.

## 6. Least-privilege & network posture

OmniRoute has **no per-session isolation model** — it is a shared daemon fronting many
providers with ambient egress to each. That is weaker than the per-category isolation `17`
§2 mandates for task runtimes. For an *LLM completion* runtime this matters less (there is
no filesystem/process to sandbox), but the **network posture is ambient** (the daemon can
reach every configured provider), which is the opposite of `17`'s default-deny. The adapter
must not present OmniRoute as more isolated than it is (`03` §6 honesty).

## 7. Verdict for this doc

**Conditional pass, with one hard gate.** OmniRoute **violates** the `.env`-single-source
rule **iff** it stores provider keys — which is disallowed. It is **compliant** when
restricted to **no-auth providers** (zero stored keys) or **strict BYOK pass-through**
(keys stay in Nexus `.env`, never persisted by OmniRoute), plus loopback binding, changed
password, and a fail-closed adapter. The ambient network posture and shared-daemon model
are acceptable for a completion backend but must be represented honestly.
