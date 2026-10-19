# 01 — System Understanding

> Onboarding audit of Nexus **v1.0.0** (git tag `v1.0.0`, commit `aa3e527`). Read-only. Every
> non-trivial claim is cited to `file:line` or a commit hash. This document is descriptive, not
> prescriptive — it records what Nexus *is*, not what it should become.

---

## 1. What Nexus actually is

Nexus is a **single-operator AI Orchestration Control Plane**: a long-lived Python process that
coordinates tasks, approvals, agent execution, research, and reporting through a deterministic,
auditable, event-sourced workflow engine. The product thesis is explicit and consistently held
throughout the codebase: *"Conversation is a feature. Orchestration is the product."*
(`docs/00_BRIEF.md:158-161`); *"AI assists the system. AI does not control the system."*
(`docs/01_ARCHITECTURE.md:706-711`).

Concretely, the running system is:

- A **FastAPI ASGI application** (`nexus/api.py:251`, entrypoint `python -m nexus` →
  `nexus/__main__.py:34-40`) that boots a database, an in-process event bus, a Discord bot,
  background outbox/metrics loops, and a workflow orchestrator inside one lifespan
  (`nexus/api.py:65-138`).
- A **SQLite (WAL) database** as the single source of truth (`nexus/database.py:100-106`,
  `nexus/config.py:76`), with an immutable append-only audit log
  (`nexus/memory/models.py:184-199`).
- A **Discord-first human interface** for task entry and approval decisions
  (`nexus/communication/discord/bot.py:225-328`, `nexus/communication/discord/service.py:84-113`).
- A **runtime execution layer** that runs agent/CLI commands behind a hard approval + governance
  gate (`nexus/execution/service.py:43-45`, `nexus/execution/governance.py:60-653`).

## 2. The problem it solves

Modern AI tooling is fragmented — chat in one place, tasks in another, approvals tracked manually,
agents run from terminals with no audit trail (`docs/00_BRIEF.md:65-90`). Nexus centralizes that
operational surface into one governed control plane so that a single power user (the brief names
*Hill Patel*, `docs/00_BRIEF.md:164-178`) can delegate work, approve privileged actions through
Discord, run AI agents against allow-listed repositories, and receive intelligence digests — while
**every action is persisted and auditable** and **nothing executes without human approval**.

The design north star: behave like a *trusted Chief of Staff* that remembers context, tracks
commitments, and coordinates execution while remaining under human governance
(`docs/00_BRIEF.md:96-110`).

## 3. The single most important onboarding fact: docs describe more than the code runs

Nexus v1.0.0 is a **genuinely strong, well-governed core** wrapped in **documentation and design
artifacts that describe a more complete system than is wired into the running process.** An operator
or developer onboarding here must internalize this gap immediately, because the blueprint reads as
authoritative but is, in several load-bearing places, *aspirational or stale*.

The clearest, evidence-backed examples:

| Documented as present | Code reality | Evidence |
|---|---|---|
| Phase 2–7 "Not Started"; only Phase 1 + 8 complete | Phases 2 & 3 shipped: Discord, runtimes, governance, research, briefings; tagged v1.0.0 | `blueprint/STATUS.md:58-68` vs `git log` (`8c31e10`, `23c5a02`..`4566020`) |
| APScheduler-driven cron (research jobs, daily briefing, hourly approval sweep, heartbeat sweeper) | **No scheduler exists in `nexus/`** — only `asyncio` poll loops | Zero matches for `apscheduler|add_job|CronTrigger` in `nexus/`; `nexus/api.py:114-127` |
| Research + Briefing engines run autonomously | Both engines are fully built but **have no production trigger** — only tests and resume call them | `nexus/intelligence/research.py:218`, `briefing.py:74` (no scheduler/listener invokes them) |
| Approval expiration runs hourly | `sweep_expired_approvals` is **never called in production** | `nexus/approvals/service.py:184` (callers only in `scripts/`, `tests/`) |
| Claude Code / Gemini CLI adapters invoke their binaries | Both are **generic shell runners**; no `claude-code`/`gemini` binary is invoked | `nexus/execution/runners/claude.py:107`, `gemini.py:112` |
| Nexus is a real agent runtime | Nexus has a real loop scaffold but a **hardcoded plan, canned search, and an `AsyncMock` simulation branch in production code** | `nexus/execution/runners/nexus.py:7,145-149,183-209` |
| Subsystems operational | `/api/v1/status` reports gateway/communication/intelligence/execution/agents/scheduling as literal `"stub"` | `nexus/api.py:223-228` |

