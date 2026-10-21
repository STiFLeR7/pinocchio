# 12 — Improvement Opportunities

> Read-only audit. Per Operating Rules, this lists **opportunities supported by evidence** — it does
> not authorize or perform changes. Each item ties to debt (`10`) / risk (`11`) IDs and cites code.
> Ordered by leverage (impact ÷ effort). Nothing here should be actioned until the audit is approved
> and a change is explicitly requested.

---

## Tier 1 — Highest leverage (small change, large risk/correctness payoff)

| # | Opportunity | Why (evidence) | Touch points |
|---|---|---|---|
| I-01 | **Fix the timeout field name** so runners read `gemini_timeout`/`claude_timeout`/`research_timeout`/`hard_limit` | TD-01/R-06: `getattr(..., "research_timeout_seconds", 300)` always returns 300 | `runners/claude.py:83`, `gemini.py:88` |
| I-02 | **Fail-closed on empty `owner_ids`** (refuse approvals / refuse boot without owners) | R-01: empty list disables auth | `approvals/service.py:94`, `bot.py:53`, `config.py:42` |
| I-03 | **Make `post_message` failures observable** (return/raise) so the outbox doesn't mark failed sends `sent` | R-04/TD-05 | `service.py:80-82`, `outbox.py:159` |
| I-04 | **Rotate `.env` secrets; ship `.env.example` with placeholders; stop baking secrets into images** | R-03/TD-06 | `.env`, `docker-compose.yml:16` |
| I-05 | **Synchronize the blueprint** (STATUS/ROADMAP/README/CHANGELOG) with Phase 2/3 + v1.0.0 | TD-09/R-17, Operating Rule 9 | `STATUS.md`, `ROADMAP.md`, `README.md`, `CHANGELOG.md` |

## Tier 2 — Activate the built-but-dormant autonomy layer

| # | Opportunity | Why (evidence) | Touch points |
|---|---|---|---|
| I-06 | **Wire APScheduler** (already a dependency) with a persistent job store to drive: hourly `sweep_expired_approvals`, hourly `run_aggregation_and_retention`, research crawl, daily briefing, heartbeat/orphan sweep | TD-02/TD-18/R-05/R-09; ADR-009, ADR-010, ADR-001 all assume it | new scheduling wiring; `approvals/service.py:184`, `metrics.py:142`, `research.py:218`, `briefing.py:74` |
| I-07 | **Subscribe to `RESEARCH_COMPLETED`** to chain research → briefing | TD-23; `research-workflow-design.md:58` | `orchestrator.py:46-52` |
| I-08 | **Add a startup recovery supervisor + orphan-execution monitor** keyed on `last_heartbeat` | TD-22/R-10; `docs/08:549-563` only partial | new startup hook; `executions`/`execution_steps`/`agent_steps` |
| I-09 | **Reconcile approval-expiration semantics** with ADR-009 (notify + review queue, no task-cancel) — or amend the ADR | TD-11 | `approvals/service.py:209-210`, `ADR-009` |

## Tier 3 — Runtime & execution hardening

| # | Opportunity | Why (evidence) | Touch points |
|---|---|---|---|
| I-10 | **Implement real Claude/Gemini CLI invocation, or rename them** to reflect generic-shell behavior | TD-04; `runtime-adapter-design.md:67-73` | `runners/claude.py:107`, `gemini.py:112` |
| I-11 | **Remove `AsyncMock` from production Nexus**; inject a test double; implement real `web_search` + `terminate()` | TD-04/R-16 | `nexus.py:7,76-86,183-209,310-312` |
| I-12 | **Default to an isolating sandbox** (or refuse host execution without explicit opt-in) | R-02/TD-03 | `config.py:101`, `manager.py:34-53` |
| I-13 | **Tokenize the command blacklist** (shlex/argv) instead of substring matching | TD-10 | `governance.py:620-621` |
| I-14 | **Subject Nexus `write_file`/`execute_command` to governance path containment** | TD (runtime) | `nexus.py:96-105,121` |
| I-15 | **Mark failed steps `FAILED`** instead of always `COMPLETED` | TD-21 | `runners/claude.py:142` |

