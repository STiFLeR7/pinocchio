# Onboarding Report — Nexus Operator Onboarding Experience

> **Milestone:** v1.1.0 "Containment" · Phase 3 · **Status:** ✅ built, runs, tested.
> Module: `nexus/onboarding.py` · Entry: `python -m nexus onboard` (or `python -m nexus.onboarding`).

---

## 1. Intent

A first-class, "bring-the-system-online" onboarding flow — inspired in spirit (not code) by the
Nous Research `hermes-agent` TUI — that walks an operator through staged validation of every Nexus
subsystem and finishes with a clear go/no-go verdict.

**Safe by default:** every stage is **read-only**; it performs **no external sends and no network
I/O** (no Discord messages, no emails, no LLM calls). Configuration is reported only as
present / missing / invalid — **secret values are never printed**. (Per operator decision: config
remediation plan + safe validation; live delivery is a separate, gated capability.)

## 2. Flow (11 stages + verdict)

`Welcome banner → System → Configuration → Git → Sandbox → Discord → SMTP → Research → Scheduler →
Runtime → Memory → Operator profile → Finish (verdict)`

Each stage yields colored ✔/▲/✘/• checks with a one-line, secret-free detail. Output auto-degrades
to ASCII glyphs when the terminal cannot encode Unicode (Windows cp1252 safe), and forces UTF-8
stdout when possible. Exit code is non-zero if any stage FAILs (CI/scriptable).

## 3. Stage coverage

| Stage | Checks (read-only) |
|---|---|
| System | Python ≥3.12, platform, venv active, `data/` & `config/` dirs |
| Configuration | bot token, guild id, **owner ids (A-001 fail-closed)**, LLM key, SMTP completeness |
| Git | `git` on PATH, workspace `.git` present |
| Sandbox | containment posture (enabled/provider/network/fs), docker availability or fail-closed fallback |
| Discord | bot credentials present, channel routing count; live delivery **deferred** |
| SMTP | transport config completeness (host/from/auth); live delivery **deferred** |
| Research | RSS feeds configured, OpenRouter key; live run **deferred** |
| Scheduler | `build_scheduler` constructs; lists registered J1–J6 job ids; not started |
| Runtime | registry resolves `nexus`/`gemini`/`claude` + legacy `hermes` alias; no execution |
| Memory | DB `SELECT 1`, table count |
| Operator | name / username / email (identity only — `.env` stays source of truth) |

## 4. Captured run (this environment, safe mode)

```
[1/11] System checks               ✔  Python 3.13.11, venv active, data/ + config/ present
[2/11] Configuration validation    ✘  owner ids MISSING (A-001 fail-closed); SMTP incomplete (warn)
[3/11] Git validation              ✔  git present, repository present
[4/11] Sandbox validation          ✔  enabled=False provider=local → execution fail-closed (default-secure)
[5/11] Discord validation          ✔  token+guild present, 7 channels mapped (delivery deferred)
[6/11] SMTP validation             ▲  host=set from=missing auth=missing (delivery deferred)
[7/11] Research validation         ▲  RSS feeds none; OpenRouter key present (run deferred)
[8/11] Scheduler validation        ✔  6 jobs: research_collection, daily_briefing, approval_expiration_sweep,
                                       metrics_aggregation, outbox_health, checkpoint_health
[9/11] Runtime validation          ✔  nexus/gemini/claude resolve; hermes alias → NexusRuntimeAdapter
[10/11] Memory validation          ✔  SELECT 1 ok; 11 tables present
[11/11] Operator profile           ✔  Hill Patel / stifler / hillaniljppatel@gmail.com
────────────────────────────────────────────────────────
  BLOCKED — remediation required    7 ok  2 warn  2 fail*
```

\* The runtime stage initially false-failed `gemini`/`claude` (registration is import-triggered; the
stage now imports all adapter modules first). After the fix the verdict's failing stage is **only**
Configuration (missing owner ids — the genuine A-001 blocker). See
`integration-status-report.md` for the remediation plan.

## 5. Tests

`tests/unit/test_onboarding.py` (5, DB-free): `_present` helper, **owner-ids fail-closed** surfaces
as FAIL, owner-ids-present OK, runtime+alias resolution, `summarize` counts. All green within the
219-test suite.

## 6. Design notes

- Zero new credential store — operator identity is in-session/report only; `.env` remains the single
  source of truth (constraint honored).
- Subsystem APIs reused as-is (`get_settings`, `build_scheduler`, `runtime_registry`,
  `create_engine`/`async_session_factory`, `get_session`) — no architecture change.
- Live-send capability is intentionally **not** implemented here; it is gated behind config
  remediation and a separate authorization.
