# Nexus v1.1.0 — Containment

## Executive Summary

Nexus v1.1.0 "Containment" is the first **Pilot operational release** of the AI Orchestration
Control Plane. It was validated through a real, end-to-end operational bring-up — not a mock harness —
exercising all nine subsystems on live infrastructure: boot, operator onboarding, scheduler, email,
research, briefing, runtime execution, checkpoint recovery, and Discord. The autonomous agent
runtime, developed under the internal codename "Hermes", is promoted to a first-class **Nexus Agent**.

**Classification: Pilot Ready** (9/9 stages live-validated). Not yet Production Ready — see Known
Limitations.

## Major Features

- **Nexus Agent (Hermes → Nexus rebranding)** — registry id `nexus`, back-compat alias for legacy
  `hermes` records and imports; third-party Nous Research references intentionally preserved.
- **Nexus Agent: Experimental → Pilot** — fail-fast init, tunable step budget, honest terminal
  lifecycle, cancellation, and resume-from-checkpoint (H-2/H-4).
- **Sandbox: Pilot Safe** — default-secure containment, fail-closed execution, S-3 startup gate.
- **Live operator onboarding** — `python -m nexus onboard`, safe read-only staged validation.
- **Multi-provider LLM gateway** — Groq → Zenmux → OpenRouter (free) fallback chain.
- **Email + Discord notifications** — both delivering on real infrastructure.

## Architecture Improvements

- No architectural redesign — registry, governance, sandbox, scheduler-port, and event-sourced
  memory boundaries preserved; ADR history intact.
- Orchestrator exit-status finalization honors the agent's truthful terminal status (H-4).
- Config alignment reads deployed `.env` keys (`DISCORD_OWNER_ID`, `NOTIFY_SMTP_*`,
  `NOTIFY_EMAIL_FROM`) without a parallel credential store; `.env` remains the single source of truth.

## Operational Validation Results (9/9)

| Stage | Verdict |
|---|---|
| Boot (A-001 + S-3 gates) | ✅ |
| Operator onboarding | ✅ |
| Scheduler | ✅ |
| Email (SMTP) | ✅ |
| Research | ✅ |
| Briefing | ✅ |
| Runtime (Nexus Agent) | ✅ |
| Recovery (checkpoint resume) | ✅ |
| Discord | ✅ |

## Live Integration Results

- **Email:** real SMTP delivery to operator (`smtp.gmail.com:587`) after a one-line double-STARTTLS fix.
- **Discord:** bot connected to guild, "Welcome to Nexus" embed posted to `#general`,
  `message_id 1519643857816649821`.
- **Research:** 20 findings parsed from a live RSS feed, LLM-scored and persisted.
- **Recovery:** interrupt → `timed_out` → fresh-adapter resume → `completed`, no corruption.

## Performance Metrics (observed 2026-06-25)

- Tests: **219 passed** (~45 s); ruff clean; mypy clean (61 files).
- LLM latency (Groq primary): ~120 ms.
- Email delivery: ~8.8 s incl. handshake.
- Scheduler: 4 jobs executed (`started:4`/`completed:4`).
- Checkpoints persisted: 39; executions: 3; agent steps: 5.

## Upgrade Notes

- **No database migration required.** Fresh schema from current models via `create_all`; existing
  v1.1.0-column databases need no change.
- Legacy `runner="hermes"` / `hermes_agent` still resolve; import the runtime from
  `nexus.execution.runners.nexus_agent` (old `hermes` module path removed).
- LLM defaults are now free OpenRouter models; set `GROQ_API_KEY` / `ZENMUX_API` for the full
  fallback chain or a paid/BYOK OpenRouter key for sustained load.
- Singular `DISCORD_OWNER_ID` env key now supported for A-001 owner resolution.

## Known Limitations

- Free-tier LLM rate-limits under sustained load (mitigated, not eliminated).
- `create_all`-only schema management; Alembic migrations incomplete.
- `.env` `DISCORD_*_CHANNEL` ids not yet read into config (delivery works via channel resolution).
- Gemini / Claude runtimes remain generic shell runners (Experimental).
- No production web `SearchProvider` for agent tools.
- In-code version string still reads `0.1.0` (pre-existing debt; deferred to v1.2).

## Roadmap toward v1.2

- Durable/BYOK LLM capacity and rate-limit alerting.
- Adopt a real schema-migration tool (Alembic) and retire manual recreate.
- Map `.env` Discord channel ids into config for deterministic routing.
- Real Gemini/Claude CLI runtime integration.
- Production `SearchProvider`.
- Version-string alignment; broader soak/load testing on J5/J6 health metrics.
