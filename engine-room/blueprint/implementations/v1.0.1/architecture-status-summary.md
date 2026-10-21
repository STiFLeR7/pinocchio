# Architecture Status Summary (AP-104)

> **The single source of truth for subsystem status.** Every subsystem is classified with evidence.
> When any other document (README, STATUS) states a subsystem's status, it must agree with this file.
>
> **Basis:** Nexus v1.0.0 (tag) + v1.0.1 Alignment. Reality verified first-hand and cross-checked
> against the accepted onboarding audit (`blueprint/onboarding/`).
>
> **v1.1.0 "Containment" — Track S update (2026-06-24):** the **Sandbox Isolation** row is upgraded
> **Experimental → Pilot Safe** per the accepted Track S closure (S-2/S-3/S-4) and
> `ADR-sandbox-pilot-safe`. This change is evidence-bound to the Track S source (default-secure
> fail-closed resolution, startup validation, workspace confinement) and is **effective on commit** of
> Track S to `v1.1.0-planning`.
>
> **v1.1.0 "Containment" — Track H / H-2 update (2026-06-24):** the **Nexus Runtime** row is upgraded
> **Mocked/Prototype → Experimental** per the accepted H-2 closure and `ADR-hermes-experimental`
> (no prod mock, provider-backed search, goal-derived planning, structured tool-calls, truthful exit
> status). Evidence-bound to the H-2 source; **effective on commit**. Lifecycle safety
> (terminate/resume) remains the Pilot bar (H-4). No other subsystem row changes.

---

## Classification scale

| Class | Meaning |
|---|---|
| **Production Ready** | Built, tested, safe, and genuinely relied upon in the governed path |
| **Operational** | Built and working in-process; fit for attended/pilot use |
| **Experimental** | Built but unproven / unsafe-by-default / needs review before trust |
| **Pilot Safe** | Default-secure and fail-closed; safe for supervised pilot use with documented residual risks (A-006 security-classification axis) |
| **Stubbed** | Interface exists; concrete behavior is a generic placeholder |
| **Mocked** | Contains simulated/canned behavior in the production path |
| **Deferred** | Intentionally postponed within v1.0.x |
| **Future** | Genuinely not started; a later-milestone aspiration |

---

## Master status table

| Subsystem | Status | Evidence | Notes |
|---|---|---|---|
| **Approval System** | 🟢 Production Ready | `execution/service.py:43-45`, `approvals/service.py:85-181`; 12 governance tests | Un-bypassable DB-backed gate. **Now fail-closed** on empty `owner_ids` (A-001, `service.py:96-102`). |
| **Governance Layer (11-gate)** | 🟢 Production Ready | `execution/governance.py` | Best-tested code in repo; audits every decision. |
| **Memory System** | 🟢 Production Ready | `memory/manager.py:28-101`, `models.py:184-199` | Event-sourced immutable `audit_log` + checkpoint replay. |
| **Communication Outbox** | 🟢 Production Ready | `gateway/communication_outbox.py:79-243`; concurrency/lease tests | Lease-based, backoff+jitter, dead-letter, audited. |
| **Task Management** | 🟢 Production Ready | `task_service.py:25-38`; e2e `tests/e2e/test_mvp_workflow.py` | Guarded lifecycle, locking, Discord CRUD. |
| **Runtime Registry + adapter split** | 🟢 Operational | `runners/__init__.py`, `runners/base.py` | Excellent extensible abstraction; concrete runtimes vary (below). |
| **Execution timeouts** | 🟢 Operational | `runners/base.py:9-27` (`resolve_execution_timeout`, `hard_limit` clamp) | **Fixed** (A-002) to honor ADR-010 tiers. |
| **Scheduler Foundation** | 🟢 Operational | `scheduling/scheduler.py`, `jobs.py`; AP-103B reports | **New in v1.0.1.** 6 jobs, audited, single-node. Closes A-003. |
| **Metrics Persistence** | 🟢 Operational | `core/metrics.py`; `metrics_aggregation` job (5m) | Collection always worked; **aggregation+retention now actually scheduled** (was dormant in v1.0.0). |
| **Research Engine** | 🟡 Operational (latent) | research service; `research_collection` job (2h) | Engine production-grade; **now scheduled** but `research_feeds` empty by default → safely audited-skip until configured. RSS/Atom only. |
| **Daily Briefing Engine** | 🟡 Operational | briefing service; `daily_briefing` job (08:00 Asia/Kolkata) | **Now scheduled.** Note: default briefing path uses synchronous flush (per onboarding 07). |
| **Gemini Runtime** | 🟠 Stubbed | `runners/gemini.py` | Generic shell runner; no real `gemini` CLI binary invocation yet. |
| **Claude Runtime** | 🟠 Stubbed | `runners/claude.py` | Generic shell runner; no real `claude` CLI binary invocation yet. |
| **Nexus Runtime** | 🟠 Experimental (Track H / H-2) | `runners/nexus.py`, `runners/nexus_tools.py`, `runners/search_provider.py`; 21 nexus tests (16 honesty + 5) | **v1.1.0 H-2, effective on commit.** Was 🔴 Mocked (AsyncMock branch, canned search, decorative plan, always-`0` exit). Now **honest**: no prod mock, provider-backed search (`SearchProvider` DI), goal-derived planning, structured tool-calls, truthful exit status. Lifecycle safety (terminate/resume) still **absent** → Pilot bar (H-4). Basis: `ADR-hermes-experimental`, `nexus-experimental-closure-review.md`. |
| **Sandbox Isolation** | 🟢 Pilot Safe (Track S) | `manager.py:34-64,196-256`, `provider.py:65,146,151-170,296-300`, `confinement.py`, `nexus.py:75-117`, `api.py:106-113`; 35 sandbox tests (9+14+12) | **v1.1.0 Track S (S-2/S-3/S-4), effective on commit.** Was Experimental (default host exec). Now **default-secure fail-closed** resolution (R-01/R-02), **boot-validated** + Docker-availability probe (R-06/R-07), **honest policy enforcement** (R-03), **workspace-confined** agent file tools (R-05). Isolation still opt-in (`enabled=true,provider=docker`); host run only by deliberate, warned, audited choice. Residual: R-04 (governance blacklist), R-08 (shell surface), R-09 (default not `readonly`). Basis: `ADR-sandbox-pilot-safe`, `track-s-closure-review.md`. |
| **Health reporting** | 🟠 Experimental | `core/health.py:49-71`; `api.py` `/api/v1/status` returns `"stub"` | Boot-time boolean from `git --version`; not live-probed. Known gap. |
| **Alembic migrations** | 🟠 Experimental | `api.py` `create_all`; incomplete migrations | `create_all` is the real schema source; migrations incomplete/untested. Blocks PostgreSQL path. |
| **Distributed / multi-node scheduling** | ⚪ Future | `scheduler-future-scaling.md` | Lease model + PostgreSQL coordination designed, not built. |
| **PostgreSQL backend** | ⚪ Future | ADR-002 | SQLite/WAL today. |
| **Extra integrations (WhatsApp/Slack/GitHub)** | ⚪ Future | ROADMAP Phase 9 | Not started. |

