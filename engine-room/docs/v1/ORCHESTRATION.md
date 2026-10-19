# ORCHESTRATION.md

# Nexus Orchestration & Performance

Version: 1.2.0 · Companion to `ARCHITECTURE_CONTINUE.md`, `HARNESS.md`

How an operator intent becomes an audited, governed, executed outcome — and the
performance envelope that governs it. Everything here is event-driven, async, and
fail-closed.

---

## 1. The Dex v2 chat pipeline (`nexus/communication/chat/`)

```
 ChannelMessage
      │
      ▼
 ┌──────────┐   LLM (OpenRouter)        ┌────────────┐  server-side policy   ┌───────────┐
 │ Planner  │ ───────────────────────▶  │ ChatAction │ ───────────────────▶  │ Validator │
 │ classify │   parse JSON → type+      │  type      │  _ACTION_POLICY stamps │ govern +  │
 │ intent   │   payload (NO governance) │  payload   │  requires_owner/appr.  │ schema    │
 └──────────┘                           └────────────┘                        └─────┬─────┘
                                                                                     │ ok?
                  ┌──────────────────────────────────────────────────────────┬──────┘
                  │ rejected → ChatResponse(reply, executed=False)            │
                  │ needs approval → ChatResponse("needs approval", exec=F)   │ approved
                  ▼                                                            ▼
         (operator sees reason)                                        ┌────────────┐
                                                                       │  Executor  │
                                                                       │  dispatch  │
                                                                       └─────┬──────┘
       REPLY · SEND_EMAIL · CREATE_TASK · RUN_RESEARCH · SHOW_STATUS · APPROVAL_REQUEST
                                                                             │
                                                            ChatResponse(reply, posts[], executed)
```

| Stage | Class (file) | Responsibility | Side effects? |
|---|---|---|---|
| Plan | `Planner` (`planner.py`) | LLM classifies intent → `ChatAction(type, payload)`. **Never sets governance flags.** | LLM call only |
| Policy | `_ACTION_POLICY` (`planner.py`) | Trusted table stamps `requires_owner` / `requires_approval` per action type | none |
| Validate | `Validator` (`validator.py`) | Owner gate, approval gate, per-type required-field schema (`_REQUIRED_FIELDS`) | none |
| Execute | `Executor` (`executor.py`) | Dispatch to domain services; emit SYSTEM cards | yes (DB, email, events) |
| Orchestrate | `ChatService` (`service.py`) | Holds per-conversation history (rolling, max 12 turns); runs the pipeline | — |

### Governance is stamped server-side, never by the LLM

```
 _ACTION_POLICY  (planner.py)            (requires_owner, requires_approval)
   REPLY            (False, False)        public
   SHOW_STATUS      (False, False)        public
   SEND_EMAIL       (True,  False)        owner-only
   CREATE_TASK      (True,  False)        owner-only
   RUN_RESEARCH     (True,  False)        owner-only
   APPROVAL_REQUEST (True,  True)         owner + manual approval
```

The Planner's only job is classification. Even if the LLM is manipulated into
claiming an action is "safe", the flags come from this table — a prompt-injection
cannot escalate privilege. The Executor injects `session_factory` + `event_gateway`
and mirrors the slash-command path (`TaskService.create_task` →
`change_status(QUEUED)`); `RUN_RESEARCH` persists a task with `runtime_id="nexus"`.

---

## 2. Task lifecycle (`nexus/memory/task_service.py`)

```
 CREATED ──▶ QUEUED ──▶ ACTIVE ──▶ COMPLETED        VALID_TRANSITIONS enforces every edge;
               │           │   └──▶ FAILED           illegal jumps raise; transitions take a
               │           │   └──▶ CANCELLED         row lock (with_for_update) and emit an event
               │           └──▶ BLOCKED ──▶ ACTIVE          (TASK_CREATED / TASK_UPDATED /
               └──▶ CANCELLED        └──▶ CANCELLED          TASK_COMPLETED …)
   COMPLETED · FAILED · CANCELLED are terminal (empty transition set)
```

---

## 3. Approval gate (`nexus/approvals/service.py`)

```
 action.requires_approval ─▶ Validator returns needs_approval=True ─▶ task stays out of execution
        │
        ▼ (orchestrator on TASK_UPDATED→QUEUED, or explicit request)
 ApprovalService.create_approval_request(task_id, expires_in_hours=24)
        │  task → BLOCKED ; emit APPROVAL_REQUESTED ; Discord posts an interactive card
        ▼
 Operator decides (Discord buttons / API)
        │
 ApprovalService.evaluate_approval(approval_id, decision, decided_by, reason)
        │  fail-closed if no owner_ids ; reject expired
        ├─ APPROVED → task ACTIVE  → emit APPROVAL_GRANTED → execution flow
        └─ REJECTED → task CANCELLED → emit APPROVAL_REJECTED
 sweep_expired_approvals()  (Job J3) → EXPIRED → parent task CANCELLED
```

`PENDING → {APPROVED | REJECTED | EXPIRED}`; only an active `APPROVED` record opens
`check_approval_gate(task_id)`, which `ExecutionService.start_execution` asserts
before any runtime runs.

---

## 4. Execution flow (`nexus/scheduling/orchestrator.py`)

The `WorkflowOrchestrator` subscribes to the event bus and drives execution:

