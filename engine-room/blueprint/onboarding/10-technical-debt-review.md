# 10 — Technical Debt Review

> Read-only audit. Consolidated, evidence-backed technical debt. Severity reflects pilot impact.
> This document **describes** debt; it does not authorize changes (Operating Rule 1).

---

## Severity legend
🔴 High (correctness/security/operability) · 🟡 Medium (reliability/maintainability) · 🟢 Low (hygiene)

---

## 🔴 High-severity debt

| ID | Item | Evidence | Impact |
|---|---|---|---|
| TD-01 | **Execution timeout bug** — runners read `research_timeout_seconds` which doesn't exist on `ExecutionConfig`; always falls back to 300s, ignoring ADR-010 tiers | `runners/claude.py:83`, `gemini.py:88` vs `config.py:83-86` | Every CLI run capped at 5 min regardless of config; long jobs killed |
| TD-02 | **No scheduler** — APScheduler is a dependency but no scheduler/job exists; cron-driven work (research, briefing, expiration sweep, aggregation, heartbeat) never fires | zero matches in `nexus/`; `api.py:114-127` | Autonomy + continuous operation impossible |
| TD-03 | **Default sandbox = zero isolation** — commands run directly on host | `config.py:101-102`, `provider.py:88-101` | Only the (bypassable) blacklist protects the host |
| TD-04 | **`AsyncMock` imported & used in production Nexus** + hardcoded plan/canned search | `nexus.py:7,145-149,183-209` | Nexus is partly a simulation, not a real agent |
| TD-05 | **Silent Discord message loss** — `post_message` swallows errors → `None` → outbox marks row `sent` | `service.py:80-82`, `outbox.py:159,191-194` | Approval requests/alerts dropped when Discord down |
| TD-06 | **Committed live-looking secrets in `.env`** (Groq/OpenRouter/Resend keys, Discord token, SMTP password) | `.env:1-19` (gitignored, not tracked) | On-disk + image exposure; treat as compromised, rotate |
| TD-07 | **Migrations incomplete & never validated** — 6 tables (incl. base `repository_registry`) have no migration; prod schema via `create_all`; tests bypass Alembic | `api.py:81-83`, `conftest.py:59`, `models.py` | `alembic upgrade head` fails on clean DB; PostgreSQL path blocked |
| TD-08 | **Empty `owner_ids` disables approval auth** | `config.py:42`, `approvals/service.py:94`, `bot.py:53` | Misconfig → anyone can approve |

## 🟡 Medium-severity debt

