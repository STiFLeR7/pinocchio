# ADR-010: Execution Timeout Policy and Heartbeat Tracking

Date: 2026-06-19
Status: Accepted
Decided By: Hill Patel

Adds: Constraint 28 (see below)

---

## Decision

All execution runners have mandatory timeout limits and heartbeat tracking.

No execution runner may run indefinitely.

---

## Timeout Levels

| Runner | Timeout | Notes |
|---|---|---|
| Research Jobs | 15 minutes | Unattended scheduled work |
| Gemini CLI | 30 minutes | Standard code tasks |
| Claude Code | 45 minutes | Complex engineering tasks |
| Hard Limit | 60 minutes | Absolute maximum; any runner |
| Override | Manual Approval Required | For tasks exceeding 60 min |

---

## Heartbeat Tracking (Constraint 28)

Every execution record must contain:

```python
class ExecutionRecord(BaseModel):
    id: UUID
    task_id: UUID
    runner: RunnerType          # GEMINI, CLAUDE, NEXUS, RESEARCH
    started_at: datetime        # When execution began
    last_heartbeat: datetime    # Updated periodically during execution
    timeout_threshold: int      # Seconds until timeout
    completed_at: datetime | None
    exit_status: ExitStatus | None
    logs: str | None
    result: str | None
```

Heartbeat is updated every 30 seconds during execution.

---

## Timeout Flow

```
ExecutionStarted
       │
       ▼
   [Running]
  heartbeat: every 30s
       │
  (timeout elapsed)
       │
       ▼
 Process Terminated
       │
       ▼
   [Timed Out]
       │
       ├── Persist all logs collected so far
       ├── Record ExecutionFailed event
       ├── Notify user via Discord alert channel
       └── Update task status to Failed (recoverable)
```

---

## Implementation Contract

```python
class ExecutionRunner(Protocol):
    """All runners must implement this contract."""

    timeout_seconds: int  # Class-level default

    async def execute(
        self,
        request: ExecutionRequest,
        on_heartbeat: Callable[[str], Awaitable[None]],
    ) -> ExecutionResult: ...
```

The runner is responsible for:
1. Respecting `timeout_seconds`
2. Calling `on_heartbeat` periodically with progress
3. Returning `ExecutionResult` regardless of outcome (success or failure)

---

## Constraint 28 (New Constraint)

> **Constraint 28: No Execution May Run Indefinitely**
>
> Every execution must have:
> - Start timestamp
> - Last heartbeat
> - Timeout threshold
> - Completion timestamp
> - Exit status
>
> An execution without a timeout is incorrectly designed.

This constraint is **mandatory** for:
- Gemini CLI Runner
- Claude Code Runner
- Nexus Agent Runner (if adopted)
- Research Agent Jobs

---

## Status

Accepted — Owner approved 2026-06-19.
