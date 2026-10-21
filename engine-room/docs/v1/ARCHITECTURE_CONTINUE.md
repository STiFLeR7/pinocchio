# ARCHITECTURE_CONTINUE.md

# Nexus Architecture — As-Built Continuation

Version: 1.2.0 · Status: As-built reference · Continues: `01_ARCHITECTURE.md`

`01_ARCHITECTURE.md` is the design source-of-truth (the intended shape). This
document is the **as-built** continuation: it records how the implementation
actually wires together at the code level, with ASCII diagrams and concrete
module references. Companion docs: `HARNESS.md`, `ORCHESTRATION.md`,
`COMMUNICATION.md`.

> Nexus is an AI Orchestration Control Plane — a deterministic, auditable,
> recoverable layer that coordinates humans, tasks, approvals, channels, AI
> runtimes, memory and schedulers. Not a chatbot, not a single-agent framework.

---

## 1. System at a glance (ASCII)

```
                                   OPERATOR
                                      │
                      Discord (chat · slash · approvals)        HTTP (/health, /api/v1)
                                      │                                  │
 ┌────────────────────────────────────┼──────────────────────────────────┼─────────────┐
 │  COMMUNICATION LAYER                │                       API (FastAPI / ASGI)      │
 │  ┌──────────────────────────────────▼───────────────┐   ┌──────────────▼──────────┐  │
 │  │ Channel Harness  (transport-independent)          │   │ lifespan: build + own   │  │
 │  │   ChannelRole · ChannelMessage · ChannelRouter    │   │ engine, services, loops │  │
 │  └───────────────┬───────────────────────────────────┘   └──────────────┬──────────┘  │
 │   Discord adapter│ (NexusBot · DiscordService)                          │             │
 └──────────────────┼───────────────────────────────────────────────────────┼───────────┘
                    │                                                         │
            ┌───────▼─────────┐         publish/subscribe          ┌──────────▼─────────┐
            │  Dex v2 Chat    │  ───────────────────────────────▶  │   EVENT GATEWAY    │
            │  Planner→Valid- │      NexusEvent (in-memory bus)    │  (pub/sub, async)  │
            │  ator→Executor  │  ◀───────────────────────────────  └──────────┬─────────┘
            └───────┬─────────┘                                                │
                    │ domain calls                                            │ subscribers
   ┌────────────────▼─────────────────┐   ┌───────────────────────────────────▼──────────────┐
   │ CORE DOMAIN SERVICES              │   │ WORKFLOW ORCHESTRATOR                              │
   │  TaskService · ApprovalService    │   │  TASK_UPDATED→approval · APPROVAL_GRANTED→execute │
   │  ExecutionService · PolicyService │   │  EXECUTION_* → summarise & post                   │
   └────────────────┬─────────────────┘   └───────────────────┬───────────────────────────────┘
                    │                                          │ resolves
                    │                          ┌───────────────▼───────────────┐
                    │                          │ EXECUTION / RUNTIME HARNESS    │
                    │                          │  runtime_registry → adapter    │
                    │                          │  claude · gemini · nexus       │
                    │                          │  (Sandbox + Governance)        │
                    │                          └───────────────┬───────────────┘
   ┌────────────────▼──────────────────────────────────────────▼───────────────┐
   │ MEMORY / DATA LAYER   SQLAlchemy 2.x async · aiosqlite (WAL)                │
   │  tasks · approvals · executions · execution_steps · agent_steps            │
   │  audit_log(immutable) · research_findings · briefings · system_outbox      │
   │  workflow_checkpoints · knowledge_items                                    │
   └────────────────▲──────────────────────────────────────────▲───────────────┘
                    │                                          │
   ┌────────────────┴───────────┐          ┌───────────────────┴───────────────┐
   │ SCHEDULING LAYER           │          │ INTELLIGENCE LAYER                 │
   │  APScheduler (J1–J6)       │ ───────▶ │  ResearchService · BriefingService │
   │  research/briefing/sweeps  │          │  PriorityFeedService · OpenRouter  │
   └────────────────────────────┘          └───────────────────┬────────────────┘
                                                                │ enqueue
                          ┌─────────────────────────────────────▼────────────────┐
                          │ TRANSACTIONAL OUTBOX  (system_outbox)                 │
                          │  enqueue → lease → deliver → retry/dead-letter        │
                          │  → Discord chunks · → Email (SMTP)                    │
                          └───────────────────────────────────────────────────────┘
```

