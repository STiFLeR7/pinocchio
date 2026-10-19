# H-1 — Nexus Lifecycle Design (v1.1.0)

> **Track H · Design only.** Defines the explicit Nexus execution lifecycle, the cancellation model,
> and the wiring points — using the **existing** event/audit/memory architecture (Rules 3–8). No code.
> Answers Q2 (missing states) and Q6 (cancellation).

---

## 1. Problem (evidence)

Today the loop has **no explicit lifecycle**: `execute_goal` runs until `finish`/`max_steps`/exception,
always returns `exit_code: 0` (`nexus.py:284-289`), `terminate()` is a no-op never called by the
orchestrator (`nexus.py:312-314`, `orchestrator.py:210-216`). Failures, timeouts, and cancellations
are indistinguishable from success.

## 2. Target lifecycle (conceptual state machine)

```
            ┌─────────────┐
            │  VALIDATED  │  (validate_goal passed — governance)
            └──────┬──────┘
                   ▼
            ┌─────────────┐
            │  PLANNING   │  (goal-derived plan generated)
            └──────┬──────┘
                   ▼
        ┌───────► DECIDING ───────────────┐ (structured tool-call from model)
        │          │                       │
        │          ▼                       ▼
        │   TOOL_EXECUTING            (tool == finish) ─► COMPLETED
        │          │
        │          ▼
        │     CHECKPOINTED  (step + checkpoint + heartbeat persisted)
        │          │
        └──────────┘  (loop while within budget and not cancelled)

   Cross-cutting exits (from any active state):
     • cancel signal observed     ─► CANCELLING ─► CANCELLED
     • budget/step bound reached  ─► TIMED_OUT  (distinct from COMPLETED)
     • unrecoverable error        ─► FAILED
```

**Terminal states:** `COMPLETED`, `FAILED`, `TIMED_OUT`, `CANCELLED`. Each maps to a **real exit
status** the orchestrator finalizes faithfully (replacing the always-`SUCCESS` path).

**Resumable boundary:** `CHECKPOINTED` is the only safe resume entry point (recovery-design).

## 3. State representation (reuse, no schema redesign)

- States are expressed via the **existing** `AgentStepRecord.status` and the parent `ExecutionRecord`
  status — extending the *value set*, not the schema. `agent_steps.status` today stores
  `ExecutionStatus.COMPLETED.value` per step (`nexus.py:257`); the design uses the existing
  `ExecutionStatus` enum semantics for per-step and terminal outcomes.
- **No new tables, no migration** are proposed at design level. If a new status value is needed it is an
  enum addition (additive), decided at the implementation AP, not here.
- Terminal outcome is also surfaced as the **return contract** of `execute_goal`/`resume_goal`
  (`status` + `exit_code` + counters), consumed by the orchestrator.

## 4. Cancellation model (Q6)

**Cooperative cancellation** — no forced thread kill of the event loop:

1. **Signal source:** a cancellation request is recorded against the execution (e.g. a boolean/te­rminal
   flag on the existing `ExecutionRecord`, or an in-process asyncio cancellation token held by the
   adapter). Design preference: a **DB-observable signal** so cancellation survives across the async
   boundaries already used by the orchestrator, consistent with the DB-backed approval model (Rule 5).
2. **Observation points:** the loop checks the signal at **state boundaries** — before `DECIDING` and
   before `TOOL_EXECUTING`. This bounds worst-case cancellation latency to one tool execution.
3. **In-flight tool:** a running `execute_command` subprocess is terminated via the **existing sandbox**
   `SandboxProcess.terminate()`/provider terminate (`provider.py:45-48,187-207`) — no new mechanism.
4. **`terminate()` becomes real:** it sets the signal (and triggers the in-flight sandbox kill); the
   loop transitions `CANCELLING → CANCELLED`, persists a final checkpoint + audit, and returns
   `cancelled`.
5. **Wiring (the missing link):** the orchestrator's agent branch (`orchestrator.py:210-216`) and the
   **timeout path** must invoke `terminate()` — today they never do. The scheduler/timeout integration
   reuses `resolve_execution_timeout` (already honored by Nexus `execute_command`, `nexus.py:119`).

## 5. Heartbeats & timeouts

- Heartbeat stays as-is (`nexus.py:291-299`) — real per-step `last_heartbeat`.
- **Timeout** becomes a real terminal state (`TIMED_OUT`) when the configured budget (wall-clock via the
  ADR-010 timeout, and/or the configurable step bound, Cap 19) is exceeded — replacing the silent
  `max_steps` stop that currently reports success.

## 6. Eventing (Rule 6 — no overloading)

- Lifecycle transitions are recorded in the **audit ledger** via the existing `MemoryService.log_event`
  path (as Nexus already does for steps).
- **Decision:** do **not** overload the `SCHEDULER_JOB_*` events (those are scheduler-owned, per
  AP-103A). Whether agent lifecycle warrants dedicated `EXECUTION_*`/`AGENT_*` event types (vs. reusing
  existing execution events) is an **implementation-AP decision**; this design only requires that
  terminal outcomes are auditable and faithfully finalized — not a new event taxonomy.

## 7. Architecture preservation

- Reuses `ExecutionRecord`/`AgentStepRecord`/`WorkflowCheckpointRecord`, audit ledger, governance, and
  sandbox — **no redesign** (Rules 1,2,4,7,8).
- Cancellation is DB-observable → **no hidden coupling** between orchestrator and adapter beyond the
  existing session/record contract (Rule 9).
- Scheduler architecture untouched; timeout reuse only (Rule 3).

## 8. Tier mapping

- **Experimental:** real exit status / terminal-state distinction (no always-`0`).
- **Pilot:** cooperative cancellation wired + tested; `TIMED_OUT` enforced; resumable boundary defined
  (handed to recovery-design).
