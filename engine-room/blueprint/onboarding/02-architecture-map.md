# 02 — Architecture Map

> Read-only audit of Nexus v1.0.0. Maps the documented 6-layer architecture to the actual Python
> packages, with citations. Source of architectural intent: `docs/01_ARCHITECTURE.md`,
> `blueprint/architecture/service-boundaries.md`.

---

## 1. The documented layering vs the implemented packages

`docs/01_ARCHITECTURE.md:160-184` defines six layers. The implemented package tree maps cleanly
onto them, with two important naming caveats noted below.

```
Documented layer            →  Implemented package(s)                         Evidence
─────────────────────────────────────────────────────────────────────────────────────
Communication Layer         →  nexus/communication/{discord,email}            discord/bot.py, email/service.py
Event Gateway               →  nexus/gateway/{gateway,outbox,                 gateway/gateway.py:28-63
                               communication_outbox} + nexus/core/events.py   core/events.py:18-49
Nexus Core (orchestration)  →  nexus/scheduling/orchestrator.py               orchestrator.py:29 (WorkflowOrchestrator)
                               nexus/core/{types,exceptions,health,metrics}    core/*
Memory Layer                →  nexus/memory/* + nexus/database.py             memory/manager.py, database.py
Scheduling Layer            →  nexus/scheduling/ (event-driven, NOT cron)     orchestrator.py (no APScheduler)
Intelligence Layer          →  nexus/intelligence/*                            intelligence/{research,briefing,summary,openrouter}.py
Execution Layer             →  nexus/execution/*                               execution/{service,governance,runners,sandbox}
Repository Layer            →  config/repositories.yaml + repository_registry  governance.py:149-175, models.py:493-513
```

### Naming caveats (important for orientation)

1. **`nexus/scheduling/` is not a scheduler.** It contains `WorkflowOrchestrator`, an
   *event-driven* dispatcher (`orchestrator.py:29-52`). There is **no APScheduler instance, job
   store, or cron trigger anywhere in `nexus/`** despite `apscheduler` being a declared dependency
   (`pyproject.toml:17`) and being documented as the scheduling backbone. The only background
   timers are three `asyncio` poll loops started in the FastAPI lifespan (`nexus/api.py:114-127`).

2. **The "Nexus Core / Workflow Orchestrator"** of the architecture doc is physically the
   `WorkflowOrchestrator` in the `scheduling` package, plus the shared primitives in `nexus/core/`
   (enums/types, exceptions, health, metrics, policy defaults). There is no single "core" package
   that owns orchestration; orchestration is the orchestrator + the per-event services it spins up.

## 2. The real runtime topology (what boots, in order)

From `nexus/api.py:65-138` (FastAPI `lifespan`):

```
python -m nexus  →  uvicorn  →  nexus.api:app  →  lifespan startup:
 1. get_settings()                                         config.py:195
 2. setup_logging()                                        logging_config.py:16
 3. create_engine() + async_session_factory()             database.py:119,145
 4. Base.metadata.create_all()   ← schema bootstrap        api.py:81-83  (NOT alembic)
 5. health.run_git_startup_validation()                    health.py:49
 6. PolicyService.seed_default_policies()                  policy_service.py:174
 7. EventGateway()                                         gateway.py
 8. OpenRouterClient(settings)                             openrouter.py:20
 9. NexusBot + DiscordService                              bot.py:131, service.py
10. EmailService                                           email/service.py:23
11. WorkflowOrchestrator(...).register_listeners()        orchestrator.py:46-52
12. asyncio loops:  publish_outbox_loop (2s)              api.py:115  → outbox.py:171
                    run_communication_outbox_loop (2s)    api.py:120  → communication_outbox.py:316
                    run_metrics_flush_loop (5s)           api.py:125  → metrics.py:123
13. Discord bot.start()  (only if real token configured)  api.py:131-135
```

Shutdown cancels the loops with a final metrics flush, closes the bot, disposes the engine
(`api.py:140-176`).

## 3. The end-to-end control flow (the spine)

This is the single most important diagram to hold in your head. It is **event-driven**, not
call-stack driven: components communicate through the in-process `EventGateway`
(`gateway.py:37-63`) and the database outboxes.

