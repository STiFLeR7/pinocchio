# 07 — Event Flow Map (Architecture Review: Event Model, EventGateway, the two Outboxes)

> Read-only audit of `nexus/core/events.py`, `nexus/gateway/*`. Nexus has **three** event channels:
> an in-process bus (`EventGateway`), a system-event outbox (`system_events` → Discord), and a
> communication outbox (`system_outbox` → Discord/Email). Evidence cited as `file:line`.

---

## A. The event envelope  (`core/events.py`)

`NexusEvent` is a **frozen** Pydantic model (`events.py:49`) — events are immutable. Fields:
`id`, `event_type: EventType`, `entity_type`, `entity_id`, `data`, `correlation_id`, `timestamp`,
`source` (`events.py:25-47`).

**Canonical event types** (`core/types.py:56-102`, 30 values): task (`task.created/updated/
completed/cancelled`), approval (`approval.requested/granted/rejected/expired`), execution
(`execution.started/completed/failed/timed_out`), research (`research.started/completed/failed`),
communication (`notification.sent/failed`), reporting (`report.generated`), system
(`system.started/stopped`), workflow (`workflow.checkpointed/resumed`), sandbox
(`sandbox.created/started/terminated/timeout/failure`).

⚠ **Doc divergence** — `blueprint/architecture/event-model.md:24-118` lists PascalCase events
(`TaskQueued`, `TaskStarted`, `ExecutionHeartbeat`, `CheckpointCreated`) that **do not exist** in
the enum, and omits all sandbox/notification/report/system events that **do** exist. The doc is
stale; `core/types.py` is authoritative.

---

## B. EventGateway — in-process bus  (`gateway/gateway.py`)

**Purpose** — Async in-process pub/sub. `subscribe(event_type, callback)` (`gateway.py:28-35`);
`publish(event)` fans out to subscribers (`:37-63`).

**Critical property** — This bus is **ephemeral and in-memory**. A failing subscriber is logged and
swallowed; other subscribers still run (`:53-63`). There is no retry/persistence/dead-letter at this
layer. Durability comes from the DB outboxes, not the bus.

**Subscribers in production** (`orchestrator.py:46-52`): `TASK_UPDATED`, `APPROVAL_GRANTED`,
`EXECUTION_COMPLETED`, `EXECUTION_FAILED`. ⚠ Notably, **`RESEARCH_COMPLETED` has no subscriber** —
the designed research→briefing chain (`research-workflow-design.md:58`) is not wired.

---

## C. System-events Outbox  (`gateway/outbox.py` → Discord)

**Backing table** — `system_events` (`models.py:411-423`), written transactionally with audit by
`MemoryService.enqueue_outbox_event` (`memory/service.py:51-69`).

**Dispatch** — `publish_outbox_loop` polls every 2s, selects oldest 20 `pending`, routes by event
type to Discord channels (TASK_* → `tasks`; APPROVAL_REQUESTED → approval card; APPROVAL_GRANTED/
REJECTED → `alerts`; EXECUTION_* → `execution_log`/`alerts`), marks `sent`, single batch flush
(`outbox.py:171-212,28-168`).

**⚠ This outbox is the weaker of the two — at-most-once and lossy:**
- **No leasing / no `worker_id`** — two app instances would double-send (`outbox.py:184`).
- **No `attempt_count`, no dead-letter** — a permanently-failing event stays `pending` forever
  (`outbox.py:161-168`).
- **Batch-flush window** — statuses mutated in memory, flushed once per batch; a crash mid-batch
  re-sends (`outbox.py:191-199`).
- **Silent message loss** — `DiscordService.post_message` swallows send errors and returns `None`
  (`service.py:80-82`); `dispatch_outbox_event` treats `None` as success and marks the row `sent`
  even when Discord delivery failed (`outbox.py:50-55,159,191-194`). So approval requests / alerts
  can be **permanently dropped** when Discord is down — directly contradicting the resilience claim
  in `discord-integration-design.md:12`.

---

## D. Communication Outbox  (`gateway/communication_outbox.py` → Discord/Email)

This is the **mature, lease-based outbox** (AP-501). Backing table `system_outbox` (`models.py:431-452`)
with `attempt_count`, `max_attempts`, `next_retry_at`, `worker_id`, `last_error`, `delivered_at`.

