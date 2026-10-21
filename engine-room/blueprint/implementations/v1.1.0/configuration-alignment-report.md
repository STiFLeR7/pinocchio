# Configuration Alignment Report (Operational Bring-up · Phases 1–2)

> **Milestone:** v1.1.0 "Containment" · **Status:** audit complete + alignment **executed** (operator
> authorized owner + email + free-model alignment). **`.env` = single source of truth; never
> rewritten; secret values never printed.**
>
> **⚠ Point-in-time audit (superseded by operational bring-up).** The "token invalid / supply a valid
> token" rows record the Discord state *during alignment*. The operator subsequently supplied a valid
> `DISCORD_BOT_TOKEN` and the bot delivered live (`message_id 1519643857816649821`). Final outcome:
> `operational-bringup-report.md` (9/9) and `notification-validation.md` (Discord ✅).

---

## 1. Subsystem configuration audit (code requires vs `.env`)

| Subsystem | Code reads | Status | Aligned to |
|---|---|---|---|
| Governance/Approval (A-001) | `DISCORD_OWNERS`/`NEXUS_DISCORD__OWNER_IDS` | ✅ after alignment | now also reads `DISCORD_OWNER_ID` |
| Discord (bot) | `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID` | ⚠ token **invalid** | — (operator must replace token) |
| Email (SMTP) | `NEXUS_EMAIL__*` | ✅ after alignment | mapped from `NOTIFY_SMTP_*` + `NOTIFY_EMAIL_FROM` |
| LLM (research/agent) | OpenRouter key | ✅ + multi-provider | Groq (`GROQ_API_KEY`) + Zenmux (`ZENMUX_API`) + OpenRouter free |
| Gemini/Claude runtimes | `GEMINI_API_KEY` / subprocess | ⚠ stubs | n/a |
| Research feeds | `NEXUS_SCHEDULING__RESEARCH_FEEDS` | ⚠ none | one-shot public feed used for live test |
| Scheduler/Sandbox/DB | `NEXUS_*` defaults | ✅ | defaults |

## 2. Alignment changes executed (`config.py`)

1. **Owner ids** — accept `DISCORD_OWNER_ID` (singular; the deployed key) alongside `DISCORD_OWNERS` /
   `NEXUS_DISCORD__OWNER_IDS`. Resolves A-001 fail-closed boot gate (owner_ids count = 1).
2. **Email (SMTP)** — read `NOTIFY_SMTP_SERVER`→`smtp_host`, `NOTIFY_SMTP_PORT`→`smtp_port`,
   `NOTIFY_SMTP_PASSWORD`→`password`, `NOTIFY_EMAIL_FROM`→`from_address` (and `username`, Gmail-style).
   Additive; env wins only when present.
3. **Free-model defaults** — `OpenRouterConfig` primary/fallbacks set to free models
   (`nvidia/nemotron-3-super-120b-a12b:free`, `qwen3-next…:free`, `llama-3.3-70b…:free`).

## 3. Multi-provider LLM gateway (`intelligence/openrouter.py`)

`OpenRouterClient` now builds an ordered provider chain from available keys and falls back across all:
1. **Groq** `https://api.groq.com/openai/v1` → `llama-3.3-70b-versatile`, `meta-llama/llama-4-scout-17b-16e-instruct`
2. **Zenmux** `https://zenmux.ai/api/v1` → `z-ai/glm-5.2`
3. **OpenRouter** free models (rate-limited last resort)

Smoke: Groq answered "ONLINE" in **116 ms**. This removed the OpenRouter **402 (no credits)** and
free-tier **429 (rate-limit)** blockers that initially failed research summaries and agent decisions.

## 4. Remaining config blockers (operator-side)

| Blocker | Root cause | Unblocker |
|---|---|---|
| Discord delivery | `DISCORD_BOT_TOKEN` invalid (`Improper token`) | supply a valid bot token |
| Discord channels | code default names vs guild channels; `.env` `DISCORD_*_CHANNEL` unread | align channel ids or rename guild channels |
| Research feeds | none configured | set `NEXUS_SCHEDULING__RESEARCH_FEEDS` |

## 5. Orphaned `.env` keys (read by no code)

`RESEND_API_KEY`, `NOTIFY_RESEND_ENABLED`, `DISCORD_WEBHOOK_URL`, `LLM_DISCORD_WEBHOOK_URL`,
`DISABLE_SEMANTIC_MEMORY`. (Email uses SMTP, not Resend; Discord uses the bot, not webhooks.)
