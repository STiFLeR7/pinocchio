# 11 — Open Risks

> Read-only audit. Risks are forward-looking failure scenarios for a pilot. Each combines a project
> self-documented risk (where one exists) with code evidence. Likelihood × Impact → Priority.

---

## Risk register

| ID | Risk | Likelihood | Impact | Priority | Evidence |
|---|---|---|---|---|---|
| R-01 | **Approval auth disabled by misconfiguration** — empty `owner_ids` lets anyone approve privileged execution | Med | Critical | 🔴 P0 | `config.py:42`, `approvals/service.py:94`, `bot.py:53` |
| R-02 | **Host compromise via default no-isolation sandbox + bypassable blacklist** | Med | Critical | 🔴 P0 | `config.py:101`, `provider.py:88`, `governance.py:621` |
| R-03 | **Credential exposure** — live-looking secrets on disk in `.env`, copied into Docker images via `env_file` | High | High | 🔴 P0 | `.env:1-19`, `docker-compose.yml:16` |
| R-04 | **Silent approval/alert loss when Discord is down** — outbox marks failed sends as `sent` | Med | High | 🔴 P0 | `service.py:80-82`, `outbox.py:159` |
| R-05 | **Tasks permanently stuck `BLOCKED`** — expiration sweep never runs | High | Med | 🟠 P1 | `approvals/service.py:184` (uncalled) |
| R-06 | **Long-running executions killed at 5 min** — timeout field-name bug | High | Med | 🟠 P1 | `runners/claude.py:83` vs `config.py:83` |
| R-07 | **SQLite write contention** under 3 loops + Discord + HTTP → `SQLITE_BUSY`, possible task-state corruption | Med | High | 🟠 P1 | `GAPS_AND_RISKS.md:277-281`, `gap-analysis.md:39-41`, `database.py:105` |
| R-08 | **Migration failure on fresh deploy** — `alembic upgrade head` fails (missing base-table migrations); only `create_all` works | High (if Alembic used) | High | 🟠 P1 | `api.py:81-83`, `models.py` (6 NO-MIGRATION tables) |
| R-09 | **Unattended operation silently does nothing** — operator expects autonomous research/briefings; none are scheduled | High | Med | 🟠 P1 | `research.py:218`, `briefing.py:74` (no trigger) |
| R-10 | **Background loop death is unrecovered** — no supervisor restarts outbox/metrics loops | Low | High | 🟠 P1 | `api.py:114-127` (bare asyncio tasks) |
| R-11 | **Audit log unbounded growth** degrades replay & disk over a long pilot — no vacuum/compaction | Med | Med | 🟡 P2 | `ADR-004:108-109`, `final-architecture-review.md:42` |
| R-12 | **Operator locked out of Discord = no emergency bypass** to approve/abort | Low | High | 🟡 P2 | `final-architecture-review.md:24` (no bypass path) |
| R-13 | **Content injection** — malicious RSS content rendered unescaped into briefing email/Discord | Low | Med | 🟡 P2 | `briefing.py:509-554` |
| R-14 | **Double-delivery / clogged sweep** on `system_events` outbox (no leasing/dead-letter) | Low | Med | 🟡 P2 | `outbox.py:184,161-168` |
| R-15 | **Discord rate-limit failures** under burst of approvals/notifications | Med | Low | 🟡 P2 | `GAPS_AND_RISKS.md:289-293` |
| R-16 | **Runaway agent cannot be stopped** — Nexus `terminate()` is a no-op; sandbox `terminate()` not awaited | Low | Med | 🟡 P2 | `nexus.py:310-312`, `provider.py:45-48` |
| R-17 | **Operator trusts stale blueprint** — STATUS/ROADMAP/README describe a different system state | High | Low | 🟡 P2 | `STATUS.md:58-68`, `README.md:5-6` |

---

## P0 risks — must be addressed before any non-trivial pilot

1. **R-01 Configure `owner_ids`.** Without it, the system's core safety guarantee (human approval)
   is silently off. This is the single highest-leverage pre-pilot action.
2. **R-02/R-03 Isolation & secrets.** Either restrict the pilot to fully trusted repos/commands on a
   disposable host, or enable the Docker sandbox provider; rotate all `.env` credentials and stop
   baking them into images.
3. **R-04 Discord delivery integrity.** Until `post_message` failures are observable, treat Discord
   delivery as best-effort and verify approvals landed; do not rely on it for anything critical.

## Risks the project already acknowledges (for traceability)

`blueprint/GAPS_AND_RISKS.md` and `blueprint/reports/gap-analysis.md` independently document:
SQLite concurrency (RISK-002 / GAP-001), Discord rate limits (RISK-003), execution timeout
(RISK-004, *believed resolved by ADR-010 — but see R-06, the resolution is not effective in code*),
secret management (RISK-005, *resolved as "gitignored `.env`" — but see R-03*), outbox publisher
(GAP-002, *resolved*), subprocess buffer limits (GAP-003), retry states (GAP-004), and deferred
multi-tenant/vector memory (GAP-006/007). The notable finding of this audit is that **two risks the
project marks "resolved" (timeout, secrets) are not actually mitigated in the shipped code.**

## Risk posture conclusion

The risk profile is **concentrated in configuration and the autonomy/recovery gap**, not in the core
spine. A disciplined operator on a trusted, isolated host with `owner_ids` set and credentials
rotated can run a meaningful attended pilot at acceptable risk. Continuous, unattended, or
multi-tenant operation is materially riskier until the P0/P1 items are addressed.
