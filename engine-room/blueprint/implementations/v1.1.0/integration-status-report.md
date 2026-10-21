# Integration Status Report & Configuration Remediation Plan

> **Milestone:** v1.1.0 "Containment" · Phases 2 + 4 (modified) · **Status:** ✅ safe validation
> complete. **Mode:** read-only, no external sends (operator decision). `.env` = single source of
> truth; secret **values never printed** — only present / missing / invalid.
>
> **⚠ Point-in-time audit (superseded by operational bring-up).** The blockers below (notably the
> A-001 owner-id gap) record the state *discovered* during this phase. All were subsequently
> resolved — owner id aligned, Discord delivered live (`message_id 1519643857816649821`). For the
> final outcome see `operational-bringup-report.md` (9/9) and `production-readiness-assessment.md`.

---

## 1. Configuration report (what the code actually reads)

The codebase consumes a specific set of environment variables. The populated `.env` largely uses a
**different scheme** (Resend / webhooks / Groq) that **no code path reads**.

| Capability | Env var the code reads | Status | Note |
|---|---|---|---|
| Discord bot token | `DISCORD_BOT_TOKEN` | ✅ present | |
| Discord guild | `DISCORD_GUILD_ID` | ✅ present | |
| **Approval auth (A-001)** | `DISCORD_OWNERS` / `NEXUS_DISCORD__OWNER_IDS` | ❌ **missing** | **startup fails closed** (`api.py:81`) — the one hard blocker |
| LLM gateway (research/agent) | `OPENROUTER_API_KEY` | ✅ present (process env) | resolves at runtime; **not** in the `.env` file (file has `GROQ_API_KEY`) |
| Agent/Gemini LLM | `GEMINI_API_KEY` | ⚠ absent | optional; OpenRouter covers research |
| Email SMTP | `NEXUS_EMAIL__{USERNAME,PASSWORD,SMTP_HOST,SMTP_PORT,FROM_ADDRESS,TO_ADDRESS}` | ❌ missing | `.env` has `NOTIFY_SMTP_*` / `RESEND_*` (unread) |

**Orphaned in `.env` (read by no code):** `GROQ_API_KEY`, `RESEND_API_KEY`, `NOTIFY_EMAIL_*`,
`NOTIFY_SMTP_*`, `NOTIFY_RESEND_ENABLED`, `DISCORD_*_CHANNEL`, `DISCORD_WEBHOOK_URL`,
`LLM_DISCORD_WEBHOOK_URL`, `DISABLE_SEMANTIC_MEMORY`. (`config/settings.yaml` absent → defaults apply.)

> **Reconciliation note:** the Phase-2 `.env`-file scan reported `OPENROUTER_API_KEY` missing; the
> live onboarding run shows it **present** because it resolves from the **process environment**, not
> the `.env` file. Both statements are true at their layer; runtime behavior is what matters, and the
> key **is** available.

## 2. Per-integration status (safe validation)

| Integration | Constructable / configured | Live-tested | Blocker to live |
|---|---|---|---|
| Discord | ✅ token+guild+7 channels | ⏸ deferred (safe mode) | none for delivery; bot uses discord.py (not the `.env` webhooks) |
| Email (SMTP) | ⚠ `NEXUS_EMAIL__*` unset | ⏸ deferred | no code-readable SMTP creds (only `NOTIFY_*`/`RESEND_*`) |
| Research | ✅ OpenRouter key present | ⏸ deferred | no RSS feeds configured (`NEXUS_SCHEDULING__RESEARCH_FEEDS`) |
| Scheduler | ✅ builds, 6 jobs (J1–J6) | ⏸ not started | none (start is a runtime action) |
| Runtime | ✅ `nexus`/`gemini`/`claude` + `hermes` alias resolve | ⏸ deferred | `gemini`/`claude` are subprocess **stubs**; `nexus` agent needs a real injected `SearchProvider` for web tools |
| Memory | ✅ DB reachable, 11 tables | ✅ (local, read-only) | none |

## 3. Configuration remediation plan (to enable live operation)

Add the **code-readable** keys to `.env` (single source of truth — do **not** create another store):

1. **`DISCORD_OWNERS`** = comma-separated operator Discord user id(s). **Required** — without it the
   app fails closed at startup (A-001). *Highest priority.*
2. **`NEXUS_EMAIL__SMTP_HOST` / `__SMTP_PORT` / `__USERNAME` / `__PASSWORD` / `__FROM_ADDRESS` /
   `__TO_ADDRESS`** — to enable real SMTP email (the operator onboarding email). The existing
   `NOTIFY_SMTP_*` values can be copied into these names.
3. *(optional)* **`NEXUS_SCHEDULING__RESEARCH_FEEDS`** — RSS feed map to activate J1 research runs.
4. *(optional)* **`GEMINI_API_KEY`** — only if the Gemini CLI runtime is wired (currently a stub).

**Not required:** `OPENROUTER_API_KEY` already resolves at runtime.

Two integration approaches were offered; the operator selected **remediation plan + safe validation**
(this document) over auto-adapting the code to the `.env`'s alternate scheme. No live sends were
performed.

## 4. Verdict

System is **one hard blocker** away from a clean boot: **missing owner ids (A-001)**. Email and
research are **warns** (degraded, not fatal). Everything else validates green in safe mode.