Two delivery paths leave the core: **synchronous** chat replies (Discord, via the
chat pipeline) and **asynchronous** notifications/briefings (via the transactional
outbox, drained by a background loop). Everything mutating goes through domain
services, emits a `NexusEvent`, and is recorded in the immutable `audit_log`.

---

## 2. Architectural layers (as-built)

| Layer | Package | Key symbols |
|---|---|---|
| API / lifespan | `nexus/api.py` | `create_app`, `lifespan`, `_AppState`, `/health`, `/api/v1/status` |
| Communication | `nexus/communication/` | `ChannelRouter`, `NexusBot`, `DiscordService`, `ChatService`, `EmailService` |
| Event gateway | `nexus/gateway/gateway.py` | `EventGateway` (in-memory pub/sub) |
| Outbox | `nexus/gateway/{outbox,communication_outbox}.py` | `publish_outbox_loop`, `run_communication_outbox_loop` |
| Core domain | `nexus/memory/`, `nexus/approvals/`, `nexus/execution/` | `TaskService`, `ApprovalService`, `ExecutionService`, `PolicyService` |
| Runtime harness | `nexus/execution/runners/` | `runtime_registry`, `BaseRuntimeAdapter`, `CLIRuntimeAdapter`, `AgentRuntimeAdapter` |
| Scheduling | `nexus/scheduling/` | `build_scheduler`, `APSchedulerAdapter`, `WorkflowOrchestrator`, jobs J1–J6 |
| Intelligence | `nexus/intelligence/` | `ResearchService`, `BriefingService`, `PriorityFeedService`, `OpenRouterClient` |
| Data | `nexus/database.py`, `nexus/memory/models.py` | `Base`, `create_engine`, `async_session_factory`, ORM records |
| Core types | `nexus/core/` | `EventType`, `TaskStatus`, `ApprovalStatus`, `ExecutionStatus`, metrics |

---

## 3. Startup sequence (`lifespan`, `nexus/api.py`)

The ASGI lifespan **owns** every long-lived object; nothing is a hidden global
except `_state` and the settings singleton.

```
 1. setup_logging(level, format)                        structlog (json|text)
 2. GATES  ── A-001  fail-closed if discord.owner_ids empty   (ConfigurationError)
           └─ S-3   await validate_sandbox_startup(settings)
 3. engine = create_engine(db.url, echo)                aiosqlite + WAL pragmas
    session_factory = async_session_factory(engine)
    Base.metadata.create_all                            (dev convenience)
 4. run_git_startup_validation(session_factory)
 5. policy_service.seed_default_policies()              AP-317 baseline policy
 6. event_gateway = EventGateway()
    openrouter_client = OpenRouterClient(settings)
 7. email_service = EmailService(settings)
    chat_service  = ChatService.build(llm, email, owner_email, session_factory, event_gateway)
 8. discord_bot  = NexusBot(settings, session_factory, event_gateway, llm, chat_service)
    discord_service = DiscordService(discord_bot)
 9. orchestrator = WorkflowOrchestrator(session_factory, event_gateway, discord_service, llm)
    orchestrator.register_listeners()
10. create_task( publish_outbox_loop(...,            poll_interval=2.0) )   # event→discord
11. create_task( run_communication_outbox_loop(...,  poll_interval=2.0) )   # outbox→discord/email
12. create_task( run_metrics_flush_loop(...,         interval=5.0) )
13. scheduler = build_scheduler(...);  scheduler.start()                    # J1–J6
14. if discord.token present: create_task( discord_bot.start(token) )

 shutdown: scheduler.stop → cancel outbox/comm/metrics tasks → close bot → engine.dispose
```

---

## 4. Data layer