```
 Discord /task_create ─┐
 programmatic create  ─┴─► TaskService.create_task ──► tasks row + TASK_CREATED audit  (task_service.py:55-100)
                                     │
                          change_status(QUEUED)
                                     │ emits TASK_UPDATED (event bus)
                                     ▼
            WorkflowOrchestrator.on_task_updated  (orchestrator.py:54-77)
                                     │ creates approval, task → BLOCKED
                                     ▼
            ApprovalService.create_approval_request ──► approvals row + APPROVAL_REQUESTED (approvals/service.py:38-81)
                                     │
                          (system_events outbox)  ──► publish_outbox_loop ──► Discord approval card
                                     ▼                                          (outbox.py:81-109, service.py:84-113)
                       Owner clicks Approve  (owner-id gate, bot.py:52-58)
                                     │
            ApprovalService.evaluate_approval ──► task → ACTIVE + APPROVAL_GRANTED (approvals/service.py:85-181)
                                     ▼
            WorkflowOrchestrator.on_approval_granted ──► run_execution_flow (asyncio task) (orchestrator.py:79-101)
                                     │ health gate (orchestrator.py:104-116)
                                     ▼
            ExecutionService.start_execution ──► check_approval_gate (HARD GATE) (execution/service.py:43-45)
                                     ▼
            Runtime adapter validate() ──► GovernanceManager.validate_execution (11 checks) (governance.py:60-653)
                                     ▼
            adapter execute() ──► SandboxManager.execute ──► subprocess (sandbox/manager.py:55, provider.py:88)
                                     ▼
            finalize_execution ──► task → COMPLETED/FAILED + EXECUTION_COMPLETED/FAILED (execution/service.py:156-235)
                                     ▼
            WorkflowOrchestrator.on_execution_finished ──► SummaryEngine ──► Discord #summaries (orchestrator.py:274-311)
```

Two durability mechanisms wrap this spine:

- **Transactional outbox** — events and outbound messages are written to DB tables in the *same
  transaction* as the business state, then dispatched by background loops
  (`memory/service.py:51-69`, `gateway/communication_outbox.py:79-243`). This is why a Discord
  outage cannot lose an approval request.
- **Event sourcing** — every state transition writes an immutable `audit_log` row
  (`memory/models.py:184-199`); workflow context is recompiled from checkpoint + replay
  (`memory/manager.py:28-101`).

## 4. Architectural principles actually enforced in code

These are not just doc aspirations — they are mechanically enforced:

- **Human-approval-before-execution is un-bypassable.** `start_execution` raises if no `APPROVED`
  record exists (`execution/service.py:43-45`); subprocess spawning is confined to
  `nexus/execution/` (`service-boundaries.md:103`). No alternate path spawns execution. *(Verified:
  no other subprocess-spawn site outside execution/.)*
- **Database is the source of truth, not Discord.** Approval gate reads the `approvals` table, not
  Discord state (`approvals/service.py:241-248`), so an offline bot cannot cause a bypass.
- **Intelligence layer never mutates orchestration state or triggers execution.** Research/Briefing
  write only their own findings/briefings/outbox rows; Summary is read-only (audited in
  `05`/`08`). Compliant with `docs/01_ARCHITECTURE.md:398-405`.
- **Layered imports.** ADR-014 mandates lower layers must not import higher
  (`ADR-phase1-foundation.md:50-62`); enforced by review/CI rather than an import linter.

## 5. Where the implemented architecture diverges from the documented one

| Doc claim | Reality | Evidence |
|---|---|---|
| APScheduler scheduling layer with persistent job store | asyncio poll loops; no scheduler, no job store | `nexus/api.py:114-127`; `ADR-001:100` |
| Per-entity event tables (`task_events`, `approval_events`, `scheduled_jobs`, `notifications`) | Unified single `audit_log` + two outbox tables | `ADR-002:84-93` vs `models.py:184-199` |
| Alembic migrations define production schema | Production schema bootstrapped by `Base.metadata.create_all` at boot; 6 ORM tables have no migration | `api.py:81-83`; see `06-database-map.md` |
| Model fallback chain Nemotron→OwlAlpha→DeepSeek | Code defaults to Gemini→Claude→Gemini-flash (Python) / free models (YAML) — two divergent config sources | `docs/01_ARCHITECTURE.md:440-466` vs `config.py:63-69`, `settings.example.yaml:58-62` |

See `10-technical-debt-review.md` for the consolidated divergence list.

## 6. Architectural maturity assessment (evidence-based)

- **Spine maturity: high.** The task→approval→execution→audit→summary path is real, layered,
  transactional, and tested at unit/integration/e2e levels.
- **Autonomy maturity: low.** Scheduling is absent; research/briefing/expiration/aggregation are
  built but un-triggered.
- **Runtime maturity: medium.** The registry/adapter/governance abstraction is excellent; the
  actual CLI integrations are generic shell runners and Nexus is partly simulated.

Nexus is best described architecturally as a **well-engineered governed-execution kernel with an
event-sourced memory backbone**, around which the autonomous-operations layer is designed and
partially built but not yet activated.