None of this makes Nexus a prototype — the **core orchestration spine (task → approval gate →
governed execution → audit → summary) is real, tested, and runs end-to-end** (see
`tests/e2e/test_mvp_workflow.py:73-213`). But "v1.0.0 / approved for pilot" should be read as
*"the governed execution core is pilot-ready; the autonomous-operation and multi-runtime layers are
partially wired."*

## 4. What genuinely works end-to-end today

Verified by the e2e test and integration test plus source reading:

1. A task is ingested (Discord `/task_create` or programmatic `TaskService.create_task`,
   `bot.py:225-260`, `task_service.py:55-100`) and persisted.
2. Queuing emits an event; the orchestrator creates an approval request and forces the task to
   `BLOCKED` (`orchestrator.py:54-77`, `approvals/service.py:54-58`).
3. The approval request is delivered to Discord as an embed with Approve/Reject buttons
   (`discord/service.py:84-113`, `bot.py:104-128`).
4. Only a configured owner can decide (`bot.py:52-58`, `approvals/service.py:94-95`).
5. On approval, execution runs **only after** `check_approval_gate` passes — execution cannot
   bypass approval (`execution/service.py:43-45`). The governance gate then enforces 11 ordered
   checks (`execution/governance.py:60-653`).
6. Output is persisted (logs, diff, summary artifacts), the task is finalized, and an LLM-generated
   summary is posted to Discord (`orchestrator.py:221-246,298-311`).
7. State survives restart: checkpoints + audit-log replay rebuild context
   (`memory/manager.py:28-101`); the outbox redelivers undelivered messages
   (`gateway/communication_outbox.py:79-243`).

## 5. What is built but not wired (latent capability)

These subsystems are implemented to a high standard but lack a production trigger or have a
disconnected dependency:

- **Research Engine** (`intelligence/research.py`) — full RSS crawl → dedup → LLM summarize →
  persist → checkpointed resume. No scheduler calls it; `RESEARCH_COMPLETED` has no subscriber.
- **Briefing Engine** (`intelligence/briefing.py`) — full operational digest aggregation, markdown
  + HTML render, outbox delivery. No scheduler calls it.
- **Metrics aggregation/retention** (`core/metrics.py:142`) — only the raw flush loop runs; the
  hourly aggregate + retention purge is never invoked, so the aggregate table stays empty.
- **Approval expiration sweep** (`approvals/service.py:184`) — never scheduled; expired approvals
  can leave tasks `BLOCKED` indefinitely.

## 6. How to read the rest of this onboarding set

- `02-architecture-map.md` — the layered architecture and the actual package→layer mapping.
- `03-runtime-map.md` — runtime registry, selection, adapters, sandbox (Architecture Review).
- `04-governance-map.md` — the governance gate, approval enforcement, policy service, ADR model.
- `05-memory-map.md` — event sourcing, checkpoints, recovery framework.
- `06-database-map.md` — full table catalog and the `create_all`-vs-Alembic divergence.
- `07-event-flow-map.md` — event model and the two outboxes.
- `08-integration-map.md` — Discord, Email, OpenRouter.
- `09-operational-capabilities.md` — readiness per operational capability.
- `10`–`12` — technical debt, open risks, improvement opportunities (evidence-gated).
- `13`/`14` — first-week operator and developer guides.
- `15-onboarding-summary.md` and root `NEXUS_FIRST_IMPRESSION.md` — the synthesis.