## Tier 4 — Reliability of external I/O

| # | Opportunity | Why (evidence) | Touch points |
|---|---|---|---|
| I-16 | **Per-model OpenRouter timeout + bounded backoff + circuit breaker + `max_tokens`** | TD-13 | `openrouter.py:44-100` |
| I-17 | **Add leasing + `attempt_count` + dead-letter to the `system_events` outbox** (match `system_outbox`) | TD-16/R-14 | `outbox.py:171-212` |
| I-18 | **Stop using sync-flush as the briefing default** (use the resilient loop) | TD-17 | `briefing.py:201` |
| I-19 | **Escape feed/task content** in briefing HTML/markdown | TD-14/R-13 | `briefing.py:509-554` |
| I-20 | **Add Discord `on_disconnect`/`on_resumed` handlers** (at least logging) | TD-20 | `bot.py` |

## Tier 5 — Persistence, schema & DB

| # | Opportunity | Why (evidence) | Touch points |
|---|---|---|---|
| I-21 | **Generate Alembic migrations for the 6 missing tables + base `repository_registry`; stop relying on `create_all` in prod; add a migration round-trip test** | TD-07/R-08 | `alembic/versions/`, `api.py:81-83`, `conftest.py:59` |
| I-22 | **Add `PRAGMA synchronous=NORMAL`** to match ADR-002 | TD (db) | `database.py:103-105` |
| I-23 | **Normalize datetimes** to tz-aware `datetime.now(UTC)` | TD-31 | `models.py:237,259` |
| I-24 | **Audit-log compaction/vacuum strategy** for long pilots | R-11 | new; `manager.py` replay |

## Tier 6 — Boundaries, tests & hygiene

| # | Opportunity | Why (evidence) | Touch points |
|---|---|---|---|
| I-25 | **Move task CRUD / DB access out of the Discord adapter** (revisit the deferred Command Bus) | TD-15; `ADR-command-bus-evaluation.md` | `bot.py:70-98,237-279` |
| I-26 | **Implement ADR-007 `EmailProvider` protocol + ADR-008 `DiscordAuthGuard`** (+ audit unauthorized attempts) | TD-19 | `email/service.py`, `bot.py:52-57` |
| I-27 | **Add tests for Discord, Email, OpenRouter, Summary, scheduler** | `09`; planned files never created (`DEVELOPMENT.md:198-203`) | `tests/` |
| I-28 | **Enforce coverage threshold (`--cov-fail-under`) and upload coverage** | CI gap | `.github/workflows/ci.yml:42` |
| I-29 | **De-triplicate research persist/summarize logic** | TD-12 | `research.py:300-322,427-468,501-541` |
| I-30 | **Reconcile version, Python-floor, Ruff-config, and broken doc commands** | TD-24..27 | `pyproject.toml`, `ruff.toml`, `DEVELOPMENT.md` |
| I-31 | **Remove dead code** (`collector.py`, `briefing._deliver_discord`, selection prefix heuristic) | TD-23 | `collector.py:16`, `briefing.py:372`, `orchestrator.py:145` |

---

## Suggested sequencing (if/when implementation is authorized)

1. **Pre-pilot safety (Tier 1):** I-01..I-05 — small, high-leverage, mostly config/correctness.
2. **Make autonomy real (Tier 2):** I-06..I-09 — the scheduler unlocks the dormant engines and is
   the difference between "attended console" and "operational control plane."
3. **Harden execution & I/O (Tiers 3-4):** I-10..I-20.
4. **Schema/test/hygiene debt (Tiers 5-6):** I-21..I-31.

> Reminder (Operating Rules 1-7): these are *opportunities*, not a mandate. The highest-value
> immediate output of this audit is the synchronized understanding in docs `01`–`09`; implementation
> should be proposed and approved item-by-item, with evidence, after the audit is accepted.
