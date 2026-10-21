# Operational Bring-up Report — Nexus v1.1.0 "Containment"

> **Role:** Systems Integration Engineer · first live bring-up. **Mode:** real integrations, no
> mocks. **Status:** **9/9 stages live-validated.** **Uncommitted** — awaiting review.
> Gates: **219 passed · ruff clean · mypy clean (61 files)**.

---

## Stage results (observed evidence)

| Stage | Verdict | Evidence |
|---|---|---|
| **Boot** | ✅ | A-001 owner gate (active, 1 owner), S-3 sandbox gate, DB 21 tables, git validation, policy seed, scheduler builds 6 jobs, 4 runtime ids resolve |
| **Onboarding** | ✅ | `python -m nexus onboard` all stages green after config alignment (owner ids resolve) |
| **Scheduler** | ✅ | 4 jobs executed; audit `scheduler.job.started:4` / `completed:4` |
| **Email (SMTP)** | ✅ | real delivery to operator via `smtp.gmail.com:587` (`email_sent_successfully`) after STARTTLS fix |
| **Research** | ✅ | 20 findings parsed from live HN RSS + LLM-scored + persisted (`research.completed`) |
| **Briefing** | ✅ | generated + dispatched (`report.generated:2`) via real engine + email |
| **Runtime (nexus agent)** | ✅ | governed real-LLM runs → `completed`/exit 0 with artifacts `{agent_plan, agent_trajectory, diff, summary}`; `RuntimeAuthorized:4` |
| **Recovery** | ✅ | interrupt→`timed_out` → fresh-adapter resume→`completed`; no corruption; audit continuity |
| **Discord** | ✅ | bot **Dex#9955** connected to "STiFLeR's server"; onboarding embed delivered to #general (`message_id 1519643857816649821`) after a valid token was supplied |

## Configuration alignment performed (Phase 2 — authorized)

`.env` was the single source of truth and never rewritten. The implementation was aligned to read it:
- **Owner ids:** `config.py` now also reads `DISCORD_OWNER_ID` (the deployed key name) → A-001 unblocked.
- **Email:** `config.py` maps `NOTIFY_SMTP_SERVER/PORT/PASSWORD` + `NOTIFY_EMAIL_FROM` (username=from) → SMTP delivery.
- **LLM providers:** to overcome OpenRouter **402 (no credits)** then free-tier **429 (rate-limit)**,
  the gateway became a **multi-provider fallback chain (Groq → Zenmux → OpenRouter free)** using the
  operator's `GROQ_API_KEY` / `ZENMUX_API` keys; Groq `llama-3.3-70b-versatile` answers in ~120ms.

## Code changes this phase (uncommitted, for review)

| File | Change | Why |
|---|---|---|
| `nexus/config.py` | `DISCORD_OWNER_ID` owner alias; `NOTIFY_*`→SMTP mapping; free-model defaults | config alignment (operational) |
| `nexus/intelligence/openrouter.py` | multi-provider fallback chain | bypass 402/429 LLM blockers |
| `nexus/communication/email/service.py` | `start_tls=False` (one line) | fix double-STARTTLS (approved) |
| `data/nexus.db` | backed up + recreated from current models | stale schema drift (approved) |

## Blockers (resolved / residual)

1. **Discord token** — was invalid (`Improper token`); operator supplied a valid token → **resolved**,
   message delivered. Residual polish: map `.env` `DISCORD_*_CHANNEL` ids into `settings.discord.channels`.
2. **Free-LLM rate-limits/credits** — mitigated by the multi-provider chain (Groq primary). A paid key
   or BYOK would remove residual 429s entirely.

## Completion criteria

Boot ✅ · onboard ✅ · scheduler ✅ · research ✅ · briefing ✅ · ≥1 runtime ✅ · notifications ✅
(email + Discord) · recovery ✅ · operational evidence ✅. **9/9 met.**

See per-stage reports + `production-readiness-assessment.md`.
