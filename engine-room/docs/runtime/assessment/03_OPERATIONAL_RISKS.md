# 03 — Operational Risks

Dependency footprint, maintenance burden, external dependencies, update cadence, and
operational complexity of running OmniRoute as a Nexus backend. Assessed from the cloned
source at `D:/_eval/OmniRoute` (v3.8.42).

## 1. Dependency footprint

| Dimension | Finding | Risk |
|---|---|---|
| Runtime platform | Full **Next.js 16 / React 19 / TypeScript** app; **Node ≥ 22** | **High** — a heavyweight web stack to host a completions proxy for a Python project |
| Native modules | `better-sqlite3` (compiled at install) | **Medium** — native build toolchain required; breaks on Node ABI drift |
| Repo size | ~8k files in the clone | **Medium** — large surface to audit/patch/trust |
| Process model | A **long-lived server** (default port 20128), separate from Nexus | **Medium** — a second daemon Nexus's availability now depends on |
| Language boundary | TS/Node service beside a Python (3.12) codebase | **Medium** — no shared tooling, tests, types, or CI with Nexus |

Nexus itself has a lean, typed, single-language footprint (Python 3.12, mypy --strict,
ruff, uv). Bolting on a Node/Next.js daemon is a **material footprint increase** for what is
architecturally a single adapter's backend.

## 2. Maintenance burden

- **Second lifecycle to operate.** Start/stop/upgrade/monitor a Node service; its health is
  now a Nexus dependency (`/api/health/ping` exists — `src/app/api/health/ping/route.ts` —
  and would have to be probed).
- **Second upgrade cadence.** OmniRoute versions independently (v3.8.42 observed; active
  project). Every upgrade is an unshared change that can alter routing, model catalog, or
  the response-header contract the adapter parses.
- **Reverse-engineered providers rot.** The no-auth free providers (opencode,
  duckduckgo-web, theoldllm, chipotle — `src/shared/constants/providers/noauth.ts`) front
  *unofficial* endpoints. These break without notice and require OmniRoute-side patches the
  Nexus team does not control. This is the single largest ongoing maintenance risk.
- **Native rebuilds.** `better-sqlite3` must recompile on Node upgrades / OS changes.

## 3. External dependencies & phone-home

- **No external telemetry / analytics in the routing path** (verified — `requestTelemetry.ts`,
  `sse/utils/logger.ts` log locally via Pino; no analytics calls). The only outbound
  non-provider call is npm's **update-notifier**, disableable
  (`OMNIROUTE_NO_UPDATE_NOTIFIER=1`). **Low** privacy risk — a genuine positive.
- **Provider egress** is inherent and intended (it is a gateway). Each configured provider
  is an external trust dependency; the no-auth ones especially (see `04`, `05`).

## 4. Update cadence & stability

- Active, versioned project (semver, `CHANGELOG.md` present). Active = frequent change =
  contract drift risk against any adapter that parses its `X-OmniRoute-*` headers or model
  catalog shape.
- The stable, low-risk surface is the **OpenAI-compatible core** (`/v1/chat/completions`,
  `/v1/models`) — an external standard unlikely to break. The **volatile** surface is
  everything OmniRoute-specific (routing backends `ts`/`bifrost`, fallback tiers, no-auth
  providers, custom headers). An adapter should bind to the *stable* surface and treat the
  volatile surface as best-effort.

## 5. Operational complexity

| Concern | Direct-to-OpenRouter (today) | With OmniRoute in front |
|---|---|---|
| Moving parts | 1 (HTTPS to a managed API) | 2 (Nexus + a local Node daemon + its sqlite) |
| Failure surface | provider outage/rate-limit | + daemon down, sqlite corruption, Node/native breakage, no-auth provider rot |
| Debuggability | one request path | two hops; must correlate Nexus logs with OmniRoute telemetry |
| Trust boundaries | one (OpenRouter) | many (OmniRoute + each configured provider) |
| Startup dependency | none | Nexus LLM calls now depend on the daemon being up first |

Complexity roughly **doubles** the operational surface for LLM access. Justified only if the
benefit (cost avoidance + rate-limit smoothing + provider breadth) outweighs it — which is a
**personal-deployment** calculus, not a production one (see `08`).

## 6. Risk-reduction levers (if adopted)

- Bind loopback only (`API_HOST=127.0.0.1`), change `INITIAL_PASSWORD`, set
  `OMNIROUTE_NO_UPDATE_NOTIFIER=1` (see `04`).
- Pin the OmniRoute version; treat upgrades as reviewed changes.
- Bind the adapter to the OpenAI-standard surface only; never hard-depend on `X-OmniRoute-*`
  headers for correctness (treat them as optional telemetry).
- Keep **OpenRouter-direct as the default**; make OmniRoute an *optional* backend so a
  daemon outage degrades to the existing path, not to failure.
- Do not rely on reverse-engineered no-auth providers for anything correctness-critical.

## 7. Verdict for this doc

**Operationally acceptable for a personal/local deployment; not for production
orchestration.** The footprint roughly doubles, the daemon becomes an availability
dependency, and the truly-free tier rests on fragile unofficial endpoints. The privacy
posture (no phone-home) is a real positive. Adopt only with the risk-reduction levers and
OpenRouter-direct retained as the default fallback.