```
 EVENT                         HANDLER                       ACTION
 TASK_UPDATED (QUEUED)   ─▶ on_task_updated          ─▶ create approval request (if policy)
 APPROVAL_GRANTED        ─▶ on_approval_granted       ─▶ spawn run_execution_flow(task) task
 EXECUTION_COMPLETED/    ─▶ on_execution_finished     ─▶ SummaryEngine → post summary to Discord
   EXECUTION_FAILED

 run_execution_flow(task_id):
   1. health check (abort if control plane unhealthy)
   2. ExecutionService.start_execution(task_id, runner)   # asserts approval gate
   3. adapter = get_runtime_adapter(runtime_id); adapter.initialize()
   4. CLI:   validate(repo,cmd) → execute(cmd) → post stdout/stderr
      Agent: validate_goal(cmd) → execute_goal(cmd)
   5. adapter.checkpoint(...) ; adapter.persist()
   6. finalize_execution(id, resolve_exit_status(result), result)  # honours agent status (H-4)
   7. emit completion → summary
```

In-flight executions are tracked in `WorkflowOrchestrator._tasks` (an
`asyncio.Task` set with a done-callback that discards on completion).

---

## 5. Scheduled jobs (`nexus/scheduling/`)

`build_scheduler` registers J1–J6 on APScheduler's `AsyncIOScheduler`. Each job is
wrapped by `run_scheduled_job` (audit + metric + failure isolation).

| Job | Function | Trigger | Default cadence | Notes |
|---|---|---|---|---|
| J1 research_collection | `run_research_job` | interval | every **2h** (`research_interval_hours`) | → PriorityFeed dispatch |
| J2 daily_briefing | `run_briefing_job` | cron | **08:00** IST (`briefing_hour:minute`) | enqueues Discord + email |
| J3 approval_expiration_sweep | `run_approval_expiry_job` | interval | **15m** | expires stale approvals |
| J4 metrics_aggregation | `run_metrics_aggregation_job` | interval | **5m** | rolls up metrics |
| J5 outbox_health | `run_outbox_health_job` | interval | **10m** | read-only; backlog threshold 100 |
| J6 checkpoint_health | `run_checkpoint_health_job` | interval | **30m** | read-only; stale > 60m |

APScheduler options per job: `coalesce=True`, `max_instances=1`,
`misfire_grace_time=300`. Every run emits `SCHEDULER_JOB_STARTED` then
`…_COMPLETED | …_FAILED | …_SKIPPED` (a job raises `JobSkippedError` to record a
skip, e.g. no research feeds configured) plus a `scheduler_job_duration_ms` metric.

---

## 6. Performance & concurrency envelope

All values are real defaults from `nexus/config.py` and the loop wiring.

### 6.1 Timeout budget (ADR-010 / A-002)

```
 research 900s ─┐
 gemini  1800s ─┼─▶ min(timeout, hard_limit=3600s)   per-runtime ceiling
 claude  2700s ─┘
 agent step budget = 5 steps (agent_max_steps)        → TIMED_OUT if exhausted
```

### 6.2 Background loop cadence

| Loop | Interval | Batch / limit |
|---|---|---|
| `publish_outbox_loop` (events→Discord) | 2.0s | ≤20 events/sweep |
| `run_communication_outbox_loop` (outbox→Discord/email) | 2.0s | lease ≤10 items, 5-min lease |
| `run_metrics_flush_loop` | 5.0s | flush buffer → DB |

### 6.3 Concurrency & consistency

- **Async throughout** (`asyncio`); SQLAlchemy `AsyncSession`.
- **Row locks** (`with_for_update()`) on every state transition (task, approval,
  execution) — no lost updates under concurrent handlers.
- **Single-instance jobs** (`max_instances=1`) + `coalesce` — no overlapping runs.
- **Outbox leasing** — `worker_id` + lease expiry lets the drain loop be safely
  re-entrant; items are processed at-least-once with idempotent status checks.
- **SQLite WAL** + `busy_timeout=5000` — concurrent readers during writes.

### 6.4 Retry & resilience

- **Outbox delivery**: on failure, `attempt_count++`; retry with exponential
  backoff `10 * 2^attempt + jitter`; after `max_attempts` (5) → `dead_letter`
  (emits `NOTIFICATION_FAILED`).
- **Scheduler**: jobs never propagate exceptions; a failure is audited as
  `SCHEDULER_JOB_FAILED` and the scheduler keeps running.
- **Agent recovery**: per-step `checkpoint()` + `agent_steps` enable
  `resume_goal()` after a crash; `last_heartbeat` drives timeout detection (J6).

### 6.5 Observability (metrics recorded, flushed every 5s)

```
 approval_latency_ms          = approval.decided_at − approval.requested_at
 execution_start_latency_ms   = execution.started_at − approval.decided_at
 db_write_duration_ms / transaction_duration_ms   (per get_session)
 scheduler_job_duration_ms    (per job)            event_flush_duration_ms
```

These are exactly the fields surfaced in the morning briefing's "Operational
Performance Metrics" block.

### 6.6 Performance characteristics (summary)

- **Latency floor for notifications**: ≤ ~2s (outbox poll interval) once enqueued.
- **Chat reply latency**: dominated by one OpenRouter completion (planner);
  validation/execution are local DB ops.
- **Throughput knobs**: outbox lease size (10), publish sweep cap (20), loop
  intervals (2s) — all tunable without code changes via the loop wiring/config.
- **Bounded work**: every runtime is hard-capped at `hard_limit`; agents are
  additionally bounded by `agent_max_steps`; jobs are single-instance — the system
  cannot runaway-consume.

See `COMMUNICATION.md` for the outbox/delivery internals and `HARNESS.md` for the
runtime contract that the execution flow dispatches through.
