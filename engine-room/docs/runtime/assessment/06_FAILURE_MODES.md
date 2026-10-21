# 06 — Failure Modes

Can the Runtime Manager absorb OmniRoute's failures **without architectural change**?
Each OmniRoute failure is mapped onto the frozen error taxonomy (`11_ERROR_MODEL.md` §2)
and the lifecycle outcome it drives (`07`). The governing question: does any failure force
a new error class, a new state, or a new event? Answer: **no**.

## 1. OmniRoute failure surface (from source)

- **429 classification** (`src/shared/utils/classify429.ts`): `FailureKind =
  "rate_limit" | "quota_exhausted" | "transient"`; keyword quota detection (`daily.*limit`,
  `quota.*exceed`, `out of credits`, …). Cooldowns ~60 s (rate_limit) / ~1 h
  (quota_exhausted).
- **Circuit breaker + tier fallback** (`open-sse/services/accountFallback.ts`):
  subscription → api → cheap → free; per-provider breaker opens on sustained failure.
- **Timeouts** (`src/shared/utils/runtimeTimeouts.ts`): fetch/idle 600 s, stream readiness
  80 s, connect 30 s; Bifrost 30 s.
- **Cancellation** (`AbortController`/`signal`) on upstream fetch.
- **Reverse-engineered provider breakage** — a no-auth upstream changes/blocks and returns
  malformed or error responses.

## 2. Mapping onto the frozen error taxonomy (`11` §2)

| OmniRoute failure | Nexus error class (`11`) | Lifecycle outcome (`07`) | New class needed? |
|---|---|---|---|
| Daemon down / unreachable at prepare | **execution-startup-failure** (adapter could not bring the backend up) | `Prepared → Failed` | No |
| Backend up but no usable model/provider | **runtime-unavailable** (no healthy candidate) | `Created → Failed` | No |
| 429 `rate_limit` / `quota_exhausted` | **provider-failure** (provider quota/usage rejection) *or* **timeout** if surfaced as elapsed bound | `Running → Failed` (or `→ Cancelled` via `10`) | No |
| Upstream 5xx / provider crash | **provider-failure** | `Running → Failed` | No |
| Socket/stream collapse mid-completion | **transport-failure** | `Running → Failed` | No |
| Timeout (connect/idle/readiness elapsed) | **timeout** (`10`) | `Cancelled` *or* `Failed` → `Destroyed` | No |
| Client/RM abort | **user-cancellation** | `Running → Cancelled` | No |
| Malformed / non-conforming response body | **provider-failure** (provider returned an invalid result) | `Running → Failed` | No |
| Reverse-engineered no-auth provider stops working | **provider-failure** (origin is the provider) | `Running → Failed` | No |
| Tool-limit truncation / degraded tool-calling | *not an error* — a **capability degradation** recorded as `unsupported`/degraded (`05` §2–3) | eligible/degraded, not `Failed` | No |
| OmniRoute sqlite/native fault (its own substrate) | **infrastructure-failure** (substrate fault behind the adapter) | `* → Failed` | No |

**Every** OmniRoute failure lands in an existing class. The taxonomy was designed to be
**provider-independent** precisely so that "an unknown backend misbehaved" is already
covered by `provider-failure`/`transport-failure` with the specifics riding in the
adapter-surfaced `detail` (`11` §6). OmniRoute is exactly such an unknown backend.

## 3. RM absorbs, RM does not recover (`11` §1, §5)

RM **classifies** and emits `runtime.failed` (or `runtime.cancelled` for the intentional
path), then drives `→ Failed → Released → Destroyed`. It does **not** decide retry /
runtime-switch / escalate — that is Recovery, a later phase reacting to the event (`11` §5).

Notably, **OmniRoute's own resilience (breaker, tier fallback, cooldowns) lives entirely
behind the adapter** and is *invisible* to RM — it is provider mechanics (`03` §1). RM sees
only the final outcome after OmniRoute has exhausted its internal fallbacks. This is correct
layering: OmniRoute retrying across free providers is *not* Nexus Recovery; it is one
backend trying to satisfy one call. If it ultimately fails, RM records one
`provider-failure` and hands off to Recovery.

> A subtle governance point: OmniRoute's fallback can *silently* downgrade quality (e.g.
> fall from a capable model to a weak free one) and still return `200`. That is **not** a
> failure RM sees — it is a degraded success. The adapter should surface the actually-served
> provider/model (`X-OmniRoute-Provider`/`-Model`) as **execution-metadata** (`13`) so the
> downgrade is *recorded*, not hidden (no-silent-default discipline). This is telemetry, not
> a new error class.

## 4. Fail-closed alignment (`17` §1 rule 4, `11` §1)

A missing OmniRoute token, an unreachable daemon, or an unresolved credential must
**refuse the session** (`→ Failed`), never proceed unauthenticated or on a guessed default.
This matches RM's fail-fast/fail-closed discipline exactly — no architectural change, just
correct adapter behavior.

## 5. Verdict for this doc

**RM absorbs every OmniRoute failure with zero architectural change.** No new error class,
no new lifecycle state, no new event is required — the provider-independent taxonomy (`11`)
already covers "an opaque backend rate-limited / crashed / broke / timed out." The only new
*discipline* (not architecture) is: record OmniRoute's silent quality-downgrades as
execution-metadata so a degraded-but-200 completion is auditable rather than invisible.
