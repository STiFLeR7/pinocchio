# Onboarding Validation

> v1.1.0 bring-up · `python -m nexus onboard` (read-only staged validation).

## Operator
Hill Patel · @stifler · hillaniljppatel@gmail.com.

## Stages (post config-alignment)
| Stage | Result |
|---|---|
| System checks | ✅ Python 3.13, venv, dirs |
| Configuration | ✅ owner ids resolve (A-001), LLM key, Discord token present, SMTP config |
| Git | ✅ git + repository |
| Sandbox | ✅ default-secure (enabled=False → fail-closed) |
| Discord | config present (delivery validated separately — token invalid) |
| SMTP | ✅ transport configured (NOTIFY_*→SMTP aligned) |
| Research | ✅ OpenRouter/multi-provider key present |
| Scheduler | ✅ 6 jobs registered |
| Runtime | ✅ nexus/gemini/claude + hermes alias resolve |
| Memory | ✅ DB connectivity + tables |
| Operator profile | ✅ identity recorded (in-session; `.env` source of truth) |

Before alignment the Configuration stage **correctly FAILED** on missing owner ids (A-001 fail-closed)
— evidence the onboarding surfaces real blockers rather than masking them. After aligning
`DISCORD_OWNER_ID`, the owner gate passes.

## Tests
`tests/unit/test_onboarding.py` (5, DB-free) green within the 219-suite: owner-ids fail-closed,
runtime+alias resolution, helpers, summarize.

## Verdict
Onboarding: **Pilot Ready** — staged, honest, safe; surfaces A-001 and config gaps explicitly.