**Pipeline**:
- `lease_outbox_items` — atomically claims `pending`/`retrying` (and reclaims expired `processing`)
  items, stamps `worker_id`, sets a 5-min lease, commits (`communication_outbox.py:79-120`).
- `process_outbox_item` — re-loads guarded by `status=="processing" AND worker_id==self`
  (`:133-141`); delivers by channel (`discord` chunked to 1900 chars, `email` via
  `send_briefing_email`); on success → `sent` + `NOTIFICATION_SENT` audit; on failure →
  increment attempt, `retrying` with **exponential backoff + jitter** (`10*2^attempt + rand(0,5)`),
  or `dead_letter` + `NOTIFICATION_FAILED` after `max_attempts` (`:123-243`).
- `run_communication_outbox_loop` — unique `worker_id`, leases 10, processes each in its own
  transaction (`:316-341`).

**Guarantees** — At-least-once with lease reclamation; FIFO within a batch; concurrency-safe (tested
in `tests/unit/gateway/test_communication_outbox.py:235-274`).

**⚠ But the production default bypasses it.** `BriefingService.sync_outbox_flush` defaults `True`
(`briefing.py:201`), so briefings call `flush_outbox_synchronously` (`communication_outbox.py:246-312`)
which **dead-letters on first failure with no retry/backoff** — despite its "used for testing"
docstring (`:252`). The resilient loop exists but the default path skips it.

---

## E. End-to-end event flow (concrete)

```
Task queued
  └─ TaskService.change_status(QUEUED) ─ audit TASK_UPDATED ─ EventGateway.publish
       └─ orchestrator.on_task_updated ─ ApprovalService.create_approval_request
            ├─ approvals row + audit APPROVAL_REQUESTED  (DB)
            └─ MemoryService.enqueue_outbox_event ─ system_events row (pending)
                 └─ publish_outbox_loop (2s) ─ Discord approval card  [system-events outbox]
Owner approves (Discord button, owner-id gate)
  └─ ApprovalService.evaluate_approval ─ task ACTIVE ─ audit/publish APPROVAL_GRANTED
       └─ orchestrator.on_approval_granted ─ run_execution_flow (asyncio task)
            └─ ExecutionService.start_execution (approval gate) ─ governance ─ sandbox ─ subprocess
                 └─ finalize_execution ─ EXECUTION_COMPLETED/FAILED
                      └─ orchestrator.on_execution_finished ─ SummaryEngine ─ Discord #summaries
Briefing (when triggered — currently only by tests/resume)
  └─ generate_and_dispatch_briefing ─ briefings row + system_outbox rows (pending)
       └─ flush_outbox_synchronously (default) OR run_communication_outbox_loop ─ Discord/Email
```

---

## Event-flow gap analysis

**Excellent** — Frozen immutable event envelope; transactional outbox write semantics on both
producers; the comm outbox's lease/backoff/dead-letter machinery is genuinely production-grade and
tested.

**Missing** — `RESEARCH_COMPLETED` subscriber (no research→briefing chain); leasing + dead-letter on
the `system_events` outbox; Discord reconnect/disconnect handlers (none exist anywhere); event-model
doc reconciliation.

**Risky** — Silent message loss in the `system_events` outbox when Discord is down
(`service.py:80-82` ↔ `outbox.py:159`); no leasing → double-send if two instances run; sync-flush
default dead-letters briefings on first failure; channel fallback to "first text channel"
(`bot.py:213-215`) can route approvals to the wrong channel.

**Never change** — Same-transaction outbox writes (`memory/service.py:51-69`, `briefing.py:163-193`);
the `worker_id`+`status==processing` re-load guard (`communication_outbox.py:133-141`); frozen
`NexusEvent`; append-only `audit_log`.

**Monitor** — `system_outbox` dead-letter count + attempt distribution; `event_flush_duration_ms`;
stuck `pending` rows in `system_events`; `unknown_outbox_event_type` / `discord_post_message_failed`
warnings.

**Improve** — see `12`: make `post_message` failures observable; add leasing/dead-letter to
`system_events`; add Discord connection handlers; replace the channel fallback with an explicit
error.