| ID | Item | Evidence | Impact |
|---|---|---|---|
| TD-09 | **Blueprint/code desync** — STATUS/ROADMAP/README/CHANGELOG predate Phase 2/3 & v1.0.0 | `STATUS.md:58-68`, `README.md:5-6,146-153`, `CHANGELOG.md:9-39` | Violates Operating Rule 9; misleads onboarding |
| TD-10 | **Substring command blacklist** — bypassable & over-broad | `governance.py:621`, `policy_defaults.py:9` | Weak last line of host defense |
| TD-11 | **Approval expiration semantics conflict** — code cancels task; ADR-009 says notify+review-queue, no auto-reject | `approvals/service.py:209-210` vs `ADR-009:11-15` | Behavior contradicts accepted decision |
| TD-12 | **Research persist/summarize logic triplicated** | `research.py:300-322,427-468,501-541` | Bug fixes must be applied 3× |
| TD-13 | **OpenRouter total-timeout + no backoff/circuit-breaker/`max_tokens`** | `openrouter.py:44-100` | Slow primary starves fallbacks; cost runaway |
| TD-14 | **HTML/markdown injection** from unescaped feed/task content in briefings | `briefing.py:509-554` | Untrusted content → email/Discord |
| TD-15 | **Business logic + DB access inside Discord adapter** | `bot.py:70-98,237-279` | Violates adapter boundary; Command Bus deferred (`ADR-command-bus-evaluation.md`) |
| TD-16 | **`system_events` outbox lacks leasing/attempts/dead-letter** (unlike `system_outbox`) | `outbox.py:184,161-168` | Double-send across instances; permanent-fail clogs sweep |
| TD-17 | **Sync-flush is the briefing default** — dead-letters on first failure, bypassing the resilient loop | `briefing.py:201`, `communication_outbox.py:274-276` | No retry for briefing delivery |
| TD-18 | **Metrics aggregation/retention never invoked** | `metrics.py:142` uncalled | Aggregate table empty; raw rows never purged; unbounded `_write_buffer` under DB outage |
| TD-19 | **ADR-007 `EmailProvider` & ADR-008 `DiscordAuthGuard` abstractions missing** | `email/service.py`, `bot.py:52-57` | Accepted ADRs unimplemented; provider swap requires rewrite |
| TD-20 | **No reconnect handlers for Discord** | grep: none | No observability of disconnects |
| TD-21 | **Steps always marked COMPLETED on failure** | `runners/claude.py:142` | Failure only visible via exit code |
| TD-22 | **No generic startup recovery supervisor / orphan-execution monitor** | `api.py:65-99` | Stalled runs not reaped; `docs/08:549-563` flow only partial |
| TD-23 | **Dead code** — `sandbox/collector.py` artifact copy-back; `briefing._deliver_discord`; selection description-prefix heuristic the ADR said it removed | `collector.py:16`, `briefing.py:372`, `orchestrator.py:145-152` | Confusion; Docker artifacts never collected |

## 🟢 Low-severity / hygiene debt

| ID | Item | Evidence |
|---|---|---|
| TD-24 | Version incoherence — tag v1.0.0 but `pyproject.toml:3` = 0.1.0, `config.version`="0.1.0", two version sources | `pyproject.toml:3`, `config.py:143`, `api.py:19` |
| TD-25 | Python floor mismatch — `requires-python>=3.12` vs docs "3.11+" | `pyproject.toml:6` vs `README.md:7` |
| TD-26 | Duplicate Ruff config — `ruff.toml` shadows `[tool.ruff]` in pyproject (dead block) | `ruff.toml` vs `pyproject.toml:55-60` |
| TD-27 | Broken doc command — `python -m nexus --health-check` ignored by `__main__` | `DEVELOPMENT.md:52` vs `__main__.py:34-40` |
| TD-28 | Hardcoded uvicorn host/port; hardcoded default `echo` command | `__main__.py:34-40`, `orchestrator.py:145` |
| TD-29 | Doc GAP-001/002/003 (duplicate/mislabeled docs) still Open | `GAPS_AND_RISKS.md:23-71` |
| TD-30 | ADR numbering collisions (ADR-015 twice; several runtime ADRs unnumbered) | `blueprint/DECISIONS/` |
| TD-31 | Naive vs tz-aware datetime mixing | `models.py:237,259` |
| TD-32 | `_validate_policy_schema` skips `concurrency_retry_*` keys | `policy_service.py:209-224,244-245` |
| TD-33 | Empty email templates dir despite Jinja2 dep | `templates/email/` (.gitkeep), `pyproject.toml:20` |

---

## Debt themes

1. **Aspirational docs vs shipped code** is the dominant theme — TD-02, TD-04, TD-09, TD-11, TD-18,
   TD-19, TD-23. The blueprint repeatedly describes capabilities that exist as design or stub.
2. **The autonomy layer is unwired** — TD-02, TD-18, TD-22 plus dormant research/briefing engines.
3. **Reliability edges around external I/O** — TD-05, TD-13, TD-16, TD-17, TD-20.
4. **Security hardening gaps** — TD-03, TD-06, TD-08, TD-10, TD-14, TD-19.

None of these are hidden behind `TODO` markers — across `nexus/` the only literal stub strings are
the six `"stub"` subsystem labels in `api.py:223-228`. The debt is **silent** (dead-but-defined
functions, wrong field names, unwired engines), which makes this written inventory the primary map.