---

## Status rollup

- **Production Ready (5):** Approval, Governance, Memory, Communication Outbox, Task Management.
- **Operational (5):** Runtime Registry, Execution timeouts, Scheduler, Metrics, (latent) Research / Briefing.
- **Pilot Safe (1):** Sandbox isolation (v1.1.0 Track S; effective on commit).
- **Stubbed (2):** Gemini, Claude runtimes.
- **Experimental (3):** Nexus runtime (v1.1.0 H-2, honest; effective on commit), Health reporting, Alembic migrations.
- **Future (3):** Distributed scheduling, PostgreSQL, extra integrations.

## One-line truth

> Nexus v1.0.1 is a **production-grade governed-execution kernel** (approval + governance + memory +
> outbox) with an **operational single-node autonomy layer** (scheduler now drives research,
> briefing, approval-expiry, metrics, and health jobs), whose **CLI runtimes (Gemini/Claude) are still
> stubbed** while **Nexus is now honest (Experimental, v1.1.0 H-2 — real decisions, provider-backed
> search, goal-derived plans, truthful outcomes; lifecycle safety still ahead at Pilot)** and whose
> **sandbox is now default-secure (Pilot Safe, v1.1.0 Track S — refuses to run on the host implicitly;
> isolation opt-in)** — honestly pilot-ready as an attended-to-lightly-autonomous single-operator
> control plane.

## Especially-watched subsystems (AP-104 mandate)

- **Nexus Runtime** — 🟠 **Experimental** (v1.1.0 H-2, effective on commit): honest decisions, provider-
  backed search, goal-derived plans, structured tool-calls, truthful exit status. **Not** lifecycle-safe
  yet (no terminate/resume) — do not represent as Pilot/resumable; that is the H-4 bar.
- **Research Engine** — 🟡 built + scheduled, **but empty feeds by default**; not autonomous until configured.
- **Scheduler** — 🟢 Operational, **single-node only** (no cross-process lease yet).
- **Sandbox Layer** — 🟢 **Pilot Safe** (v1.1.0 Track S, effective on commit): default-secure
  fail-closed, boot-validated, workspace-confined. Isolation still opt-in (`provider=docker`); host
  execution only by deliberate, audited choice. Residual R-04/R-08/R-09 disclosed.
- **Metrics Persistence** — 🟢 now aggregated on schedule (the v1.0.0 dormancy is resolved).
- **Outbox / Governance / Approval / Memory** — 🟢 the trustworthy core.
