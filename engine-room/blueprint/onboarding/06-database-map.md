# 06 — Database Map (Architecture Review: Database Layer, Schema, Migrations)

> Read-only audit of `nexus/database.py`, `nexus/memory/models.py`, `nexus/core/types.py`,
> `alembic/`. Stack: **SQLite (WAL) + SQLAlchemy 2.x async (aiosqlite)**. Evidence cited as
> `file:line`.

---

## A. Database Layer  (`nexus/database.py`)

**Engine** — `create_async_engine(..., pool_pre_ping=True)` (`database.py:119-123`); URL
`sqlite+aiosqlite:///./data/nexus.db` (`config.py:76`).

**Pragmas** (per-connection listener, `database.py:100-106`): `journal_mode=WAL`,
`foreign_keys=ON`, `busy_timeout=5000`. ⚠ ADR-002 also specifies `synchronous=NORMAL`
(`ADR-002:50`) — **not set in code**.

**Sessions** — `async_sessionmaker(expire_on_commit=False)` (`:145-149`); `get_session()` is an
async context manager that commits on success, rolls back on exception, always closes, and records
`db_write_duration_ms`/`transaction_duration_ms` (`:152-192`).

**Base & mixins** — `Base(AsyncAttrs, DeclarativeBase)`; `TimestampMixin` (UUID pk, created/updated,
`is_archived`); `AuditMixin` (id + created_at only — for immutable tables) (`:43-92`).

**Concurrency model (important)** — SQLite is single-writer; `busy_timeout=5000` then `SQLITE_BUSY`.
Three background loops + Discord + HTTP all writing to one SQLite file is the exact contention risk
flagged in `GAPS_AND_RISKS.md:277-281`. The governance semaphore acquisition has explicit
backoff-on-locked handling (`governance.py:299-326`) precisely because of this.

---

## B. Full table catalog (21 ORM models)

`[NO MIGRATION]` = present in ORM/`create_all` but **absent from `alembic/versions/`**.

| # | Class | Table | Notes |
|---|---|---|---|
| 1 | `TaskRecord` | `tasks` | status/priority + runtime metadata (`runtime_type/id`, `execution_profile`, `runtime_policy`); cascades to approvals/executions/research |
| 2 | `ApprovalRecord` | `approvals` | task FK CASCADE; status, `expires_at`, `decided_by` |
| 3 | `ExecutionRecord` | `executions` | task FK; `runner`, `repository`, `last_heartbeat`, `timeout_threshold`, `exit_status`, `result` |
| 4 | `AuditLogRecord` | `audit_log` | **immutable** (AuditMixin); event_type/entity/data(JSON)/correlation_id |
| 5 | `ResearchItemRecord` | `research_items` | title/source/summary/tags |
| 6 | `ResearchFindingRecord` | `research_findings` | AP-306; importance_score, `discovered_at` (naive utcnow) |
| 7 | `BriefingRecord` | `briefings` | AP-307; type, channels, `content_hash`, status |
| 8 | `KnowledgeItemRecord` | `knowledge_items` | plain text (no embeddings) |
| 9 | `WorkflowCheckpointRecord` | `workflow_checkpoints` | `workflow_id`, `step_name`, `state`(JSON) |
| 10 | `ExecutionStepRecord` | `execution_steps` | command/pid/exit_code/stdout/stderr/heartbeat |
| 11 | `AgentStepRecord` | `agent_steps` | **[NO MIGRATION]** thought/tool/result trajectory |
| 12 | `ResearchJobRecord` | `research_jobs` | query, `schedule_cron`, status |
| 13 | `SystemEventRecord` | `system_events` | event outbox cache (immutable) |
| 14 | `SystemOutboxRecord` | `system_outbox` | **[NO MIGRATION]** comm outbox: attempt_count, next_retry_at, worker_id |
| 15 | `SystemMetricRawRecord` | `system_metrics_raw` | **[NO MIGRATION]** AP-502 raw metric rows |
| 16 | `SystemMetricAggregateRecord` | `system_metrics_aggregates` | **[NO MIGRATION]** hourly aggregates |
| 17 | `RepositoryRegistryRecord` | `repository_registry` | **[base table NO MIGRATION]** allowlist + AP-304 governance columns |
| 18 | `ExecutionArtifactRecord` | `execution_artifacts` | **[NO MIGRATION]** persisted artifacts |
| 19 | `GovernanceSemaphoreRecord` | `governance_semaphores` | per-repo concurrency lock |
| 20 | `SystemPolicyRecord` | `system_policies` | versioned policy store |
| 21 | `SystemPolicyHistoryRecord` | `system_policy_history` | immutable policy revisions |

