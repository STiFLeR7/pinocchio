# 09 — Operational Capabilities & Readiness Review

> Read-only audit. Evaluates whether Nexus v1.0.0 is genuinely ready for each operational capability
> the brief lists. Every verdict is evidence-backed. Verdicts: ✅ Ready · 🟡 Partial · 🔴 Not ready.

---

## Summary scorecard

| Capability | Verdict | One-line basis |
|---|---|---|
| Daily usage (task + approval + execution) | 🟡 Partial | Spine works & is tested, but runners are generic shell + timeout bug |
| Continuous operation (run unattended for days) | 🔴 Not ready | No scheduler, no expiration sweep, no orphan monitor, no process supervisor |
| Autonomous research | 🔴 Not ready | Engine fully built but **never triggered**; RSS-only |
| Task management | ✅ Ready | Full lifecycle, state machine, persistence, audit, Discord CRUD |
| Approval workflows | ✅ Ready (core) / 🟡 (expiry) | Un-bypassable gate + owner auth; but expiration never sweeps |
| Multi-runtime execution | 🟡 Partial | Registry/governance excellent; adapters are shell stubs / partly simulated |

---

## 1. Daily usage — 🟡 Partial

**Works:** The task→approval→governed-execution→summary path runs end-to-end and is covered by an
e2e test that exercises the full lifecycle with a real `cmd:echo` execution
(`tests/e2e/test_mvp_workflow.py:73-213`). Tasks persist, approvals gate execution, governance
enforces 11 checks, summaries post to Discord.

**Caveats:** (a) "Claude"/"Gemini" runtimes are generic shell runners, not real CLI integrations
(`runners/claude.py:107`, `gemini.py:112`); (b) the execution timeout is stuck at 300s for all
runtimes due to a config field-name bug (`runners/claude.py:83` vs `config.py:83`); (c) the default
sandbox provides **no isolation** — commands run on the host (`config.py:101`), so daily use depends
heavily on the governance blacklist, which is substring-based and bypassable
(`governance.py:621`).

**Verdict:** usable for a careful single operator on trusted repos; not yet "set and forget."

## 2. Continuous / unattended operation — 🔴 Not ready

The brief's success criterion is "the system can run unattended" (`docs/00_BRIEF.md:469`). Today:
- **No scheduler** — APScheduler is a dependency but unused; only three asyncio poll loops run
  (`api.py:114-127`). Nothing fires time-based work.
- **Approval expiration never sweeps** — tasks can hang in `BLOCKED` indefinitely
  (`approvals/service.py:184`, never scheduled).
- **No orphan-execution monitor** — `last_heartbeat` columns exist but nothing reaps stalled runs.
- **No process supervisor** — `__main__` hardcodes host/port and there is no systemd/NSSM config;
  Docker has `restart: unless-stopped` but the image lacks the CLI binaries execution needs
  (`ADR-011:17-24`).
- **Background loops have no supervisor** — if `publish_outbox_loop`/metrics loop dies, nothing
  restarts it.

**Verdict:** Nexus must currently be operated as an *attended* process.

## 3. Autonomous research — 🔴 Not ready

The Research Engine is fully implemented (crawl → dedup → summarize → persist → resumable,
`research.py:218-475`) but **has no production trigger** — only tests and `resume_research_run`
invoke it, and `RESEARCH_COMPLETED` has no subscriber. It is also RSS/Atom-only; the search-API/arXiv
providers are doc-only. Autonomous research is *latent capability*, not an operational feature.

## 4. Task management — ✅ Ready

Full lifecycle state machine with guarded transitions and irreversible terminal states
(`task_service.py:25-38`), `with_for_update` locking, complete audit trail, and Discord CRUD
(`/task_create`, `/task_list`, `/task_status`). Persistence survives restart. This is genuinely
production-quality.

## 5. Approval workflows — ✅ core / 🟡 expiration

The approval gate is the strongest part of Nexus: un-bypassable, DB-backed, owner-authorized,
concurrency-safe, fully audited (`execution/service.py:43-45`, `approvals/service.py:85-181`), with
12 governance tests. **Caveats:** expiration is never swept (tasks strand in `BLOCKED`); empty
`owner_ids` disables auth (`config.py:42`); unauthorized Discord attempts aren't audited
(ADR-008 gap). Configure `owner_ids` before any pilot.

## 6. Multi-runtime execution — 🟡 Partial

The registry + adapter-split + governance abstraction is excellent and extensible
(`runners/__init__.py`, `runners/base.py`). But the concrete runtimes are: Claude/Gemini = identical
generic shell runners (no binary invoked); Nexus = real loop scaffold with hardcoded plan, canned
search, and an `AsyncMock` simulation branch in production (`nexus.py:7,145-209`). "Multi-runtime"
is architecturally real but functionally shallow today.

---

## Cross-cutting operational facts

- **Health** is a process-global boolean set once at boot from a `git --version` probe
  (`health.py:49-71`); it is **never re-checked** and does not probe the DB/Discord/OpenRouter live.
  `/health` returns 503 when the flag is false (`api.py:186-200`); `/api/v1/status` reports all
  subsystems as literal `"stub"` (`api.py:223-228`).
- **Metrics** are collected and flushed every 5s (`metrics.py:123`), but **aggregation + retention
  never run** (`metrics.py:142` uncalled), so the aggregate table stays empty and raw rows are never
  purged. In-memory deques are lost on restart.
- **Auditability is genuinely strong** — every governance decision, state transition, and
  notification outcome writes an immutable `audit_log` row. This is the operational bedrock.
- **Configuration is split** between a flat `.env` (Groq/Resend/Discord channel vars) and a nested
  `config/settings.yaml` schema — the two do not share keys, a real misconfiguration trap (see
  `13-first-week-operator-guide.md`).

---

## Pilot-readiness conclusion

Nexus v1.0.0 is **pilot-ready as an attended, single-operator governed-execution console** for
running approved commands against allow-listed repositories with a full audit trail. It is **not yet
ready as an autonomous, continuously-operating research/briefing platform** — those subsystems are
built but un-triggered, and the scheduling/recovery infrastructure that would make unattended
operation safe is absent. The right pilot framing is: *"governed execution kernel, operated by a
human, with autonomy as the next milestone."*
