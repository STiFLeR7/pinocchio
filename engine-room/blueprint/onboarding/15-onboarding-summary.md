# 15 — Onboarding Summary

> Read-only audit synthesis of Nexus v1.0.0 (commit `aa3e527`, tag `v1.0.0`). Consolidates docs
> `01`–`14`. Evidence-backed throughout.

---

## 1. One-paragraph synthesis

Nexus is a **single-operator AI Orchestration Control Plane**: an event-driven, event-sourced Python
service whose product is *governed orchestration*, not conversation. Its core spine —
task → human approval → governed execution → immutable audit → AI summary — is **real, layered,
transactional, and tested at unit/integration/e2e levels**, and its governance and memory
architecture are genuinely well-engineered. However, the documentation describes a **more complete
system than the code runs**: the scheduling layer is absent (no APScheduler despite the dependency),
the research and briefing engines are fully built but never triggered, the Claude/Gemini "runtimes"
are generic shell runners, Nexus is partly simulated (including `AsyncMock` in production), and the
blueprint state files (STATUS/ROADMAP/README) are stale relative to the shipped Phase 2/3 work. The
accurate framing of v1.0.0 is: **a pilot-ready, attended, governed-execution kernel with autonomy as
the clearly-designed next milestone.**

## 2. What this audit produced

`blueprint/onboarding/01`–`15` plus root `NEXUS_FIRST_IMPRESSION.md`. The Architecture Review of all
ten brief-mandated subsystems is distributed across:
- Runtime Registry, Runtime Selection, Sandbox Manager → `03-runtime-map.md`
- Governance Layer → `04-governance-map.md`
- Memory Layer, Recovery Framework → `05-memory-map.md`
- Metrics Persistence → `04`/`09` (and below)
- Outbox → `07-event-flow-map.md`
- Research Engine, Briefing Engine → `08-integration-map.md`

## 3. Subsystem verdict table

| Subsystem | Engineering quality | Operational status | Key evidence |
|---|---|---|---|
| Approval gate | Excellent | ✅ Live, un-bypassable | `execution/service.py:43-45` |
| Runtime governance (11-gate) | Excellent | ✅ Live, 12 tests | `governance.py:60-653` |
| Memory / event sourcing | Excellent | ✅ Live | `memory/manager.py:28-101` |
| Database (SQLite/WAL) | Good | ✅ Live (⚠ migration drift) | `database.py:100-106`, `api.py:81-83` |
| Communication Outbox | Excellent | 🟡 Live but bypassed by sync-flush default | `communication_outbox.py:79-243`, `briefing.py:201` |
| System-events Outbox | Adequate | 🟡 Live but lossy on Discord outage | `outbox.py:159` |
| Runtime Registry/Selection | Excellent abstraction | 🟡 Selection still uses id+prefix | `runners/__init__.py`, `orchestrator.py:143-152` |
| Runners (Claude/Gemini/Nexus) | Mixed | 🟡 Shell stubs / partly simulated | `claude.py:107`, `nexus.py:183-209` |
| Sandbox Manager | Good abstraction | 🟡 Default = no isolation | `manager.py:34-53`, `config.py:101` |
| Metrics persistence | Good | 🟡 Raw flush only; aggregation uncalled | `metrics.py:123` vs `:142` |
| Research Engine | Good | 🔴 Built, never triggered | `research.py:218` |
| Briefing Engine | Good | 🔴 Built, never triggered | `briefing.py:74` |
| Scheduler | — | 🔴 Does not exist | no `apscheduler` in `nexus/` |
| Recovery supervisor | — | 🔴 Partial (no orphan reaper/auto-resume) | `api.py:65-99` |

## 4. The five things every newcomer must internalize

1. **The approval gate is the product's spine and it genuinely works** — DB-backed, owner-authorized,
   un-bypassable (`execution/service.py:43-45`). Protect it above all.
2. **Docs ≠ code.** STATUS/ROADMAP/README are stale; ADRs/designs describe unbuilt or stubbed
   features. Trust source over blueprint, and cross-check (this audit set does).
3. **There is no scheduler.** Anything "daily" or "hourly" (briefings, research, expiry, aggregation)
   does **not** run autonomously today.
4. **Configuration is split and safety depends on it** — set `owner_ids` (else auth is off), and
   know the default sandbox runs on the host with no isolation.
5. **It's event-driven + event-sourced.** Trace events and the audit log, not the call stack.

## 5. Gap-analysis rollup (per the brief's six lenses)

- **Excellent:** approval gate, 11-gate governance, immutable audit ledger, transactional outboxes,
  event-sourced recovery, runtime/adapter abstraction, structured logging.
- **Missing:** scheduler; autonomy triggers; recovery supervisor/orphan monitor; ADR-007/008
  abstractions; real CLI integrations; tests for Discord/Email/OpenRouter/Summary.
- **Risky:** empty-owner auth bypass; host execution + bypassable blacklist; on-disk secrets;
  silent Discord loss; 5-min timeout bug; SQLite contention; migration drift.
- **Never change:** approval gate, audit immutability, transactional outbox, fail-closed policy
  reads, terminal task-state sinks, semaphore release symmetry.
- **Monitor:** SQLite locks; outbox dead-letters/backlog; stuck `BLOCKED` tasks; stale heartbeats;
  audit-log growth; the already-emitted latency metrics.
- **Improve:** see `12-improvement-opportunities.md` (Tier 1 pre-pilot fixes are small & high-value).

## 6. Recommended next focus (after audit acceptance)

The highest-leverage next step is **not** new features — it is **closing the doc/code gap and
activating the dormant autonomy layer**:
1. Tier-1 pre-pilot safety fixes (timeout field name, fail-closed owners, secret rotation, blueprint
   sync) — small, evidence-clear, high-impact (`12`, I-01..I-05).
2. Wire APScheduler to bring research/briefing/expiration/aggregation to life (`12`, I-06..I-09) —
   this is the difference between an attended console and an operational control plane.

> Per Operating Rules, implementation is proposed only **after** this audit is accepted. The primary
> deliverable is shared, evidence-based understanding — which this onboarding set now provides.