JSON columns use the **SQLite dialect** `JSON` type (`models.py:21`) — a hard coupling that
complicates the documented PostgreSQL migration.

**Enums** (`core/types.py`, all `StrEnum` except `Priority`): `TaskStatus` (7),
`ApprovalStatus` (5), `ExecutionStatus` (6), `OutboxStatus` (5), `EventType` (30),
`RunnerType` (gemini_cli/claude_code/nexus_agent/research), `Priority` (1-4). Status columns are
stored as plain `String(50)`, not DB enum types — validity is enforced only in application code.

---

## C. Migrations  (`alembic/`)

Five ordered migrations: `bb6af9e30a24` (initial) → `c1a2b3c4d5e6` (governance semaphores) →
`d2a3b4c5e6f7` (policy externalization) → `e3b4c5d6e7f8` (research_findings) → `f4c5d6e7f8a9`
(briefings). Async env via aiosqlite (`alembic/env.py:57-77`).

**⚠ The critical structural finding: `create_all` vs Alembic divergence.**
- Production schema is created at boot by `Base.metadata.create_all` (`api.py:81-83`), **not** by
  Alembic.
- 6 ORM models have **no migration** (table above), including the **base** `repository_registry`
  table — yet migration `d2a3b4c5e6f7` does `op.add_column('repository_registry', ...)` (`:53-54`),
  which **assumes the table already exists**. So `alembic upgrade head` on a clean DB would fail
  unless `create_all` ran first.
- Tests build schema via `create_all` too (`tests/conftest.py:59`), so **no test ever exercises
  `alembic upgrade head`** — migration drift is invisible to CI.

Consequence: migrations are effectively decorative for the SQLite MVP, and the documented
PostgreSQL cutover (`ADR-002` Phase 2) is currently unsafe because the migration set is incomplete
and never validated.

---

## Database subsystem gap analysis

**Excellent** — WAL + FK + busy_timeout configured per-connection; correct immutable-table modeling;
clean async session lifecycle with metrics; descriptive ordered migrations exist; well-normalized
schema with sensible indexes and cascades.

**Missing** — Migrations for 6 tables incl. base `repository_registry`; `synchronous=NORMAL` pragma;
a migration round-trip test; dialect-neutral JSON for the PostgreSQL path; per-entity event tables
that ADR-002 described (superseded by unified `audit_log`).

**Risky** — `create_all` defines real schema → migrations can silently drift; SQLite-dialect JSON
blocks the "no app changes" PostgreSQL claim (`ADR-002:101`); naive vs aware datetime mixing
(`models.py:237,259`); single-writer SQLite under multi-loop concurrency.

**Never change** — `audit_log` immutability; FK pragma enforcement; the transactional-write
discipline through `get_session`.

**Monitor** — DB lock contention / `SQLITE_BUSY`; WAL file growth (`nexus.db-wal`/`-shm`);
`audit_log` row growth; `system_outbox` dead-letter/backlog depth.

**Improve** — see `12`: generate the missing migrations and stop relying on `create_all` in prod;
add `synchronous=NORMAL`; add a migration round-trip test; normalize datetimes; reconcile
`database-design.md` (lists ~8 of 21 live tables) and `ADR-002` with the actual schema.
