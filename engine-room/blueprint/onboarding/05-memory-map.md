# 05 — Memory Map (Architecture Review: Memory Layer, Recovery Framework)

> Read-only audit of `nexus/memory/` + `nexus/database.py`. Nexus memory is an **event-sourcing**
> stack: an immutable append-only `audit_log` plus periodic checkpoints, with derived state
> recompiled by replay. Evidence cited as `file:line`.

---

## A. Memory Manager / Context Compiler  (`memory/manager.py`)

**Purpose** — Reconstruct the ephemeral, derived `ContextFrame` for a workflow from the latest
checkpoint plus replay of audit events after it (`manager.py:1-5,21-22`). This is the realization of
ADR-004's "ContextFrame is derived, never stored" principle (`ADR-runtime-foundations.md:24`,
`final-architecture-review.md:74-81`).

**Dependencies** — `WorkflowCheckpointRecord`, `AuditLogRecord` (`memory/models.py`).
**Inputs** — `workflow_id` (+ default model). **Outputs** — a `ContextFrame`
(messages/model/thinking_level/active_tools/metadata).

**Mechanism** (`manager.py:28-101`):
1. Load latest checkpoint for `workflow_id` (`created_at DESC LIMIT 1`).
2. Seed state from `checkpoint.state` JSON.
3. Load audit events where `entity_id == workflow_id` AND `created_at > checkpoint_time`, ascending.
4. **Reduce** events (PAT-001 reduction): model/thinking/tool changes and message-appending events
   (`message`, `task.created`, `task.updated`, `execution.step.*`) (`manager.py:71-92`).
5. Return the recompiled frame.

**Critical invariants** — A checkpoint's `state` JSON is the full snapshot; the audit log carries
deltas since the snapshot; reconstruction is deterministic (snapshot + tail). Nothing depends on
process memory, so restart-safety is structural.

**Failure modes** — `metadata` is only seeded from the checkpoint, never updated by replay
(`manager.py:51,94-101`); reduction is *time-ordered* (`created_at`), so same-timestamp events have
undefined order; the boundary is strictly `>` checkpoint time, so an event at the exact checkpoint
instant is dropped (`manager.py:64`); `compile_context` filters by `entity_id == workflow_id` while
checkpoints key on `workflow_id` — these must be the same UUID (an unenforced coupling invariant).

**Recovery** — Deterministic recompile after restart; durable in SQLite WAL.

---

## B. Memory / Task / Policy services

**MemoryService** (`memory/service.py`) — the audit ledger + outbox + checkpoint API:
- `log_event(event, enqueue_outbox=True)` inserts an `AuditLogRecord` and (optionally) a
  `SystemEventRecord` outbox row **in the same session**, then flushes (`service.py:33-54`). This
  transactional coupling is the basis of the outbox pattern's correctness.
- `create_checkpoint` / `restore_checkpoint` (`service.py:71-94`).

**TaskService** (`memory/task_service.py`) — the task state machine:
- `change_status` is guarded by `VALID_TRANSITIONS` (`task_service.py:25-38`) under a
  `with_for_update` lock (`:113`); invalid transitions raise `TaskEngineError`.
- Terminal states `COMPLETED/FAILED/CANCELLED` have **empty** transition sets (`:35-37`) — they are
  irreversible sinks. ⚠ Note the `with_for_update` comment (`:112`) overstates SQLite guarantees:
  SQLite uses whole-DB write locking under WAL, not true row locks; correctness rests on the
  single-writer model + `busy_timeout`.

**PolicyService** — covered in `04-governance-map.md` (fail-closed reads, optimistic locking,
history, seeding).

---

## C. Recovery Framework

**What is durable** — Every business mutation commits through `get_session`
(commit/rollback/close + metrics, `database.py:152-192`) into SQLite WAL. The durable tables are
`audit_log`, `workflow_checkpoints`, `system_events` (event outbox), and `system_outbox`
(comm outbox).

**What replays on restart**:
1. **Schema bootstrap** — `Base.metadata.create_all` creates any missing tables (idempotent),
   then git validation + policy seeding (`api.py:80-94`).
2. **Context replay** — `ContextCompiler.compile_context` rebuilds derived context
   (`manager.py:28-101`).
3. **Workflow resume** — explicit per-workflow resume: `research.resume_research_run`
   (`intelligence/research.py:361-475`) and `briefing.resume_briefing_run`
   (`intelligence/briefing.py:250-370`) restore a checkpoint, emit `WORKFLOW_RESUMED`, and branch
   on the saved `step`.
4. **Outbox drain** — both outbox loops resume sweeping pending rows after restart
   (`outbox.py:171`, `communication_outbox.py:316`).

**⚠ What is NOT implemented** — There is **no generic startup recovery supervisor** that scans for
incomplete workflows/executions and auto-resumes them. The documented restart flow ("Load Workflow
State → Restore Queues → Restore Scheduled Jobs → Resume Operations", `docs/08:549-563`) is only
*partially* realized: checkpoint restore and outbox drain exist, but resume is invoked manually
per-workflow, scheduled jobs are not restored (there is no scheduler), and orphaned executions
(detectable via `last_heartbeat` columns on `executions`/`execution_steps`/`agent_steps`) have **no
monitor** consuming them.

---

## D. What memory is NOT (deferred capability)

- **Vector / semantic / knowledge-graph memory: entirely deferred — no code.** `knowledge_items` is
  a plain text table with no embeddings (`models.py:273-281`). ADR-004 explicitly chose
  deterministic/rule-based retrieval and "avoid semantic search initially"
  (`docs/08:424-446,450-464`). The `.env` even carries `DISABLE_SEMANTIC_MEMORY`
  (`.env`) — a flag for a feature that does not exist in code.
- **Cross-session "Chief of Staff" long-term memory** beyond the audit log is aspirational; what
  exists is the event ledger + checkpoints + research/briefing tables.

---

## Memory subsystem gap analysis

**Excellent** — Correct immutable audit ledger (`AuditMixin` omits `updated_at`/`is_archived`,
`database.py:80-92`, `models.py:184-199`); genuine event-sourcing snapshot+replay that is actually
used (`manager.py`, `research.py:361`); transactional outbox keeps audit+dispatch atomic
(`service.py:33-69`); optimistic-locked policy store with history; clean session lifecycle with
metrics.

**Missing** — Generic startup recovery supervisor / orphan-execution monitor; vector/KG memory
(deferred by design); audit-log compaction/vacuum (unbounded growth acknowledged in
`ADR-004:108-109`).

**Risky** — `with_for_update` overstated for SQLite (`task_service.py:112`); naive
`datetime.utcnow` defaults on `research_findings.discovered_at`/`briefings.generated_at`
(`models.py:237,259`) mix with tz-aware datetimes elsewhere; replay relies on `created_at`
time-ordering, not a monotonic sequence.

**Never change** — `audit_log` immutability (any UPDATE/DELETE breaks accountability); terminal
task states as sinks (`task_service.py:35-37`); transactional-outbox atomicity (`service.py:33-69`);
fail-closed policy reads.

**Monitor** — `audit_log` + checkpoint table growth; stale `last_heartbeat` rows; `db_write_duration_ms`
/ `transaction_duration_ms` (already emitted, `database.py:173-174`).

**Improve** — see `12-improvement-opportunities.md` (recovery supervisor; orphan monitor; datetime
normalization; audit compaction strategy).