- **Engine** (`nexus/database.py:create_engine`): async SQLAlchemy 2.x over
  `aiosqlite`. Per-connection pragmas: `journal_mode=WAL`, `foreign_keys=ON`,
  `busy_timeout=5000`.
- **Session factory**: `async_session_factory(engine)`, `expire_on_commit=False`.
  `get_session()` async context manager commits on success, rolls back on error,
  and records `db_write_duration_ms` / `transaction_duration_ms`.
- **Base & mixins**: `Base(AsyncAttrs, DeclarativeBase)`; `TimestampMixin`
  (`id`, `created_at`, `updated_at`, `is_archived`) for mutable tables;
  `AuditMixin` (`id`, `created_at`) for append-only tables.
- **Tables** (`nexus/memory/models.py`): `tasks`, `approvals`, `executions`,
  `execution_steps`, `agent_steps`, `audit_log` (immutable), `research_items`,
  `research_findings`, `briefings`, `knowledge_items`, `workflow_checkpoints`,
  `system_outbox`.
- **Migrations**: Alembic (`alembic/env.py`), async-aware, `target_metadata =
  Base.metadata`, autogenerate from `nexus.memory.models`.

```
 tasks 1───* approvals 1───* executions 1───* execution_steps
   │                              │
   │                              └────────* agent_steps   (reasoning trajectory)
   └─ runtime_id/runtime_type/runtime_policy
 audit_log  (append-only, every state change)      system_outbox (delivery queue)
```

---

## 5. Technology stack (`pyproject.toml`)

| Concern | Library | Notes |
|---|---|---|
| Web / ASGI | `fastapi` ≥0.115, `uvicorn[standard]` ≥0.34 | app + server; `python -m nexus` runs uvicorn on `0.0.0.0:8000` |
| ORM / DB | `sqlalchemy[asyncio]` ≥2.0, `aiosqlite` ≥0.21 | async SQLite, WAL |
| Validation / config | `pydantic` ≥2.0, `pydantic-settings` ≥2.0, `pyyaml`, `python-dotenv` | YAML + `.env`, `NEXUS_` env prefix, `__` nesting |
| Scheduling | `apscheduler` ≥3.10 | `AsyncIOScheduler` |
| Discord | `discord.py` ≥2.4 | bot, slash commands, interactive approval views |
| LLM / HTTP | `httpx` ≥0.28 | OpenRouter client (primary + fallback models) |
| Email | `aiosmtplib` ≥3.0, `jinja2` ≥3.1 | SMTP delivery; Jinja2 email design system |
| Logging | `structlog` ≥24 | JSON/text structured logs |
| Dev | `pytest(-asyncio,-cov,-mock)`, `respx`, `mypy`, `ruff`, `factory-boy` | CI: `ruff check`, `mypy nexus/ --ignore-missing-imports`, `pytest` |

---

## 6. Cross-cutting principles (enforced in code)

1. **Deterministic & auditable** — every mutation emits a `NexusEvent`, persisted
   to the immutable `audit_log`; row locks (`with_for_update()`) guard transitions.
2. **Human governance, fail-closed** — A-001 refuses to boot without owners;
   approval gates force tasks to `BLOCKED` until an owner decides; the LLM never
   stamps governance flags (see `ORCHESTRATION.md` §2).
3. **Recoverable** — agent runtimes checkpoint each step (`agent_steps` +
   `workflow_checkpoints`) and can `resume_goal`; the outbox retries with backoff
   and dead-letters.
4. **Transport-independent** — the channel harness (`HARNESS.md`) means Discord is
   one adapter; email/Slack/web can bind the same roles.
5. **Failure isolation** — scheduled jobs never propagate exceptions to the
   scheduler; background loops catch-and-continue.
6. **Observable** — latency metrics (`approval_latency_ms`,
   `execution_start_latency_ms`, `*_duration_ms`) recorded and flushed every 5s.

See `ORCHESTRATION.md` for the execution pipeline and performance envelope,
`COMMUNICATION.md` for the channel/outbox data flow, and `HARNESS.md` for the
extensible channel and runtime contracts.
