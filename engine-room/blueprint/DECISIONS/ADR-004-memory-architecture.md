# ADR-004: Memory Architecture — Event Sourcing + Memory Manager

Date: 2026-06-19
Status: Accepted (Per Documentation)

---

## Context

Nexus requires persistent, auditable, recoverable memory (per 08_MEMORY_ARCHITECTURE.md and Critical Constraint 2, 10, 11, 20, 21).

The memory system must be:
- Centralized (single source of truth)
- Persistent (survive restarts)
- Auditable (immutable event log)
- Queryable (by ID, tag, status, date range)
- Recoverable (workflow checkpointing)

---

## Decision

### Pattern: Event Sourcing + Centralized Memory Manager

Every meaningful action produces an immutable event.

Events feed:
1. **Operational Memory** — current task/approval/execution state
2. **Audit Log** — immutable append-only record
3. **Knowledge Memory** — research findings, papers, summaries
4. **System Memory** — health reports, checkpoints, statistics

The **Memory Manager** is the single controller for all memory operations.

**No component bypasses the Memory Manager.**

### Event Taxonomy

```python
# Operational Events
TaskCreated
TaskUpdated
TaskCompleted
TaskCancelled

# Governance Events
ApprovalRequested
ApprovalGranted
ApprovalRejected
ApprovalExpired

# Execution Events
ExecutionStarted
ExecutionCompleted
ExecutionFailed
ExecutionCancelled

# Research Events
ResearchStarted
ResearchCompleted
ResearchFailed

# Communication Events
NotificationSent
NotificationFailed
ReportGenerated

# System Events
SystemStarted
SystemStopped
WorkflowCheckpointed
WorkflowResumed
```

### Memory Domains

| Domain | Contents | Properties |
|---|---|---|
| Operational Memory | Tasks, Approvals, Executions, Research Jobs | Mutable, high-churn |
| Knowledge Memory | Research findings, AI news, paper summaries | Grows over time, low-churn |
| System Memory | Audit log, checkpoints, health, events | Append-only for audit, mutable for health |

### Immutability Rules

- **Audit log**: append-only, never updated, never deleted
- **Approval events**: append-only
- **Execution events**: append-only
- **Task events**: append-only (state transitions recorded as events)

### Retention Policy

- Never hard delete
- Transition: `active` → `archived` → `cold_storage`
- MVP preserves all records

---

## Consequences

**Positive:**
- Complete audit trail without additional work
- Restart recovery from checkpoints
- Daily summaries generated from memory queries
- Every decision is explainable via event history

**Negative:**
- More database tables (events tables alongside state tables)
- Slightly more complex write paths (must emit events)
- Storage growth over time (mitigated by archiving)

---

## Status

Accepted — consistent with documentation.
