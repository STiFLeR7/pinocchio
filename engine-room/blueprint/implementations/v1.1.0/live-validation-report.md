# Live Validation Report

> **Milestone:** v1.1.0 "Containment" · Phase 4 (modified) · **Mode:** safe / read-only — **no
> external sends** (operator decision: "config remediation plan + safe validation"). **Secret values
> never printed.**

---

## 1. What "live validation" means here

Phase 4 originally requested real Discord messages, a real onboarding email to
`hillaniljppatel@gmail.com`, a real research run (real OpenRouter spend), a manual scheduler fire, and
live runtime execution. The operator selected **safe validation with a remediation plan** instead of
firing external/irreversible actions, because:

1. The app currently **fails closed at startup** (missing owner ids, A-001) — it cannot fully boot.
2. Email has **no code-readable SMTP credentials** (the `.env` uses `NOTIFY_*`/`RESEND_*`, which no
   code reads) — a real send is impossible without remediation.
3. `gemini` / `claude` runtimes are **stubs** — "live infrastructure" execution of them is not real.

Accordingly, every check below was performed **in-process, read-only, with no network egress**.

## 2. Results by target

| Target | Requested (Phase 4) | Performed (safe mode) | Evidence |
|---|---|---|---|
| Discord | send real onboarding message | config + routing validated; **no send** | onboarding stage 5 ✔ (token+guild, 7 channels) |
| Email | send real onboarding email | transport completeness checked; **no send** | onboarding stage 6 ▲ (`NEXUS_EMAIL__*` unset) |
| Research | one real RSS+OpenRouter run | feeds + key presence checked; **no LLM call** | onboarding stage 7 ▲ (no feeds; key present) |
| Scheduler | trigger one execution | `build_scheduler` constructs J1–J6; **not started** | onboarding stage 8 ✔ (6 jobs listed) |
| Runtime | execute gemini/claude/nexus | registry resolution only; **no run** | onboarding stage 9 ✔ (+ `hermes` alias) |
| Memory | — | DB `SELECT 1`, 11 tables | onboarding stage 10 ✔ |

## 3. Deferred live actions (and their unblockers)

| Live action | Blocked by | Unblocker |
|---|---|---|
| Real Discord onboarding message | none technical; held by safe-mode decision | re-authorize live send |
| Real onboarding email to operator | no `NEXUS_EMAIL__*` SMTP creds | add SMTP keys (see `integration-status-report.md` §3) |
| Real research run | no RSS feeds (OpenRouter key OK) | set `NEXUS_SCHEDULING__RESEARCH_FEEDS` |
| Full app boot | missing owner ids (A-001) | set `DISCORD_OWNERS` |
| Live gemini/claude execution | runtimes are stubs | real CLI integration (separate track) |

## 4. Honesty statement

No Discord message was sent. No email was sent. No LLM/research call was made. No scheduler job was
fired. No runtime was executed. All evidence above derives from read-only, in-process checks against
real configuration and real local infrastructure (SQLite). Live integration testing remains available
and gated behind the §3 remediation and an explicit authorization.
