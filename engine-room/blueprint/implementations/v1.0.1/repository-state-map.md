# Repository State Map (AP-104)

> Ground-truth snapshot of the Nexus repository as it actually exists on disk at the time of the
> v1.0.1 "Alignment" documentation pass. Every entry is first-hand (file tree + source inspection),
> not derived from prior documentation. This document is the reference reality that
> `documentation-drift-analysis.md` measures the docs against.
>
> **Commit basis:** `master` @ `aa3e527` · **Release tag:** `v1.0.0` · **Active line:** v1.0.1 Alignment.

---

## 1. Version reality (authoritative)

| Signal | Value | Source |
|---|---|---|
| Git release tag | `v1.0.0` | `git tag -l` |
| `nexus.__version__` | `0.1.0` | `nexus/__init__.py` |
| `pyproject` version | `0.1.0` | `pyproject.toml` |
| `requires-python` | `>=3.12` | `pyproject.toml` |
| README badge | `pre-alpha` / `0.1.0` / `3.11+` | `README.md:5-7` |

**Finding:** four different version stories coexist. The repository is *released as v1.0.0* (tag,
audit basis, CHANGELOG of record) but the **in-code version string is still `0.1.0`**. The in-code
string is **source/config, not documentation** — correcting it is out of AP-104 scope and is logged
as residual debt (see `documentation-drift-analysis.md` §Residual).

## 2. Source tree (`nexus/`) — what is actually built

| Package | Present | Role (verified) |
|---|---|---|
| `api.py` | ✅ | FastAPI app, lifespan wiring (DB, outbox, metrics, **scheduler**, Discord) |
| `config.py` | ✅ | Pydantic settings incl. `SchedulingConfig`, `SandboxConfig`, `ExecutionConfig` |
| `core/` | ✅ | types/events, exceptions, metrics, health |
| `database.py` | ✅ | async engine, `get_session`, SQLite/WAL |
| `approvals/` | ✅ | approval engine — **fail-closed** owner auth (`service.py:96-102`) |
| `execution/` | ✅ | service (approval gate), `governance.py` (11-gate), `runners/` |
| `execution/runners/` | ✅ | `base.py`, `claude.py`, `gemini.py`, `nexus.py` + `resolve_execution_timeout` |
| `gateway/` | ✅ | EventGateway, transactional outbox, communication outbox, **`outbox_health.py`** |
| `intelligence/` | ✅ | OpenRouter client / model routing |
| `memory/` | ✅ | event-sourced manager, models, services, **`checkpoint_health.py`** |
| `communication/` | ✅ | Discord bot/service, email service |
| `agents/` | ✅ | agent definitions |
| `scheduling/` | ✅ | **`scheduler.py`, `jobs.py`, `orchestrator.py`** — APScheduler foundation (v1.0.1) |

**Key deltas vs the system the blueprint STATUS/ROADMAP describe:** the entire
approval/execution/governance/runtime/research/briefing/outbox/metrics/scheduler surface exists.
The blueprint state docs describe a system that stops at "Phase 1 — Core Infrastructure."

## 3. Subsystem presence vs the brief's capability list

| Capability | On disk? | Primary evidence |
|---|---|---|
| Runtime Registry + adapter split | ✅ | `runners/__init__.py`, `runners/base.py` (CLI/Agent adapters) |
| Gemini Runtime | ✅ (shell) | `runners/gemini.py` |
| Claude Runtime | ✅ (shell) | `runners/claude.py` |
| Nexus Runtime | ✅ (simulated branches) | `runners/nexus.py` (AsyncMock branch) — full audit deferred to AP-105 |
| Governance Layer (11-gate) | ✅ | `execution/governance.py` |
| Approval Workflows | ✅ | `approvals/service.py`, `execution/service.py:43-45` |
| Memory System (event-sourced) | ✅ | `memory/manager.py`, `memory/models.py` |
| Research Engine | ✅ | `intelligence`/research service |
| Daily Briefing Engine | ✅ | briefing service |
| Communication Outbox | ✅ | `gateway/communication_outbox.py` |
| Metrics Persistence | ✅ | `core/metrics.py` (+ aggregation now scheduled) |
| Scheduler Foundation | ✅ (v1.0.1) | `scheduling/scheduler.py`, `jobs.py` |
| Sandbox Isolation | ✅ (default off) | `config.py:133-137` (`provider="local"`) |

## 4. v1.0.1 Alignment changes already landed (this release line)

| Finding | Change | Evidence |
|---|---|---|
| A-001 fail-open owner auth | Fail-closed at startup **and** in approval engine | `api.py:67-82`, `approvals/service.py:96-102` |
| A-002 timeout field bug | `resolve_execution_timeout(...)` clamped to `hard_limit` | `runners/base.py:9-27`, `claude.py:81`, `gemini.py:86`, `nexus.py:15` |
| A-003 missing scheduler | APScheduler foundation, 6 jobs, audited | `scheduling/` (AP-103B reports) |

A-004 (this doc pass), A-005 (Nexus audit, AP-105), A-006 (sandbox review) remain.

## 5. Documentation surface (what exists to align)

| Location | Files | Drift posture |
|---|---|---|
| Root | `README.md`, `CHANGELOG.md`, `ONBOARDING.md`, `DEVELOPMENT.md`, `NEXUS_FIRST_IMPRESSION.md` | README/CHANGELOG severely stale |
| `blueprint/` | `STATUS.md`, `ROADMAP.md`, `README.md`, `GAPS_AND_RISKS.md` | STATUS/ROADMAP severely stale; README landing lists 3 of 21 ADRs |
| `blueprint/DECISIONS/` | 21 ADRs | Current (authoritative) |
| `blueprint/onboarding/` | 15 audit docs + `NEXUS_FIRST_IMPRESSION.md` | Current (authoritative reality source) |
| `blueprint/implementations/` | v1.0.0 reports + `v1.0.1/` | Current |
| `docs/` | 9 numbered design docs + `RULES.md` | Design-intent docs; describe target architecture (see drift analysis for "planned-as-built" cases) |

## 6. ADR inventory (21 — the real decision record)

`ADR-001-tech-stack` · `002-database-choice` · `003-pi-evaluation` · `004-memory-architecture` ·
`005-agent-routing` · `006-approved-tech-stack` · `007-email-provider` · `008-discord-authorization` ·
`009-approval-expiration` · `010-execution-timeouts` · `011-local-first-deployment` ·
`command-bus-evaluation` · `final-preimplementation-review` · `nexus-runtime-evaluation` ·
`phase1-foundation` · `phase1-retrospective` · `pi-core-patterns` · `runtime-abstraction-validation` ·
`runtime-foundations` · `runtime-selection` · `runtime-v2` · `scheduler-foundation`.

The blueprint landing page (`blueprint/README.md:21-27`) lists only ADR-001..003 — itself a drift item.
